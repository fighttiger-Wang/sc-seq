#!/usr/bin/env python3
"""Deterministic, reusable annotation evidence scoring for cluster-level inputs."""

import csv
import json
from pathlib import Path
from statistics import median

from knowledge_base import build_runtime_config, load_knowledge_base


CORE_VERSION = "2.13.0"
LEGACY_STATEFUL_IDENTITY_IDS = {"CD4_Tex", "CD8_Tex"}
_LOCAL_CONFIG = Path(__file__).resolve().parent / "annotation-evidence-config.v1.json"
_VENDORED_CONFIG = Path(__file__).resolve().parent.parent / "references" / "annotation-evidence-config.v1.json"
DEFAULT_CONFIG = _LOCAL_CONFIG if _LOCAL_CONFIG.is_file() else _VENDORED_CONFIG


def _snapshot_metadata():
    vendored = Path(__file__).resolve().parent.parent / "references" / "annotation-evidence-core.snapshot.json"
    if vendored.is_file():
        return json.loads(vendored.read_text(encoding="utf-8"))
    version = Path(__file__).resolve().parent / "VERSION.json"
    return json.loads(version.read_text(encoding="utf-8")) if version.is_file() else {"core_version": CORE_VERSION}


def _norm(value):
    return str(value).strip().upper()


def _mad(values):
    if not values:
        return 0.0
    center = median(values)
    return median([abs(value - center) for value in values])


def _clamp(value):
    return round(max(0.0, min(1.0, value)), 4)


def compose_display_label(stable_id, primary_state=""):
    """Return the identity label; state is always delivered in a separate field."""
    identity = str(stable_id or "").strip()
    if identity in LEGACY_STATEFUL_IDENTITY_IDS:
        raise ValueError(
            f"Legacy identity/state boundary node {identity} cannot be emitted as Stable_ID; "
            "use CD4_T/CD8_T (or a supported subtype) plus State=Exhausted."
        )
    return identity


def _alias(headers, names, required=True):
    lookup = {_norm(value): index for index, value in enumerate(headers)}
    for name in names:
        if _norm(name) in lookup:
            return lookup[_norm(name)]
    if required:
        raise ValueError(f"Missing required column; expected one of {names}")
    return None


def load_gene_map(path):
    if not path:
        return {}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        headers = next(reader)
        source_i = _alias(headers, ["source_gene", "gene", "original_gene"])
        target_i = _alias(headers, ["canonical_gene", "target_gene", "ortholog_gene"])
        mapping = {}
        for row in reader:
            if row and row[source_i] and row[target_i]:
                mapping[_norm(row[source_i])] = _norm(row[target_i])
    return mapping


def canonical_gene(gene, mapping):
    normalized = _norm(gene)
    return mapping.get(normalized, normalized)


def load_ratio_table(path, expected_clusters, mapping):
    if not path:
        return None
    values = {str(cluster): {} for cluster in expected_clusters}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = "\t" if "\t" in sample.splitlines()[0] else ","
        reader = csv.reader(handle, delimiter=delimiter)
        headers = next(reader)
        gene_i = _alias(headers, ["gene", "GeneName", "feature", "features"])
        cluster_i = _alias(headers, ["group", "cluster", "Target_Cluster", "seurat_clusters"])
        ratio_i = _alias(headers, ["expr_ratio", "detection_ratio", "pct", "pct.1", "pct1"])
        mean_i = _alias(headers, ["mean_expr", "average_expression", "mean"], required=False)
        norm_i = _alias(headers, ["norm_expr", "normalized_expression", "scaled_expression"], required=False)
        for row in reader:
            if not row or not row[gene_i]:
                continue
            cluster = str(row[cluster_i]).strip()
            if cluster not in values:
                continue
            gene = canonical_gene(row[gene_i], mapping)
            ratio = float(row[ratio_i] or 0.0)
            if ratio > 1.0 and ratio <= 100.0:
                ratio /= 100.0
            if ratio < 0.0 or ratio > 1.0:
                raise ValueError(
                    f"Detection ratio must be within 0-1 or 0-100: cluster={cluster}, gene={gene}, value={ratio}"
                )
            if gene in values[cluster]:
                raise ValueError(f"Duplicate gene-cluster ratio row: cluster={cluster}, gene={gene}")
            values[cluster][gene] = {
                "ratio": ratio,
                "mean": None if mean_i is None or row[mean_i] in (None, "", "NA") else float(row[mean_i]),
                "norm": None if norm_i is None or row[norm_i] in (None, "", "NA") else float(row[norm_i]),
            }
    missing = [cluster for cluster, genes in values.items() if not genes]
    if missing:
        raise ValueError(f"Ratio table lacks rows for clusters: {missing}")
    return values


def marker_ratio_table(evidence, mapping):
    values = {str(cluster): {} for cluster in evidence["clusters"]}
    for cluster in evidence["clusters"]:
        for record in evidence["cluster_profiles"][str(cluster)].get("top_markers", []):
            gene = canonical_gene(record["gene"], mapping)
            values[str(cluster)][gene] = {
                "ratio": float(record.get("pct1", 0.0)),
                "background": float(record.get("pct2", 0.0)),
                "log2FC": float(record.get("log2FC", 0.0)),
            }
    return values


def gene_metric(gene, cluster, values, clusters, thresholds, full_ratio):
    current = values.get(str(cluster), {}).get(gene)
    if current is None:
        if full_ratio:
            return {
                "gene": gene, "p_in": 0.0, "p_background": 0.0, "delta": 0.0,
                "robust_z": 0.0, "detected": False, "strong": False, "review": False,
                "log2FC": None,
            }
        return None
    p_in = float(current.get("ratio", 0.0))
    if full_ratio:
        background_values = [
            float(values[str(other)][gene]["ratio"])
            for other in clusters
            if str(other) != str(cluster) and gene in values.get(str(other), {})
        ]
        background = median(background_values) if background_values else 0.0
        spread = 1.4826 * _mad(background_values)
        robust_z = (p_in - background) / max(spread, 0.05)
    else:
        background = float(current.get("background", 0.0))
        spread = 0.0
        robust_z = (p_in - background) / 0.10
    delta = p_in - background
    adaptive_primary = (
        background + thresholds["primary_robust_z"] * max(spread, 0.02)
        if full_ratio
        else thresholds["primary_detection_floor"]
    )
    primary_threshold = max(thresholds["primary_detection_floor"], adaptive_primary)
    return {
        "gene": gene,
        "p_in": round(p_in, 4),
        "p_background": round(background, 4),
        "delta": round(delta, 4),
        "robust_z": round(robust_z, 3),
        "detected": p_in >= thresholds["minimum_detection_floor"],
        "strong": p_in >= primary_threshold
        and (delta >= thresholds["minimum_detection_delta"] or robust_z >= thresholds["primary_robust_z"]),
        "review": p_in >= thresholds["rival_review_floor"]
        and (delta >= thresholds["minimum_detection_delta"] / 2 or robust_z >= thresholds["rival_robust_z"]),
        "log2FC": current.get("log2FC"),
    }


def score_panel(name, panel, cluster, values, clusters, thresholds, full_ratio):
    core = [m for gene in panel["core"] if (m := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio))]
    supportive = [
        m for gene in panel.get("supportive", [])
        if (m := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio))
    ]
    negatives = [
        m for gene in panel.get("negative", [])
        if (m := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio))
    ]
    # Positive-marker-only inputs are sparse by construction.  Missing genes
    # remain unknown, but they must not make one observed marker look like
    # complete coverage of an approved multi-gene panel.
    core_panel_size = max(len(panel["core"]), 1)
    differential_panel_size = max(
        len(panel["core"]) + len(panel.get("supportive", [])), 1
    )
    detected_core = [metric for metric in core if metric["detected"]]
    strong_core = [metric for metric in core if metric["strong"]]
    review_core = [metric for metric in core if metric["review"]]
    specificity = sum(max(metric["delta"], 0.0) for metric in core) / core_panel_size
    differential = [metric for metric in core + supportive if metric.get("log2FC") is not None]
    differential_score = sum(
        min(max(float(metric["log2FC"]), 0.0) / 2.0, 1.0) for metric in differential
    ) / differential_panel_size
    negative_hits = [metric for metric in negatives if metric["review"]]
    absolute_negative_floor = float(panel.get("absolute_negative_detection_floor", 1.0))
    absolute_negative_genes = set(panel.get("absolute_negative_genes", []))
    absolute_negative_hits = [
        metric for metric in negatives
        if metric["gene"] in absolute_negative_genes and metric["p_in"] >= absolute_negative_floor
    ]
    maximum_absolute_negative_hits = int(panel.get("maximum_absolute_negative_hits", 999))
    absolute_negative_blocked = len(absolute_negative_hits) > maximum_absolute_negative_hits
    known_fraction = len(core) / core_panel_size
    coverage = len(detected_core) / core_panel_size
    strong_fraction = len(strong_core) / core_panel_size
    score = _clamp(
        0.35 * coverage
        + 0.30 * strong_fraction
        + 0.25 * min(specificity / 0.5, 1.0)
        + 0.10 * differential_score
        - 0.08 * min(len(negative_hits), 3)
        - 0.15 * min(len(absolute_negative_hits), 2)
    )
    return {
        "label": name,
        "score": score,
        "core_known": len(core),
        "core_panel_size": core_panel_size,
        "core_known_fraction": round(known_fraction, 4),
        "core_detected": len(detected_core),
        "core_strong": len(strong_core),
        "core_review": len(review_core),
        "core_fraction": round(coverage, 4),
        "core_positive_fraction": round(coverage, 4),
        "specificity": round(specificity, 4),
        "supporting_core": [metric for metric in core if metric["review"]],
        "supporting_supportive": [metric for metric in supportive if metric["review"]],
        "negative_conflicts": negative_hits,
        "absolute_negative_conflicts": absolute_negative_hits,
        "absolute_negative_blocked": absolute_negative_blocked,
        "full_ratio_evidence": bool(full_ratio),
        "required_core_markers": int(panel.get("required_core_markers", thresholds["minimum_core_markers"])),
        "decision_rule": panel.get("decision_rule", ""),
        "confounders": panel.get("confounders", ""),
        "coherence_policy": panel.get("coherence_policy", "directional_core"),
    }


def score_states(config, cluster, values, clusters, thresholds, full_ratio, identity_label=None):
    results = []
    for name, genes in config.get("state_panels", {}).items():
        metrics = [m for gene in genes if (m := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio))]
        active = [metric for metric in metrics if metric["review"]]
        active_genes = {metric["gene"] for metric in active}
        minimum = 4 if name in {"exhaustion", "myofibroblastic"} else (3 if name == "emt" else 2)
        coherent = len(active) >= minimum
        if name == "exhaustion":
            coherent = coherent and bool(active_genes & {"TOX", "TOX2"}) and len(active_genes & {"PDCD1", "HAVCR2", "TIGIT", "LAG3", "ENTPD1", "CXCL13"}) >= 2
        if name == "myofibroblastic":
            coherent = coherent and bool(active_genes & {"ACTA2", "TAGLN", "MYL9", "TPM2"}) and bool(active_genes & {"COL1A1", "COL3A1"})
        if coherent:
            results.append({"state": name, "marker_count": len(active), "genes": [metric["gene"] for metric in active]})
    provenance = config.get("panel_provenance", {}).get(identity_label or "", {})
    major_scope = provenance.get("major_label", identity_label)
    priority_rule = config.get("state_priority_rules", {}).get(
        identity_label,
        config.get("state_priority_rules", {}).get(major_scope, {}),
    )
    priority = priority_rule.get("priority", [])
    aliases = {
        "S_phase": "Cycling", "G2M_phase": "Cycling", "interferon": "IFN",
        "activation_APC": "Activated", "exhaustion": "Exhausted",
        "stress": "Stress", "hypoxia": "Hypoxia", "emt": "EMT",
        "angiogenic": "Angiogenic", "myofibroblastic": "Myofibroblastic",
    }
    state_names = []
    for result in results:
        normalized = aliases.get(result["state"], result["state"])
        if normalized not in state_names:
            state_names.append(normalized)
    ordered = sorted(state_names, key=lambda item: (priority.index(item) if item in priority else len(priority), item))
    return {
        "detected": results,
        "state_list": ordered,
        "primary_state": ordered[0] if ordered else "",
        "display_grammar": priority_rule.get("display_grammar", "<Identity>"),
    }


def load_cell_evidence(path):
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Cell evidence must be a JSON object keyed by cluster")
    return {str(key): value for key, value in data.items()}


def _coherent(candidate, thresholds):
    if candidate.get("absolute_negative_blocked", False):
        return False
    if candidate.get("absolute_program_gate", {}).get("passed", False):
        return True
    required = candidate.get("required_core_markers", thresholds["minimum_core_markers"])
    if candidate["core_review"] >= required:
        return True
    if (
        candidate.get("coherence_policy") == "branch_gate_plus_detection"
        and candidate.get("identity_branch_gate", {}).get("passed", False)
        and candidate["core_fraction"] >= thresholds["minimum_core_fraction"]
    ):
        return True
    # In a verified full-ratio matrix, mere detection is not directional
    # evidence. Broadly expressed or ambient genes must not create a leaf call.
    # Retain the coverage fallback only for sparse positive-marker-only inputs,
    # where missing genes are unknown rather than true zeroes.
    return (
        not candidate.get("full_ratio_evidence", False)
        and candidate["core_fraction"] >= thresholds["minimum_core_fraction"]
    )


def _formally_coherent(candidate, thresholds):
    gate = candidate.get("identity_branch_gate", {})
    return (
        _coherent(candidate, thresholds)
        and gate.get("passed", True)
        and (gate.get("assessed", True) or not gate.get("rule_id"))
    )


def _program_hits(cluster, values, marker_floors):
    hits = []
    for gene, floor in marker_floors.items():
        ratio = float(values.get(cluster, {}).get(_norm(gene), {}).get("ratio", 0.0))
        if ratio >= float(floor):
            hits.append({"gene": _norm(gene), "ratio": round(ratio, 4), "floor": float(floor)})
    return hits


def _myeloid_boundary_audit(config, cluster, values, full_ratio, cell_evidence=None):
    """Audit program-level myeloid boundaries that isolated markers cannot resolve."""
    rules = config.get("myeloid_boundary_rules", {})
    if not full_ratio or not rules:
        return {"assessed": False, "reason": "requires_full_cluster_ratio"}

    neutrophil_rule = rules.get("neutrophil_vs_monocyte", {})
    monocyte_hits = _program_hits(
        cluster, values, neutrophil_rule.get("monocyte_program", {}).get("markers", {})
    )
    monocyte_minimum = int(
        neutrophil_rule.get("monocyte_program", {}).get("minimum_markers", 4)
    )
    commitment_hits = _program_hits(
        cluster, values, neutrophil_rule.get("neutrophil_commitment", {}).get("markers", {})
    )
    commitment_minimum = int(
        neutrophil_rule.get("neutrophil_commitment", {}).get("minimum_markers", 2)
    )
    alternatives = []
    for program in neutrophil_rule.get("neutrophil_program_alternatives", []):
        required_hits = _program_hits(cluster, values, program.get("required_markers", {}))
        program_hits = _program_hits(cluster, values, program.get("markers", {}))
        required_passed = len(required_hits) == len(program.get("required_markers", {}))
        passed = required_passed and len(program_hits) >= int(program.get("minimum_markers", 1))
        alternatives.append({
            "program_id": program.get("program_id", ""),
            "passed": passed,
            "required_hits": required_hits,
            "marker_hits": program_hits,
            "minimum_markers": int(program.get("minimum_markers", 1)),
        })
    neutrophil_commitment_passed = len(commitment_hits) >= commitment_minimum
    neutrophil_program_passed = neutrophil_commitment_passed and any(
        item["passed"] for item in alternatives
    )
    immature_neutrophil_program_passed = any(
        item["program_id"] == "early_granule_neutrophil" and item["passed"]
        for item in alternatives
    )
    monocyte_program_passed = len(monocyte_hits) >= monocyte_minimum

    dc_rule = rules.get("dc3_vs_monocyte", {})
    apc_hits = _program_hits(cluster, values, dc_rule.get("apc_program", {}).get("markers", {}))
    dc_hits = _program_hits(cluster, values, dc_rule.get("dc_specific_program", {}).get("markers", {}))
    dc_monocyte_hits = _program_hits(
        cluster, values, dc_rule.get("monocyte_program", {}).get("markers", {})
    )
    dc3_candidate = bool(
        len(apc_hits) >= int(dc_rule.get("apc_program", {}).get("minimum_markers", 3))
        and len(dc_hits) >= int(dc_rule.get("dc_specific_program", {}).get("minimum_markers", 2))
        and len(dc_monocyte_hits) >= int(dc_rule.get("monocyte_program", {}).get("minimum_markers", 3))
    )
    validation = (cell_evidence or {}).get("identity_boundary_validation", {})
    cell_level_validated = bool(
        validation.get("rule_id") == dc_rule.get("rule_id")
        and validation.get("coexpression_validated") is True
        and str(validation.get("method", "")).strip()
    )
    return {
        "assessed": True,
        "neutrophil_vs_monocyte": {
            "rule_id": neutrophil_rule.get("rule_id", ""),
            "monocyte_program_passed": monocyte_program_passed,
            "monocyte_hits": monocyte_hits,
            "neutrophil_commitment_passed": neutrophil_commitment_passed,
            "neutrophil_commitment_hits": commitment_hits,
            "neutrophil_program_passed": neutrophil_program_passed,
            "immature_neutrophil_program_passed": immature_neutrophil_program_passed,
            "neutrophil_program_alternatives": alternatives,
            "neutrophil_blocked_by_monocyte": bool(
                monocyte_program_passed
                and neutrophil_commitment_passed
                and not neutrophil_program_passed
            ),
        },
        "dc3_vs_monocyte": {
            "rule_id": dc_rule.get("rule_id", ""),
            "dc3_boundary_candidate": dc3_candidate,
            "apc_hits": apc_hits,
            "dc_specific_hits": dc_hits,
            "monocyte_hits": dc_monocyte_hits,
            "cell_level_validated": cell_level_validated,
            "validation_method": str(validation.get("method", "")),
        },
    }


def _absolute_program_gate(label, config, cluster, values, full_ratio):
    """Validate a configured leaf program without cluster-relative enrichment.

    Repeated canonical identities can be abundant in one subset, so every member may
    have weak median/MAD specificity even when the absolute identity program is intact.
    This gate remains conservative by requiring core, supportive, and parent-lineage
    anchors together with explicit incompatible-program exclusions.
    """
    rule = next(
        (item for item in config.get("absolute_program_rules", []) if item.get("label") == label),
        None,
    )
    if not full_ratio or not rule:
        return {"rule_id": "", "assessed": False, "passed": False}

    def detected(key, floor_key, default_floor):
        return _detected_branch_anchors(
            cluster, values, rule.get(key, []), float(rule.get(floor_key, default_floor))
        )

    core = detected("core_anchors", "core_detection_floor", 0.25)
    supportive = detected("supportive_anchors", "supportive_detection_floor", 0.10)
    parent = detected("parent_anchors", "parent_detection_floor", 0.10)
    forbidden_hits = []
    for forbidden in rule.get("forbidden_programs", []):
        genes = forbidden.get("anchors", [])
        anchors = _detected_branch_anchors(
            cluster, values, genes, float(forbidden.get("detection_floor", 0.10)),
        )
        minimum_dataset_fraction = forbidden.get("minimum_dataset_fraction")
        dataset_fractions = {}
        if minimum_dataset_fraction is not None:
            relative_anchors = []
            for gene in anchors:
                current = float(values.get(str(cluster), {}).get(gene, {}).get("ratio", 0.0))
                peak = max(
                    (float(profile.get(gene, {}).get("ratio", 0.0)) for profile in values.values()),
                    default=0.0,
                )
                fraction = current / peak if peak > 0 else 0.0
                dataset_fractions[gene] = round(fraction, 4)
                if fraction >= float(minimum_dataset_fraction):
                    relative_anchors.append(gene)
            anchors = relative_anchors
        if len(anchors) >= int(forbidden.get("minimum_anchors", 1)):
            hit = {"program": forbidden.get("program", "forbidden"), "anchors": anchors}
            if minimum_dataset_fraction is not None:
                hit["minimum_dataset_fraction"] = float(minimum_dataset_fraction)
                hit["dataset_fractions"] = dataset_fractions
            forbidden_hits.append(hit)
    passed = bool(
        len(core) >= int(rule.get("minimum_core_anchors", 2))
        and len(supportive) >= int(rule.get("minimum_supportive_anchors", 1))
        and len(parent) >= int(rule.get("minimum_parent_anchors", 2))
        and not forbidden_hits
    )
    return {
        "rule_id": rule.get("rule_id", ""), "assessed": True, "passed": passed,
        "core_anchors": core, "supportive_anchors": supportive, "parent_anchors": parent,
        "forbidden_program_hits": forbidden_hits,
        "coherence_basis": "absolute_program_with_lineage_and_exclusion_gates",
    }


def _project_supported_sibling(ranked, config, thresholds, cluster, values, full_ratio):
    if not full_ratio or not ranked:
        return ranked, {}
    by_label = {candidate["label"]: candidate for candidate in ranked}
    current = ranked[0]
    for rule in config.get("sibling_projection_rules", []):
        if current["label"] != rule.get("over"):
            continue
        preferred = by_label.get(rule.get("preferred"))
        if not preferred or not _formally_coherent(preferred, thresholds):
            continue
        if preferred["core_review"] < int(rule.get("minimum_core_review", 2)):
            continue
        if rule.get("require_absolute_program_gate") and not preferred.get(
            "absolute_program_gate", {}
        ).get("passed", False):
            continue
        if preferred["score"] < current["score"] * float(rule.get("minimum_score_ratio", 0.95)):
            continue
        anchors = _detected_branch_anchors(
            cluster, values, rule.get("required_anchors", []),
            float(rule.get("anchor_detection_floor", 0.10)),
        )
        if len(anchors) < int(rule.get("minimum_required_anchors", 0)):
            continue
        forbidden = _detected_branch_anchors(
            cluster, values, rule.get("forbidden_anchors", []),
            float(rule.get("forbidden_detection_floor", 0.20)),
        )
        if len(forbidden) > int(rule.get("maximum_forbidden_anchors", 999)):
            continue
        projected = [preferred] + [candidate for candidate in ranked if candidate is not preferred]
        return projected, {
            "rule_id": rule.get("rule_id", ""),
            "from": current["label"],
            "to": preferred["label"],
            "required_anchors": anchors,
            "forbidden_anchors": forbidden,
        }
    return ranked, {}


def _major_label(config, label):
    return config.get("major_label_map", {}).get(label, label)


def _identity_path(config, label):
    path = config.get("panel_provenance", {}).get(label, {}).get("parent_path", [])
    return list(path) if path else [label]


def _belongs_to_any(config, label, ancestors):
    path = set(_identity_path(config, label))
    return any(ancestor == label or ancestor in path for ancestor in ancestors)


def _detected_branch_anchors(cluster, values, genes, floor):
    cluster_values = values.get(str(cluster), {})
    return [
        gene for gene in genes
        if gene in cluster_values and float(cluster_values[gene].get("ratio", 0.0)) >= floor
    ]


def _relative_branch_anchors(cluster, values, genes, floor, minimum_fraction):
    cluster_values = values.get(str(cluster), {})
    anchors = []
    fractions = {}
    for gene in genes:
        current = float(cluster_values.get(gene, {}).get("ratio", 0.0))
        peak = max(
            (float(profile.get(gene, {}).get("ratio", 0.0)) for profile in values.values()),
            default=0.0,
        )
        fraction = current / peak if peak > 0 else 0.0
        fractions[gene] = round(fraction, 4)
        if current >= floor and fraction >= minimum_fraction:
            anchors.append(gene)
    return anchors, fractions


def _dataset_relative_conflicts(candidate, values, minimum_fraction):
    retained = []
    for metric in candidate.get("negative_conflicts", []):
        gene = metric.get("gene")
        current = float(metric.get("p_in", 0.0))
        peak = max(
            (float(profile.get(gene, {}).get("ratio", 0.0)) for profile in values.values()),
            default=0.0,
        )
        if peak > 0 and current / peak >= minimum_fraction:
            retained.append(metric)
    return retained


def _identity_branch_gate(candidate, config, cluster, values, full_ratio):
    """Require lineage-defining CD4/CD8 anchors before accepting a branch-specific leaf."""
    matched = []
    for rule in config.get("identity_branch_gates", []):
        if not _belongs_to_any(config, candidate["label"], rule.get("ancestors", [])):
            continue
        floor = float(rule.get("anchor_detection_floor", 0.10))
        anchors = _detected_branch_anchors(cluster, values, rule.get("required_anchors", []), floor)
        minimum = int(rule.get("minimum_required_anchors", 1))
        forbidden_ceiling = float(rule.get("forbidden_detection_ceiling", 1.01))
        forbidden_anchors = _detected_branch_anchors(
            cluster, values, rule.get("forbidden_anchors", []), forbidden_ceiling
        )
        maximum_forbidden = int(rule.get("maximum_forbidden_anchors", len(rule.get("forbidden_anchors", []))))
        relative_floor = rule.get("relative_reference_min_fraction")
        relative_anchors = []
        relative_fractions = {}
        relative_minimum = int(rule.get("minimum_relative_anchors", minimum))
        if relative_floor is not None:
            relative_anchors, relative_fractions = _relative_branch_anchors(
                cluster,
                values,
                rule.get("required_anchors", []),
                floor,
                float(relative_floor),
            )
        if full_ratio:
            assessed = True
            passed = len(anchors) >= minimum and len(forbidden_anchors) <= maximum_forbidden and (
                relative_floor is None or len(relative_anchors) >= relative_minimum
            )
        else:
            # Positive-marker-only input cannot prove an absent branch marker is negative.
            assessed = len(anchors) >= minimum
            passed = True
        matched.append({
            "rule_id": rule["rule_id"],
            "assessed": assessed,
            "passed": passed,
            "required_anchors": list(rule.get("required_anchors", [])),
            "detected_anchors": anchors,
            "minimum_required_anchors": minimum,
            "anchor_detection_floor": floor,
            "forbidden_anchors": list(rule.get("forbidden_anchors", [])),
            "detected_forbidden_anchors": forbidden_anchors,
            "forbidden_detection_ceiling": forbidden_ceiling if rule.get("forbidden_anchors") else None,
            "maximum_forbidden_anchors": maximum_forbidden if rule.get("forbidden_anchors") else 0,
            "relative_reference_min_fraction": relative_floor,
            "minimum_relative_anchors": relative_minimum if relative_floor is not None else 0,
            "relative_reference_anchors": relative_anchors,
            "relative_reference_fractions": relative_fractions,
            "evidence_mode": "full_ratio" if full_ratio else "positive_markers_only",
        })
    if not matched:
        return {
            "rule_id": "",
            "assessed": True,
            "passed": True,
            "required_anchors": [],
            "detected_anchors": [],
            "minimum_required_anchors": 0,
            "anchor_detection_floor": None,
            "evidence_mode": "not_applicable",
        }
    failed = [item for item in matched if not item["passed"]]
    if failed:
        return failed[0]
    assessed = [item for item in matched if item["assessed"]]
    specific = [item for item in assessed if item["rule_id"] != "REQUIRE_COHERENT_TCR_PROGRAM"]
    if specific:
        return specific[0]
    return assessed[0] if assessed else matched[0]


def _common_identity_ancestor(config, first_label, second_label):
    first_path = _identity_path(config, first_label)
    second_path = _identity_path(config, second_label)
    common = ""
    for first, second in zip(first_path, second_path):
        if first != second:
            break
        common = first
    return common


def _major_lineages_incompatible(config, first_label, second_label):
    """Return true only when projected major lineages are unrelated branches."""
    first_identity_path = _identity_path(config, first_label)
    second_identity_path = _identity_path(config, second_label)
    if "Epithelial_cell" in first_identity_path and "Epithelial_cell" in second_identity_path:
        return False
    first_major = _major_label(config, first_label)
    second_major = _major_label(config, second_label)
    if first_major == second_major:
        return False
    first_path = _identity_path(config, first_major)
    second_path = _identity_path(config, second_major)
    return first_major not in second_path and second_major not in first_path


def _project_supported_descendant(ranked, config, thresholds):
    """Prefer a coherent configured child when an ontology parent narrowly out-scores it."""
    if not ranked:
        return ranked, {}
    ancestor_candidate = ranked[0]
    for rule in config.get("descendant_projection_rules", []):
        if ancestor_candidate["label"] != rule.get("ancestor"):
            continue
        descendants = set(rule.get("descendants", []))
        eligible = []
        for candidate in ranked[1:]:
            gate = candidate.get("identity_branch_gate", {})
            gate_only = bool(rule.get("gate_only"))
            if candidate["label"] not in descendants or not gate.get("passed", True):
                continue
            if candidate["core_review"] < int(rule.get("minimum_core_review", thresholds["minimum_core_markers"])):
                continue
            if candidate["score"] < ancestor_candidate["score"] * float(rule.get("minimum_score_ratio_to_ancestor", 1.0)):
                continue
            if gate_only:
                if not gate.get("assessed", False):
                    continue
            elif not _formally_coherent(candidate, thresholds):
                continue
            eligible.append(candidate)
        if not eligible:
            continue
        projected = max(
            eligible,
            key=lambda candidate: (
                len(config.get("panel_provenance", {}).get(candidate["label"], {}).get("parent_path", [])),
                candidate["score"],
            ),
        )
        reordered = [projected, *[candidate for candidate in ranked if candidate is not projected]]
        return reordered, {
            "rule_id": rule.get("rule_id", ""),
            "ancestor_label": ancestor_candidate["label"],
            "ancestor_score": ancestor_candidate["score"],
            "projected_label": projected["label"],
            "projected_score": projected["score"],
            "minimum_score_ratio_to_ancestor": float(rule.get("minimum_score_ratio_to_ancestor", 1.0)),
        }
    return ranked, {}


def _sublineage_conflict(primary, competing, config, cluster, values, full_ratio):
    """Detect approved mutually exclusive sublineages without calling a doublet confirmed."""
    if not full_ratio:
        return None
    for rule in config.get("sublineage_conflict_rules", []):
        left_ancestors = rule.get("left_ancestors", [])
        right_ancestors = rule.get("right_ancestors", [])
        primary_side = (
            "left" if _belongs_to_any(config, primary["label"], left_ancestors)
            else "right" if _belongs_to_any(config, primary["label"], right_ancestors)
            else ""
        )
        if not primary_side:
            continue
        rival_side = "right" if primary_side == "left" else "left"
        rival_ancestors = right_ancestors if rival_side == "right" else left_ancestors
        primary_anchor_key = f"{primary_side}_anchors"
        rival_anchor_key = f"{rival_side}_anchors"
        primary_min_key = f"minimum_{primary_side}_anchors"
        rival_min_key = f"minimum_{rival_side}_anchors"
        floor = float(rule.get("anchor_detection_floor", 0.20))
        primary_anchors = _detected_branch_anchors(cluster, values, rule.get(primary_anchor_key, []), floor)
        if len(primary_anchors) < int(rule.get(primary_min_key, 1)):
            continue
        for candidate in competing:
            if not _belongs_to_any(config, candidate["label"], rival_ancestors):
                continue
            if not candidate.get("identity_branch_gate", {}).get("passed", True):
                continue
            if candidate["core_review"] < int(rule.get("minimum_rival_core_review", 2)):
                continue
            if candidate["score"] < primary["score"] * float(rule.get("minimum_score_ratio", 0.70)):
                continue
            rival_anchors = _detected_branch_anchors(cluster, values, rule.get(rival_anchor_key, []), floor)
            if len(rival_anchors) < int(rule.get(rival_min_key, 1)):
                continue
            return {
                "rule_id": rule["rule_id"],
                "primary_label": primary["label"],
                "rival_label": candidate["label"],
                "primary_branch": primary_side,
                "rival_branch": rival_side,
                "primary_anchors": primary_anchors,
                "rival_anchors": rival_anchors,
                "common_ancestor": _common_identity_ancestor(config, primary["label"], candidate["label"]),
                "rival": candidate,
            }
    return None


def _tnk_provisional(ranked, config, thresholds):
    if _major_label(config, ranked[0]["label"]) not in {"T_cell", "NK_cell"}:
        return "not_T_NK"
    by_label = {candidate["label"]: candidate for candidate in ranked}
    t_candidate = by_label.get("T_cell")
    nk_candidate = by_label.get("NK_cell") or by_label.get("NK")
    t_support = _formally_coherent(t_candidate, thresholds) if t_candidate else False
    nk_support = _formally_coherent(nk_candidate, thresholds) if nk_candidate else False
    nk_specific = set(config.get("tnk_rules", {}).get("nk_specific_anchors", []))
    nk_genes = {
        item["gene"]
        for item in (
            (nk_candidate or {}).get("supporting_core", [])
            + (nk_candidate or {}).get("supporting_supportive", [])
        )
    }
    nk_support = nk_support and bool(nk_genes & nk_specific)
    if t_support and nk_support:
        return "unresolved_T_NK"
    if t_support:
        return "T_supported"
    if nk_support:
        return "NK_supported"
    return "not_T_NK"


def enrich_evidence(
    evidence,
    ratio_path=None,
    gene_map_path=None,
    cell_evidence_path=None,
    config_path=None,
    annotation_level="subcluster",
    species="Human",
    tissue="",
    parent_population="",
    parent_kind="unknown",
    knowledge_base_path=None,
):
    if annotation_level not in {"major", "subcluster"}:
        raise ValueError(f"Unsupported annotation level: {annotation_level}")
    config = json.loads(Path(config_path or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    kb = load_knowledge_base(knowledge_base_path)
    runtime = build_runtime_config(
        kb, species=species, tissue=tissue, annotation_level=annotation_level,
        parent_population=parent_population, parent_kind=parent_kind,
    )
    config.update(runtime)
    if not config.get("identity_panels"):
        raise ValueError("No approved marker panels remain after species/tissue/parent routing")
    mapping = load_gene_map(gene_map_path)
    clusters = [str(cluster) for cluster in evidence["clusters"]]
    ratio_values = load_ratio_table(ratio_path, clusters, mapping)
    full_ratio = ratio_values is not None
    values = ratio_values if full_ratio else marker_ratio_table(evidence, mapping)
    cell_evidence = load_cell_evidence(cell_evidence_path)
    thresholds = config["thresholds"]
    decisions = {}
    for cluster in clusters:
        scored = []
        for name, panel in config["identity_panels"].items():
            candidate = score_panel(name, panel, cluster, values, clusters, thresholds, full_ratio)
            candidate["identity_branch_gate"] = _identity_branch_gate(
                candidate, config, cluster, values, full_ratio
            )
            candidate["absolute_program_gate"] = _absolute_program_gate(
                name, config, cluster, values, full_ratio
            )
            scored.append(candidate)
        ranked = sorted(
            scored,
            key=lambda item: (
                1 if _formally_coherent(item, thresholds) else 0,
                2 if item["identity_branch_gate"]["assessed"] and item["identity_branch_gate"]["passed"]
                else 1 if item["identity_branch_gate"]["passed"] else 0,
                item["score"], item["core_strong"], item["core_review"],
                len(_identity_path(config, item["label"])),
            ),
            reverse=True,
        )
        ranked, sibling_projection = _project_supported_sibling(
            ranked, config, thresholds, cluster, values, full_ratio
        )
        ranked, descendant_projection = _project_supported_descendant(ranked, config, thresholds)
        identity_boundary_audit = _myeloid_boundary_audit(
            config, cluster, values, full_ratio, cell_evidence.get(cluster, {})
        )
        primary = ranked[0]
        neutrophil_boundary = identity_boundary_audit.get("neutrophil_vs_monocyte", {})
        neutrophil_reclassified = bool(neutrophil_boundary.get("neutrophil_blocked_by_monocyte"))
        monocyte_reclassified_to_neutrophil = False
        if primary["label"] == "Neutrophil" and neutrophil_boundary.get("neutrophil_blocked_by_monocyte"):
            monocyte_candidate = next(
                (
                    candidate for candidate in ranked
                    if candidate["label"] in {"Monocyte", "Classical_monocyte", "Nonclassical_monocyte"}
                    and _formally_coherent(candidate, thresholds)
                ),
                None,
            )
            if monocyte_candidate is not None:
                ranked = [monocyte_candidate] + [candidate for candidate in ranked if candidate is not monocyte_candidate]
                primary = monocyte_candidate
        elif (
            primary["label"] in {"Monocyte", "Classical_monocyte", "Nonclassical_monocyte"}
            and neutrophil_boundary.get("neutrophil_program_passed")
            and not neutrophil_boundary.get("monocyte_program_passed")
        ):
            neutrophil_candidate = next(
                (
                    candidate for candidate in ranked
                    if candidate["label"] == "Neutrophil"
                    and candidate.get("core_detected", 0) >= 2
                    and candidate["score"] >= primary["score"] * 0.70
                ),
                None,
            )
            if neutrophil_candidate is not None:
                neutrophil_candidate["absolute_program_gate"] = {
                    "rule_id": neutrophil_boundary.get("rule_id", ""),
                    "assessed": True,
                    "passed": True,
                    "source": "myeloid_boundary_program",
                }
                ranked = [neutrophil_candidate] + [candidate for candidate in ranked if candidate is not neutrophil_candidate]
                primary = neutrophil_candidate
                monocyte_reclassified_to_neutrophil = True
        restrict_to_parent = bool(config.get("restrict_to_parent"))
        parent_ranked = [
            item for item in ranked
            if config.get("panel_provenance", {}).get(item["label"], {}).get("within_parent_scope", True)
        ]
        off_parent_ranked = [
            item for item in ranked
            if not config.get("panel_provenance", {}).get(item["label"], {}).get("within_parent_scope", True)
        ]
        parent_primary = parent_ranked[0] if parent_ranked else None
        off_parent_primary = off_parent_ranked[0] if off_parent_ranked else None
        parent_coherent = _formally_coherent(parent_primary, thresholds) if parent_primary else False
        off_parent_coherent = _formally_coherent(off_parent_primary, thresholds) if off_parent_primary else False
        off_parent_policy = config.get("off_parent_audit", {})
        off_parent_eligible = bool(
            restrict_to_parent
            and full_ratio
            and off_parent_policy.get("enabled_with_full_ratio", True)
            and off_parent_primary
            and off_parent_coherent
            and off_parent_primary["core_review"] >= int(off_parent_policy.get("minimum_core_review", 2))
            and off_parent_primary["core_strong"] >= int(off_parent_policy.get("minimum_core_strong", 0))
        )
        off_parent_dominant = bool(
            off_parent_eligible
            and (
                not parent_coherent
                or (
                    off_parent_primary["score"] >= parent_primary["score"] * float(off_parent_policy.get("minimum_score_ratio", 1.25))
                    and off_parent_primary["score"] - parent_primary["score"] >= float(off_parent_policy.get("minimum_score_margin", 0.15))
                )
            )
        )
        off_parent_conflict = bool(
            off_parent_eligible
            and parent_coherent
            and off_parent_primary["score"] >= parent_primary["score"] * float(off_parent_policy.get("conflict_score_ratio", 0.70))
        )
        if off_parent_dominant and not off_parent_conflict:
            primary = off_parent_primary
        primary_group = config["broad_groups"].get(primary["label"], "unknown")
        primary_major = _major_label(config, primary["label"])
        remaining = [item for item in ranked if item is not primary]
        if annotation_level == "major":
            runner = next((item for item in remaining if _major_label(config, item["label"]) != primary_major), remaining[0])
            competing = [item for item in remaining if _major_label(config, item["label"]) != primary_major]
        else:
            runner = remaining[0]
            competing = remaining
        runner_group = config["broad_groups"].get(runner["label"], "unknown")
        runner_major = _major_label(config, runner["label"])
        margin = round(primary["score"] - runner["score"], 4)
        coherent_primary = _formally_coherent(primary, thresholds)
        cross_identity_rivals = [
            candidate
            for candidate in competing
            if (
                _major_lineages_incompatible(config, primary["label"], candidate["label"])
            )
            and candidate.get("identity_branch_gate", {}).get("passed", True)
            and candidate["core_review"] >= (4 if candidate["label"] == "plasma" else thresholds["rival_core_markers_for_review"])
            and candidate["core_strong"] >= thresholds.get("rival_core_strong_for_review", 0)
            and candidate["score"] >= primary["score"] * thresholds["rival_to_primary_score_ratio"]
        ]
        cross_identity_rival = cross_identity_rivals[0] if cross_identity_rivals else None
        same_group_rival = None
        if annotation_level == "subcluster" and not _major_lineages_incompatible(
            config, primary["label"], runner["label"]
        ):
            if (
                runner.get("identity_branch_gate", {}).get("passed", True)
                and runner["core_review"] >= thresholds["rival_core_markers_for_review"]
                and runner["score"] >= primary["score"] * 0.35
            ):
                same_group_rival = runner
        sublineage_conflict = (
            _sublineage_conflict(primary, competing, config, cluster, values, full_ratio)
            if annotation_level == "subcluster" else None
        )
        if sublineage_conflict:
            same_group_rival = sublineage_conflict["rival"]
        coherent_rival = cross_identity_rival is not None or same_group_rival is not None
        risk_rival = cross_identity_rival or same_group_rival or runner
        risk = "R0_ACCEPT"
        action = "Accept identity; keep state programs separate."
        mixed_risk = "low"
        doublet_risk = "not_assessed_cluster_level"
        ambient_risk = "not_assessed_cluster_level"
        if not coherent_primary or margin < thresholds["minimum_accept_margin"]:
            risk, action = "R1_REVIEW_RETAIN", "Retain provisionally; inspect marker plots and nearest competing identity."
        if neutrophil_reclassified:
            risk = "R1_REVIEW_RETAIN"
            action = (
                "A coherent CD14/FCN1/VCAN monocyte program is present but the required mature, early-granule, "
                "or activated-neutrophil program is incomplete. Retain the monocyte call provisionally, inspect "
                "cell-level CSF3R/FCGR3B versus CD14/FCN1/VCAN coexpression, and block automatic merging."
            )
        elif monocyte_reclassified_to_neutrophil:
            risk = "R1_REVIEW_RETAIN"
            action = (
                "The complete activated-neutrophil program passes while the monocyte program is incomplete. "
                "Retain Neutrophil provisionally and review the granulocyte/monocyte transition at cell level."
            )
        if primary["identity_branch_gate"]["rule_id"] and not primary["identity_branch_gate"]["assessed"]:
            risk = "R1_REVIEW_RETAIN"
            action = "Branch-specific identity lacks an observed CD4/CD8 anchor in positive-marker-only evidence; retain provisionally and verify the lineage marker."
        if sublineage_conflict:
            risk, mixed_risk = "R2_RECLUSTER_OR_DOUBLET_REVIEW", "high"
            action = (
                "Mutually exclusive T-sublineage programs coexist in cluster-level ratios; "
                "inspect single-cell CD4/CD8 versus gamma-delta TCR coexpression and recluster if they occupy separate cells. "
                "Test doublets only if the incompatible programs co-occur within the same cells."
            )
        elif coherent_rival:
            if cross_identity_rival is None:
                risk, action = "R1_REVIEW_RETAIN", "Review subtype boundary; consider within-lineage reclustering."
            else:
                risk, mixed_risk = "R2_RECLUSTER_OR_DOUBLET_REVIEW", "high"
                action = "Inspect single-cell coexpression; recluster if programs occupy separate cells, or test doublets if they co-occur."
        relative_negative_conflicts = _dataset_relative_conflicts(
            primary,
            values,
            float(config.get("negative_conflict_relative_reference_min_fraction", 0.50)),
        )
        if len(relative_negative_conflicts) >= 3:
            risk, mixed_risk = "R2_RECLUSTER_OR_DOUBLET_REVIEW", "high"
            action = "Primary identity has multiple lineage-incompatible markers; inspect single-cell coexpression and recluster or test doublets."
        qc_fraction = float(evidence["cluster_profiles"][cluster].get("qc_state_fraction_top50", 0.0))
        if qc_fraction >= 0.50 and risk == "R0_ACCEPT":
            risk = "R1_REVIEW_RETAIN"
            action = "Identity is coherent, but state/QC genes dominate the top markers; review library complexity and QC metrics."
        cell = cell_evidence.get(cluster, {})
        cell_mixed_population = bool(cell.get("mixed_population_confirmed"))
        cell_mixture_resolved_negative = bool(
            cell.get("reclustering_resolved")
            and cell.get("mixed_population_confirmed") is False
            and cell.get("doublet_call") is not True
            and float(cell.get("doublet_fraction", 0.0) or 0.0) < 0.20
        )
        resolved_cell_components = [
            str(item).strip()
            for item in cell.get("resolved_components", [])
            if str(item).strip()
        ]
        if cell.get("doublet_call") is True or float(cell.get("doublet_fraction", 0.0) or 0.0) >= 0.20:
            risk, doublet_risk = "R3_DOUBLET_CANDIDATE", "high"
            action = "Review per-sample doublet calls and remove only confirmed high-risk cells before reclustering."
        evidence_mode = "cell_validated" if cluster in cell_evidence else ("ratio_enhanced" if full_ratio else "minimal")
        completeness = "full_cell" if evidence_mode == "cell_validated" else ("full_cluster_ratio" if full_ratio else "positive_markers_only")
        tnk_provisional = _tnk_provisional(ranked, config, thresholds)
        if tnk_provisional == "unresolved_T_NK":
            risk, mixed_risk = "R2_RECLUSTER_OR_DOUBLET_REVIEW", "high"
            action = "Mark mixed population/suspected doublet; block automatic merging and inspect cell-level TCR plus NK-program coexpression."
        formal_stable_id = primary["label"]
        formal_major_label = primary_major
        formal_identity_fallback = ""
        if not coherent_primary:
            resolved_parent = config.get("resolved_parent_id", "")
            if annotation_level == "subcluster" and parent_kind == "lineage" and resolved_parent:
                formal_stable_id = resolved_parent
                formal_major_label = _major_label(config, resolved_parent)
                formal_identity_fallback = "confirmed_parent"
            elif annotation_level == "major":
                formal_stable_id = ""
                formal_major_label = ""
                formal_identity_fallback = "unresolved_requires_research"
        if sublineage_conflict:
            formal_stable_id = sublineage_conflict["common_ancestor"] or primary_major
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = "mixed_incompatible_sublineages"
        if off_parent_dominant and not off_parent_conflict:
            formal_stable_id = off_parent_primary["label"]
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = "off_parent_lineage_reassignment"
            risk = "R1_REVIEW_RETAIN"
            action = (
                f"A coherent {formal_stable_id} program dominates while the confirmed parent "
                f"{config.get('resolved_parent_id', '')} is weak; treat this cluster as an off-parent contaminant "
                "and verify the subset provenance before merging."
            )
        if off_parent_conflict:
            formal_stable_id = _common_identity_ancestor(
                config, parent_primary["label"], off_parent_primary["label"]
            ) or "Cell"
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = "mixed_parent_off_parent_lineages"
            risk, mixed_risk = "R2_RECLUSTER_OR_DOUBLET_REVIEW", "high"
            action = (
                "Coherent expected-parent and off-parent programs coexist; inspect cell-level coexpression, "
                "recluster if they occupy separate cells, and test doublets only when they co-occur within cells."
            )
        if cell_mixed_population and len(resolved_cell_components) >= 2:
            formal_stable_id = config.get("resolved_parent_id", "") or primary_major or "Cell"
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = "mixed_incompatible_sublineages"
            if risk != "R3_DOUBLET_CANDIDATE":
                risk, mixed_risk = "R2_RECLUSTER_OR_DOUBLET_REVIEW", "high"
            action = (
                "Cell-level program review and resolving reclustering identify distinct component populations. "
                "Retain the original cluster as a mixed population, report the resolved components, block automatic "
                "merging, and do not imply a doublet unless an explicit cell-level doublet call supports it."
            )
        elif cell_mixture_resolved_negative and risk == "R2_RECLUSTER_OR_DOUBLET_REVIEW":
            risk, mixed_risk = "R1_REVIEW_RETAIN", "low"
            action = (
                "Cell-level program review and reclustering do not resolve a separate competing population or "
                "doublet-enriched component. Retain the coherent primary identity under manual review and treat the "
                "aggregate rival program as an intrinsic state or shared program rather than a confirmed mixture."
            )
        dc3_boundary = identity_boundary_audit.get("dc3_vs_monocyte", {})
        boundary_validation_required = bool(
            dc3_boundary.get("dc3_boundary_candidate")
            and not dc3_boundary.get("cell_level_validated")
        )
        boundary_validation_resolved = bool(
            dc3_boundary.get("dc3_boundary_candidate")
            and dc3_boundary.get("cell_level_validated")
        )
        if boundary_validation_required and risk != "R3_DOUBLET_CANDIDATE":
            risk, mixed_risk = "R2_IDENTITY_BOUNDARY_REVIEW", "indeterminate"
            formal_stable_id = config.get("resolved_parent_id", "") or primary_major or "Cell"
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = "mixed_incompatible_sublineages"
            action = (
                "A coherent APC/DC-specific program and a coherent monocyte program coexist in cluster-level ratios. "
                "Literature can nominate DC3 but cannot establish same-cell coexpression. Report the original cluster "
                "conservatively as a likely mixed Myeloid population, retain cDC2/DC3-like and monocyte components, "
                "require manual review, and block automatic merging. Cell-level validation is optional refinement for "
                "distinguishing separate subpopulations from same-cell coexpression or doublets."
            )
        provenance = config.get("panel_provenance", {}).get(
            formal_stable_id,
            config.get("panel_provenance", {}).get(primary["label"], {}),
        )
        tissue_context_review = bool(provenance.get("tissue_context_review", False))
        if tissue_context_review and risk == "R0_ACCEPT":
            risk = "R1_REVIEW_RETAIN"
            action = "Identity is coherent outside its canonical tissue scope; verify biological context, sample provenance, and contamination."
        elif tissue_context_review and risk == "R1_REVIEW_RETAIN":
            action = f"{action} Also verify the noncanonical tissue context and sample provenance."
        state_result = score_states(config, cluster, values, clusters, thresholds, full_ratio, formal_stable_id)
        resolution_search_required = formal_identity_fallback in {
            "confirmed_parent", "unresolved_requires_research"
        }
        if resolution_search_required:
            action = (
                f"The confirmed parent {formal_stable_id} is only an interim audit result. "
                "Continue the mandatory leaf-resolution pass; do not treat a temporary mapping "
                "or a missing leaf call as successful task completion."
            )
        if formal_stable_id in {"CD4_T", "CD8_T"} and not formal_identity_fallback:
            formal_identity_fallback = "branch_identity_no_supported_leaf"
            resolution_search_required = True
            if risk == "R0_ACCEPT":
                risk = "R1_REVIEW_RETAIN"
            action = (
                f"The {formal_stable_id} branch is coherent, but no finer approved identity leaf is sufficiently supported. "
                "Do not finalize the branch label immediately: run a targeted subtype-resolution search, re-evaluate approved "
                "children and knowledge-base-external candidates with competing-program checks, and require two independent "
                "sources before accepting a researched fallback or external identity."
            )
        mixed_population = bool(
            (cross_identity_rival is not None and not cell_mixture_resolved_negative)
            or tnk_provisional == "unresolved_T_NK"
            or sublineage_conflict is not None
            or off_parent_conflict
            or cell_mixed_population
            or boundary_validation_required
        )
        if mixed_population:
            formal_stable_id = "Multi_cell"
            formal_major_label = "Multi_cell"
            formal_identity_fallback = "multi_cell_annotation"
            resolution_search_required = False
        cell_doublet_supported = bool(
            cell.get("doublet_call") is True
            or float(cell.get("doublet_fraction", 0.0) or 0.0) >= 0.20
        )
        decisions[cluster] = {
            "evidence_mode": evidence_mode,
            "evidence_completeness": completeness,
            "annotation_level_scored": annotation_level,
            "primary_evidence_label": primary["label"],
            "primary_evidence_major_label": primary_major,
            "primary_major_label": formal_major_label,
            "primary_evidence_score": primary["score"],
            "runner_up_evidence_label": runner["label"],
            "runner_up_major_label": runner_major,
            "runner_up_evidence_score": runner["score"],
            "score_margin": margin,
            "positive_marker_coverage": primary["core_fraction"],
            "detection_specificity": primary["specificity"],
            "negative_marker_conflict": [item["gene"] for item in primary["negative_conflicts"]],
            "rival_lineage": risk_rival["label"],
            "rival_major_label": _major_label(config, risk_rival["label"]),
            "rival_lineage_score": risk_rival["score"],
            "tnk_provisional": tnk_provisional,
            "stable_id": formal_stable_id,
            "formal_identity_fallback": formal_identity_fallback,
            "resolution_search_required": resolution_search_required,
            "expected_parent_id": config.get("resolved_parent_id", ""),
            "off_parent_detected": bool(off_parent_dominant or off_parent_conflict),
            "off_parent_reassignment": bool(off_parent_dominant and not off_parent_conflict),
            "off_parent_candidate": off_parent_primary["label"] if off_parent_primary else "",
            "off_parent_candidate_score": off_parent_primary["score"] if off_parent_primary else 0.0,
            "parent_path": ["Multi_cell"] if mixed_population else provenance.get("parent_path", []),
            "tissue_module": [] if mixed_population else provenance.get("tissue_module", []),
            "developmental_stage": "" if mixed_population else provenance.get("developmental_stage", ""),
            "ontology_node_kind": "multi_cell_review" if mixed_population else provenance.get("node_kind", "identity"),
            "tissue_scope": ["multi_tissue"] if mixed_population else provenance.get("tissue_scope", []),
            "tissue_scope_match": provenance.get("tissue_scope_match", True),
            "tissue_context_review": tissue_context_review,
            "panel_species": provenance.get("panel_species", config.get("species")),
            "target_species": provenance.get("target_species", config.get("species")),
            "cross_species_inference": provenance.get("cross_species_inference", False),
            "marker_panel_evidence_ids": provenance.get("evidence_ids", []),
            "marker_panel_evidence_gate": provenance.get("evidence_gate", ""),
            "state_program": state_result["detected"],
            "state_list": state_result["state_list"],
            "primary_state": state_result["primary_state"],
            "display_label": compose_display_label(formal_stable_id, state_result["primary_state"]),
            "disease_role": [],
            "ambient_rna_risk": ambient_risk,
            "mixed_cluster_risk": mixed_risk,
            "doublet_risk": doublet_risk,
            "mixed_population": mixed_population,
            "suspected_doublet": (
                cell_doublet_supported
                if cell_mixed_population
                else False if boundary_validation_required
                else risk in {"R2_RECLUSTER_OR_DOUBLET_REVIEW", "R3_DOUBLET_CANDIDATE"}
            ),
            "auto_merge_allowed": bool(
                not mixed_population
                and not (off_parent_dominant and not off_parent_conflict)
                and not neutrophil_reclassified
                and not boundary_validation_required
            ),
            "mixture_type": (
                "cell_validated_mixed_population" if cell_mixed_population
                else "incompatible_T_sublineages" if sublineage_conflict
                else "parent_off_parent_lineages" if off_parent_conflict
                else "off_parent_contaminant" if off_parent_dominant
                else "aggregate_DC_monocyte_mixed_candidate" if boundary_validation_required
                else "neutrophil_monocyte_boundary_review" if neutrophil_reclassified
                else ""
            ),
            "possible_components": (
                resolved_cell_components if cell_mixed_population
                else [sublineage_conflict["primary_label"], sublineage_conflict["rival_label"]]
                if sublineage_conflict
                else [parent_primary["label"], off_parent_primary["label"]] if off_parent_conflict
                else [off_parent_primary["label"]] if off_parent_dominant
                else ["cDC2_or_DC3_like", "Monocyte"] if boundary_validation_required
                else ["Neutrophil", primary["label"]] if neutrophil_reclassified
                else [primary["label"], risk_rival["label"]] if mixed_population
                else []
            ),
            "sublineage_conflict": (
                {key: value for key, value in sublineage_conflict.items() if key != "rival"}
                if sublineage_conflict else {}
            ),
            "identity_boundary_audit": identity_boundary_audit,
            "boundary_validation_required": boundary_validation_required,
            "boundary_validation_resolved": boundary_validation_resolved,
            "risk_level": risk,
            "recommended_action": action,
            "ranked_identity_evidence": ranked[:5],
            "decision_trace": {
                "core_version": CORE_VERSION,
                "primary_coherent": coherent_primary,
                "rival_coherent": coherent_rival,
                "qc_state_fraction_top50": qc_fraction,
                "primary_broad_group": primary_group,
                "primary_evidence_major_label": primary_major,
                "formal_primary_major_label": formal_major_label,
                "developmental_stage": provenance.get("developmental_stage", ""),
                "tissue_scope_match": provenance.get("tissue_scope_match", True),
                "rival_broad_group": config["broad_groups"].get(risk_rival["label"], "unknown"),
                "rival_major_label": _major_label(config, risk_rival["label"]),
                "sublineage_conflict_rule": sublineage_conflict["rule_id"] if sublineage_conflict else "",
                "identity_branch_gate": primary["identity_branch_gate"],
                "absolute_program_gate": primary.get("absolute_program_gate", {}),
                "dataset_relative_negative_conflicts": relative_negative_conflicts,
                "descendant_projection": descendant_projection,
                "sibling_projection": sibling_projection,
                "identity_boundary_audit": identity_boundary_audit,
                "neutrophil_reclassified_to_monocyte": neutrophil_reclassified,
                "monocyte_reclassified_to_neutrophil": monocyte_reclassified_to_neutrophil,
                "boundary_validation_required": boundary_validation_required,
                "boundary_validation_resolved": boundary_validation_resolved,
                "resolution_search_required": resolution_search_required,
                "expected_parent_id": config.get("resolved_parent_id", ""),
                "parent_candidate": parent_primary["label"] if parent_primary else "",
                "parent_candidate_score": parent_primary["score"] if parent_primary else 0.0,
                "parent_candidate_coherent": parent_coherent,
                "off_parent_candidate": off_parent_primary["label"] if off_parent_primary else "",
                "off_parent_candidate_score": off_parent_primary["score"] if off_parent_primary else 0.0,
                "off_parent_candidate_coherent": off_parent_coherent,
                "off_parent_dominant": off_parent_dominant,
                "off_parent_conflict": off_parent_conflict,
                "threshold_config_version": config["config_version"],
            },
        }
    unresolved = [cluster for cluster, item in decisions.items() if item["tnk_provisional"] == "unresolved_T_NK"]
    evidence["deterministic_annotation_evidence"] = decisions
    evidence["deterministic_tnk_arbitration"] = {
        "recommended_regime": "per_cluster",
        "unresolved_seed_clusters": unresolved,
        "provisional_by_cluster": {cluster: item["tnk_provisional"] for cluster, item in decisions.items()},
        "policy": "Resolve T/NK independently per cluster; unresolved clusters are mixed/suspected-doublet and cannot auto-merge.",
    }
    evidence["annotation_evidence_policy"] = {
        "core_version": CORE_VERSION,
        "config_version": config["config_version"],
        "knowledge_base_version": config.get("knowledge_base_version"),
        "knowledge_base_source": config.get("knowledge_base_source"),
        "species": config.get("species"),
        "tissue": config.get("tissue"),
        "active_tissue_modules": config.get("active_tissue_modules", []),
        "ontology_parent_map": config.get("ontology_parent_map", {}),
        "ontology_node_kind": config.get("ontology_node_kind", {}),
        "ontology_developmental_stage": config.get("ontology_developmental_stage", {}),
        "evidence_source_registry": config.get("evidence_source_registry", {}),
        "off_parent_audit": config.get("off_parent_audit", {}),
        "snapshot": _snapshot_metadata(),
        "annotation_level_scored": annotation_level,
        "thresholds": thresholds,
        "ratio_input": str(Path(ratio_path).resolve()) if ratio_path else None,
        "gene_map_input": str(Path(gene_map_path).resolve()) if gene_map_path else None,
        "cell_evidence_input": str(Path(cell_evidence_path).resolve()) if cell_evidence_path else None,
        "limitations": [
            "Cluster-level ratios can flag but cannot confirm ambient RNA, mixed clusters, or doublets.",
            "Missing genes in positive-marker-only mode are unknown, not zero.",
            "Engineering thresholds are versioned starting defaults, not universal biological cutoffs.",
        ],
    }
    return evidence
