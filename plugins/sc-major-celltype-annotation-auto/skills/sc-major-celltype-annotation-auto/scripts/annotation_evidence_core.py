#!/usr/bin/env python3
"""Deterministic, reusable annotation evidence scoring for cluster-level inputs."""

import csv
import json
from pathlib import Path
from statistics import median

from knowledge_base import build_runtime_config, load_knowledge_base


CORE_VERSION = "2.21.0"
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


def load_ratio_table(path, expected_clusters, mapping, expected_genes=None, require_complete=False):
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
    if require_complete:
        expected = {
            canonical_gene(gene, mapping)
            for gene in (expected_genes or [])
            if str(gene).strip()
        }
        if not expected:
            raise ValueError(
                "Strict full-ratio validation requires the average-expression gene universe; "
                "the input evidence did not provide average_gene_names"
            )
        missing_genes = {
            cluster: sorted(expected - set(genes))
            for cluster, genes in values.items()
            if expected - set(genes)
        }
        if missing_genes:
            preview = {
                cluster: genes[:20] for cluster, genes in missing_genes.items()
            }
            raise ValueError(
                "Strict full-ratio table is incomplete for the average-expression gene universe: "
                f"{preview}"
            )
    return values


def _validate_runtime_snapshot(config, knowledge_base):
    """Reject mixed core/config/knowledge-base snapshots before scoring."""
    snapshot = _snapshot_metadata()
    expected = {
        "core_version": CORE_VERSION,
        "config_version": str(config.get("config_version", "")),
        "knowledge_base_version": str(config.get("knowledge_base_version", "")),
    }
    mismatches = {
        key: {"runtime": value, "snapshot": str(snapshot.get(key, ""))}
        for key, value in expected.items()
        if snapshot.get(key) and str(snapshot.get(key)) != value
    }
    kb_version = str(knowledge_base.get("knowledge_base_version", ""))
    if kb_version and expected["knowledge_base_version"] and kb_version != expected["knowledge_base_version"]:
        mismatches["knowledge_base_runtime"] = {
            "runtime": kb_version,
            "config": expected["knowledge_base_version"],
        }
    if mismatches:
        raise RuntimeError(
            "Annotation runtime snapshot mismatch; do not score with mixed versions: "
            f"{mismatches}"
        )
    return snapshot


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


def score_panel(name, panel, cluster, values, clusters, thresholds, full_ratio, blocked_positive_genes=None):
    blocked_positive_genes = {_norm(gene) for gene in (blocked_positive_genes or [])}
    core = [
        m for gene in panel["core"]
        if _norm(gene) not in blocked_positive_genes
        and (m := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio))
    ]
    supportive = [
        m for gene in panel.get("supportive", [])
        if _norm(gene) not in blocked_positive_genes
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
        "blocked_positive_markers": sorted(blocked_positive_genes),
    }


def score_states(config, cluster, values, clusters, thresholds, full_ratio, identity_label=None, blocked_positive_genes=None):
    blocked_positive_genes = {_norm(gene) for gene in (blocked_positive_genes or [])}
    results = []
    for name, genes in config.get("state_panels", {}).items():
        metrics = [
            m for gene in genes
            if _norm(gene) not in blocked_positive_genes
            and (m := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio))
        ]
        active = [metric for metric in metrics if metric["review"]]
        active_genes = {metric["gene"] for metric in active}
        state_rule = config.get("state_program_rules", {}).get(name, {})
        minimum = int(state_rule.get(
            "minimum_markers",
            4 if name in {"exhaustion", "myofibroblastic"} else (3 if name == "emt" else 2),
        ))
        coherent = len(active) >= minimum
        required_any = set(state_rule.get("required_any", []))
        if required_any:
            coherent = coherent and bool(active_genes & required_any)
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
    parent_gate = candidate.get("major_parent_identity_gate", {})
    absolute_gate = candidate.get("absolute_program_gate", {})
    competition_gate = candidate.get("mutually_exclusive_program_gate", {})
    return (
        _coherent(candidate, thresholds)
        and gate.get("passed", True)
        and (gate.get("assessed", True) or not gate.get("rule_id"))
        and parent_gate.get("passed", True)
        and (not absolute_gate.get("required", False) or absolute_gate.get("passed", False))
        and competition_gate.get("passed", True)
    )


def _program_hits(cluster, values, marker_floors):
    hits = []
    for gene, floor in marker_floors.items():
        ratio = float(values.get(cluster, {}).get(_norm(gene), {}).get("ratio", 0.0))
        if ratio >= float(floor):
            hits.append({"gene": _norm(gene), "ratio": round(ratio, 4), "floor": float(floor)})
    return hits


def _project_prior_identity_program(config, cluster, values, label, full_ratio):
    """Validate a project-prior identity that is not yet an active KB candidate."""
    rule = next(
        (item for item in config.get("project_prior_identity_rules", []) if item.get("label") == label),
        None,
    )
    if not rule:
        return {"assessed": False, "passed": False, "reason": "no_registered_project_prior_rule"}
    if not full_ratio:
        return {"assessed": False, "passed": False, "reason": "requires_full_cluster_ratio"}
    core_hits = _program_hits(cluster, values, rule.get("core_markers", {}))
    supportive_hits = _program_hits(cluster, values, rule.get("supportive_markers", {}))
    forbidden_hits = _program_hits(cluster, values, rule.get("forbidden_markers", {}))
    passed = bool(
        len(core_hits) >= int(rule.get("minimum_core_markers", 3))
        and len(supportive_hits) >= int(rule.get("minimum_supportive_markers", 1))
        and len(forbidden_hits) <= int(rule.get("maximum_forbidden_markers", 0))
    )
    return {
        "rule_id": rule.get("rule_id", ""), "assessed": True, "passed": passed,
        "core_hits": core_hits, "supportive_hits": supportive_hits,
        "forbidden_hits": forbidden_hits,
        "interpretation": rule.get("interpretation", ""),
        "evidence_ids": rule.get("evidence_ids", []),
        "parent_path": rule.get("parent_path", []),
    }


def _program_detection_profile(cluster, values, marker_floors):
    """Summarize all marker prevalences, including values below hit floors."""
    ratios = {
        _norm(gene): round(
            float(values.get(cluster, {}).get(_norm(gene), {}).get("ratio", 0.0)), 4
        )
        for gene in marker_floors
    }
    hits = _program_hits(cluster, values, marker_floors)
    return {
        "marker_ratios": ratios,
        "marker_hits": hits,
        "hit_count": len(hits),
        "mean_detection": round(sum(ratios.values()) / len(ratios), 4) if ratios else 0.0,
    }


def _borderline_program_hit(cluster, values, gene, floor, minimum_fraction):
    ratio = float(values.get(cluster, {}).get(_norm(gene), {}).get("ratio", 0.0))
    near_floor = float(floor) * float(minimum_fraction)
    if near_floor <= ratio < float(floor):
        return {
            "gene": _norm(gene), "ratio": round(ratio, 4), "floor": float(floor),
            "near_floor": round(near_floor, 4), "floor_fraction": float(minimum_fraction),
        }
    return {}


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
    alternative_commitment_rule = neutrophil_rule.get(
        "alternative_program_can_complete_commitment", {}
    )
    alternative_commitment_hits = _program_hits(
        cluster, values, alternative_commitment_rule.get("required_anchor_markers", {})
    )
    alternative_commitment_passed = bool(
        alternative_commitment_rule.get("enabled", False)
        and len(alternative_commitment_hits)
        >= int(alternative_commitment_rule.get("minimum_required_anchors", 1))
        and any(item["passed"] for item in alternatives)
    )
    neutrophil_commitment_passed = bool(
        len(commitment_hits) >= commitment_minimum or alternative_commitment_passed
    )
    neutrophil_program_passed = neutrophil_commitment_passed and any(
        item["passed"] for item in alternatives
    )
    immature_neutrophil_program_passed = any(
        item["program_id"] == "early_granule_neutrophil" and item["passed"]
        for item in alternatives
    )
    monocyte_program_passed = len(monocyte_hits) >= monocyte_minimum

    borderline_rule = neutrophil_rule.get("borderline_activated_neutrophil", {})
    borderline_anchor_hits = _program_hits(
        cluster, values, borderline_rule.get("required_anchor_markers", {})
    )
    borderline_gene = str(borderline_rule.get("borderline_marker", "")).strip()
    commitment_markers = neutrophil_rule.get("neutrophil_commitment", {}).get("markers", {})
    borderline_hit = _borderline_program_hit(
        cluster,
        values,
        borderline_gene,
        commitment_markers.get(borderline_gene, 1.0),
        borderline_rule.get("borderline_floor_fraction", 0.75),
    ) if borderline_gene else {}
    borderline_program = next(
        (
            item for item in alternatives
            if item["program_id"] == borderline_rule.get("program_id", "")
        ),
        {},
    )
    borderline_activated_neutrophil_candidate = bool(
        borderline_rule
        and len(borderline_anchor_hits) == len(borderline_rule.get("required_anchor_markers", {}))
        and borderline_hit
        and len(borderline_program.get("marker_hits", []))
        >= int(borderline_rule.get("minimum_program_markers", 2))
        and (
            not borderline_rule.get("requires_monocyte_program_absent", True)
            or not monocyte_program_passed
        )
    )

    dc_identity_programs = {}
    for identity, program in rules.get("dc_identity_programs", {}).items():
        hits = _program_hits(cluster, values, program.get("markers", {}))
        minimum = int(program.get("minimum_markers", 2))
        dc_identity_programs[identity] = {
            "passed": len(hits) >= minimum,
            "marker_hits": hits,
            "minimum_markers": minimum,
        }
    dc_like_rule = rules.get("dc_like_activation", {})
    dc_like_hits = _program_hits(cluster, values, dc_like_rule.get("markers", {}))
    dc_like_activation = {
        "passed": len(dc_like_hits) >= int(dc_like_rule.get("minimum_markers", 2)),
        "marker_hits": dc_like_hits,
        "minimum_markers": int(dc_like_rule.get("minimum_markers", 2)),
        "interpretation": "state_support_only_not_DC_identity",
    }

    dc_rule = rules.get("dc3_vs_monocyte", {})
    apc_rule = dc_rule.get("apc_program", {})
    dc_specific_rule = dc_rule.get("dc_specific_program", {})
    monocyte_specific_rule = dc_rule.get(
        "monocyte_specific_program", dc_rule.get("monocyte_program", {})
    )
    pan_myeloid_rule = dc_rule.get("pan_myeloid_support", {})
    apc_profile = _program_detection_profile(
        cluster, values, apc_rule.get("markers", {})
    )
    dc_specific_profile = _program_detection_profile(
        cluster, values, dc_specific_rule.get("markers", {})
    )
    monocyte_specific_profile = _program_detection_profile(
        cluster, values, monocyte_specific_rule.get("markers", {})
    )
    pan_myeloid_profile = _program_detection_profile(
        cluster, values, pan_myeloid_rule.get("markers", {})
    )
    macrophage_rule = dc_rule.get("macrophage_exclusion", {})
    macrophage_profile = _program_detection_profile(
        cluster, values, macrophage_rule.get("markers", {})
    )
    apc_hits = apc_profile["marker_hits"]
    dc_hits = dc_specific_profile["marker_hits"]
    dc_monocyte_hits = monocyte_specific_profile["marker_hits"]
    monocyte_specific_minimum = int(monocyte_specific_rule.get("minimum_markers", 3))
    two_marker_rule = monocyte_specific_rule.get("two_marker_competitive_exception", {})
    dc_mean = float(dc_specific_profile["mean_detection"])
    monocyte_mean = float(monocyte_specific_profile["mean_detection"])
    macrophage_mean = float(macrophage_profile["mean_detection"])
    macrophage_competing = bool(
        len(macrophage_profile["marker_hits"]) >= int(macrophage_rule.get("minimum_markers", 3))
        and macrophage_mean >= float(macrophage_rule.get("minimum_mean_detection", 0.35))
        and macrophage_mean >= dc_mean * float(macrophage_rule.get("minimum_ratio_to_dc_specific", 1.0))
    )
    two_marker_competitive = bool(
        len(dc_monocyte_hits) >= int(two_marker_rule.get("minimum_markers", 2))
        and monocyte_mean >= float(two_marker_rule.get("minimum_mean_detection", 0.25))
        and monocyte_mean >= dc_mean * float(two_marker_rule.get("minimum_ratio_to_dc", 0.80))
    )
    monocyte_specific_competitive = bool(
        len(dc_monocyte_hits) >= monocyte_specific_minimum or two_marker_competitive
    )
    dominance_rule = dc_rule.get("cdc2_dominance_review", {})
    cdc2_dominant = bool(
        len(dc_hits) >= int(dominance_rule.get("minimum_dc_specific_markers", 3))
        and len(dc_monocyte_hits) <= int(dominance_rule.get("maximum_monocyte_specific_markers", 2))
        and dc_mean >= monocyte_mean * float(dominance_rule.get("minimum_dominance_ratio", 1.50))
        and dc_mean - monocyte_mean >= float(dominance_rule.get("minimum_absolute_margin", 0.20))
    )
    dc3_candidate = bool(
        len(apc_hits) >= int(apc_rule.get("minimum_markers", 3))
        and len(dc_hits) >= int(dc_specific_rule.get("minimum_markers", 2))
        and monocyte_specific_competitive
        and not macrophage_competing
    )
    if dc3_candidate:
        boundary_reason = "coherent_dc_and_monocyte_specific_programs"
    elif cdc2_dominant:
        boundary_reason = "cdc2_dominant_over_weak_monocyte_background"
    elif macrophage_competing:
        boundary_reason = "macrophage_program_dominates_dc3_competitor"
    elif len(apc_hits) < int(apc_rule.get("minimum_markers", 3)):
        boundary_reason = "apc_program_incomplete"
    elif len(dc_hits) < int(dc_specific_rule.get("minimum_markers", 2)):
        boundary_reason = "dc_specific_program_incomplete"
    else:
        boundary_reason = "monocyte_specific_program_not_competitive"
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
            "alternative_commitment_passed": alternative_commitment_passed,
            "alternative_commitment_hits": alternative_commitment_hits,
            "neutrophil_program_passed": neutrophil_program_passed,
            "immature_neutrophil_program_passed": immature_neutrophil_program_passed,
            "borderline_activated_neutrophil_candidate": borderline_activated_neutrophil_candidate,
            "borderline_anchor_hits": borderline_anchor_hits,
            "borderline_commitment_hit": borderline_hit,
            "neutrophil_program_alternatives": alternatives,
            "neutrophil_blocked_by_monocyte": bool(
                monocyte_program_passed
                and neutrophil_commitment_passed
                and not neutrophil_program_passed
            ),
        },
        "dc_identity_programs": dc_identity_programs,
        "dc_like_activation": dc_like_activation,
        "dc3_vs_monocyte": {
            "rule_id": dc_rule.get("rule_id", ""),
            "dc3_boundary_candidate": dc3_candidate,
            "apc_hits": apc_hits,
            "dc_specific_hits": dc_hits,
            "monocyte_hits": dc_monocyte_hits,
            "monocyte_specific_hits": dc_monocyte_hits,
            "pan_myeloid_hits": pan_myeloid_profile["marker_hits"],
            "macrophage_hits": macrophage_profile["marker_hits"],
            "apc_program_mean": apc_profile["mean_detection"],
            "cdc2_program_mean": dc_specific_profile["mean_detection"],
            "monocyte_specific_program_mean": monocyte_specific_profile["mean_detection"],
            "pan_myeloid_program_mean": pan_myeloid_profile["mean_detection"],
            "macrophage_program_mean": macrophage_mean,
            "monocyte_specific_competitive": monocyte_specific_competitive,
            "two_marker_competitive_exception": two_marker_competitive,
            "macrophage_competing": macrophage_competing,
            "dc3_blocked_by_macrophage": macrophage_competing,
            "cdc2_dominant": cdc2_dominant,
            "boundary_reason": boundary_reason,
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
        return {"rule_id": "", "assessed": False, "passed": False, "required": False}

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
        "required": bool(rule.get("required", False)),
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
    default = config.get("major_label_map", {}).get(label, label)
    vocabulary = {
        str(item).strip() for item in config.get("project_major_vocabulary", [])
        if str(item).strip()
    }
    if not vocabulary:
        return default
    if label in vocabulary:
        return label
    path = list(config.get("panel_provenance", {}).get(label, {}).get("parent_path", []))
    for candidate in reversed(path):
        if candidate in vocabulary:
            return candidate
    equivalences = config.get("project_major_vocabulary_policy", {}).get(
        "identity_equivalences", {}
    )
    for candidate in equivalences.get(label, []):
        if candidate in vocabulary:
            return candidate
    return default


def _identity_path(config, label):
    path = config.get("panel_provenance", {}).get(label, {}).get("parent_path", [])
    return list(path) if path else [label]


def normalize_user_constraints(constraints, clusters, mapping=None):
    """Normalize explicit per-run annotation constraints into an auditable contract."""
    raw = constraints if isinstance(constraints, dict) else {}
    cluster_ids = {str(cluster) for cluster in clusters}

    def values(*names):
        result = []
        for name in names:
            value = raw.get(name, [])
            if value is None:
                continue
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, (list, tuple, set)):
                raise ValueError(f"Annotation constraint {name} must be a list or string")
            result.extend(str(item).strip() for item in value if str(item).strip())
        return result

    def unique(items, normalize=False):
        result, seen = [], set()
        for item in items:
            key = _norm(item) if normalize else str(item).strip()
            if key and key not in seen:
                seen.add(key)
                result.append(key if normalize else str(item).strip())
        return sorted(result)

    global_labels = unique(values("exclude_labels", "excluded_labels"))
    global_markers = unique(values("conflict_markers", "exclude_markers", "blocked_positive_markers"), normalize=True)
    if mapping:
        global_markers = sorted({canonical_gene(gene, mapping) for gene in global_markers})

    raw_clusters = raw.get("clusters", raw.get("by_cluster", {})) or {}
    if not isinstance(raw_clusters, dict):
        raise ValueError("Annotation constraint clusters/by_cluster must be an object")
    by_cluster = {}
    for cluster, item in raw_clusters.items():
        cluster = str(cluster).strip()
        if cluster not in cluster_ids:
            raise ValueError(f"Annotation constraints reference an unknown cluster: {cluster}")
        if not isinstance(item, dict):
            raise ValueError(f"Annotation constraint for cluster {cluster} must be an object")
        raw_labels = item.get("exclude_labels", item.get("excluded_labels", [])) or []
        raw_markers = item.get(
            "conflict_markers", item.get("exclude_markers", item.get("blocked_positive_markers", []))
        ) or []
        if isinstance(raw_labels, str):
            raw_labels = [raw_labels]
        if isinstance(raw_markers, str):
            raw_markers = [raw_markers]
        labels = unique(raw_labels)
        markers = unique(
            raw_markers,
            normalize=True,
        )
        if mapping:
            markers = sorted({canonical_gene(gene, mapping) for gene in markers})
        by_cluster[cluster] = {"exclude_labels": labels, "conflict_markers": markers}
    return {
        "provided": bool(global_labels or global_markers or by_cluster),
        "exclude_labels": global_labels,
        "conflict_markers": global_markers,
        "by_cluster": by_cluster,
        "semantics": {
            "exclude_labels": "Hard final-label exclusion; evidence remains visible and cannot be silently reassigned.",
            "conflict_markers": "Removed from positive identity/state scoring and retained as explicit conflict/contamination evidence.",
        },
    }


def _cluster_constraints(constraints, cluster):
    constraints = constraints or {}
    local = constraints.get("by_cluster", {}).get(str(cluster), {})
    return {
        "exclude_labels": sorted(set(constraints.get("exclude_labels", [])) | set(local.get("exclude_labels", []))),
        "conflict_markers": sorted(set(constraints.get("conflict_markers", [])) | set(local.get("conflict_markers", []))),
    }


def _label_matches_user_exclusion(config, label, excluded_labels):
    label = str(label or "").strip()
    if not label:
        return False
    label_tokens = {_norm(label), *(_norm(item) for item in _identity_path(config, label))}
    label_tokens.add(_norm(_major_label(config, label)))
    return any(_norm(item) in label_tokens for item in excluded_labels if str(item).strip())


def _belongs_to_any(config, label, ancestors):
    path = set(_identity_path(config, label))
    return any(ancestor == label or ancestor in path for ancestor in ancestors)


def _project_label_matches_identity(config, label, project_label):
    """Return whether a project label is a valid major projection of an identity."""
    project_label = str(project_label or "").strip()
    if not project_label:
        return False
    if project_label == label or project_label in _identity_path(config, label):
        return True
    if project_label == config.get("major_label_map", {}).get(label, label):
        return True
    equivalences = config.get("project_major_vocabulary_policy", {}).get(
        "identity_equivalences", {}
    )
    return project_label in equivalences.get(label, [])


def _major_parent_identity_gate(candidate, config, cluster, values, full_ratio, annotation_level):
    """Require a child panel to retain its defining parent-lineage program in major mode."""
    if annotation_level != "major":
        return {"rule_id": "", "assessed": False, "passed": True, "reason": "subcluster_mode"}
    for rule in config.get("major_parent_identity_gates", []):
        ancestors = rule.get("ancestors", [])
        if not _belongs_to_any(config, candidate["label"], ancestors):
            continue
        if rule.get("descendants_only", True) and candidate["label"] in ancestors:
            continue
        floor = float(rule.get("anchor_detection_floor", 0.10))
        anchors = _detected_branch_anchors(
            cluster, values, rule.get("required_anchors", []), floor
        )
        minimum = int(rule.get("minimum_required_anchors", 2))
        if not full_ratio:
            return {
                "rule_id": rule.get("rule_id", ""), "assessed": False, "passed": True,
                "detected_anchors": anchors, "minimum_required_anchors": minimum,
                "reason": "positive_marker_only_cannot_prove_parent_absence",
            }
        return {
            "rule_id": rule.get("rule_id", ""), "assessed": True,
            "passed": len(anchors) >= minimum, "detected_anchors": anchors,
            "minimum_required_anchors": minimum, "anchor_detection_floor": floor,
            "interpretation": rule.get("interpretation", ""),
        }
    return {"rule_id": "", "assessed": False, "passed": True, "reason": "not_applicable"}


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


def _program_profile(cluster, values, program):
    """Summarize cluster prevalence for a biological identity program."""
    floor = float(program.get("detection_floor", 0.10))
    genes = [_norm(gene) for gene in program.get("anchors", [])]
    ratios = {
        gene: float(values.get(str(cluster), {}).get(gene, {}).get("ratio", 0.0))
        for gene in genes
    }
    detected = [gene for gene, ratio in ratios.items() if ratio >= floor]
    return {
        "anchors": genes,
        "detected_anchors": detected,
        "minimum_anchors": int(program.get("minimum_anchors", 2)),
        "detection_floor": floor,
        "ratios": {gene: round(ratio, 4) for gene, ratio in ratios.items()},
        "mean_detection": round(sum(ratios.values()) / len(ratios), 4) if ratios else 0.0,
        "coherent": len(detected) >= int(program.get("minimum_anchors", 2)),
    }


def _mutually_exclusive_program_gate(candidate, config, cluster, values, full_ratio):
    """Arbitrate identity-defining sibling programs before subtype scoring."""
    if not full_ratio:
        return {"rule_id": "", "assessed": False, "passed": True, "reason": "requires_full_cluster_ratio"}
    assessments = []
    for rule in config.get("mutually_exclusive_program_rules", []):
        sides = rule.get("sides", {})
        candidate_side = next(
            (name for name, side in sides.items()
             if _belongs_to_any(config, candidate["label"], side.get("ancestors", []))),
            "",
        )
        if not candidate_side:
            continue
        rival_side = next((name for name in sides if name != candidate_side), "")
        if not rival_side:
            continue
        own = _program_profile(cluster, values, sides[candidate_side])
        rival = _program_profile(cluster, values, sides[rival_side])
        own_mean = float(own["mean_detection"])
        rival_mean = float(rival["mean_detection"])
        ratio_threshold = float(rule.get("minimum_dominance_ratio", 1.25))
        margin_threshold = float(rule.get("minimum_absolute_margin", 0.10))
        rival_dominant = bool(
            rival["coherent"] and rival_mean >= own_mean * ratio_threshold
            and rival_mean - own_mean >= margin_threshold
        )
        own_dominant = bool(
            own["coherent"] and own_mean >= rival_mean * ratio_threshold
            and own_mean - rival_mean >= margin_threshold
        )
        unresolved_dual = bool(own["coherent"] and rival["coherent"] and not own_dominant and not rival_dominant)
        assessments.append({
            "rule_id": rule.get("rule_id", ""),
            "assessed": True,
            "passed": bool(not rival_dominant),
            "candidate_side": candidate_side,
            "rival_side": rival_side,
            "candidate_program": own,
            "rival_program": rival,
            "candidate_dominant": own_dominant,
            "rival_dominant": rival_dominant,
            "unresolved_dual_program": unresolved_dual,
            "minimum_dominance_ratio": ratio_threshold,
            "minimum_absolute_margin": margin_threshold,
            "resolution": (
                "candidate_dominant" if own_dominant else "rival_dominant" if rival_dominant
                else "unresolved_requires_cell_level_validation" if unresolved_dual
                else "candidate_program_incoherent"
            ),
            "validation_ladder": rule.get("validation_ladder", []),
            "biological_invariant": rule.get("biological_invariant", ""),
        })
    if not assessments:
        return {"rule_id": "", "assessed": True, "passed": True, "reason": "not_applicable"}
    failed = [item for item in assessments if not item["passed"]]
    unresolved = [item for item in assessments if item["unresolved_dual_program"]]
    selected = dict((failed or unresolved or assessments)[0])
    selected["passed"] = all(item["passed"] for item in assessments)
    selected["all_applicable_rules_passed"] = selected["passed"]
    selected["assessments"] = assessments
    return selected


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


def _is_identity_ancestor(config, ancestor_label, descendant_label):
    """Return true only for a strict ontology ancestor relationship."""
    if not ancestor_label or not descendant_label or ancestor_label == descendant_label:
        return False
    return ancestor_label in _identity_path(config, descendant_label)


def _competing_program_audit(primary, candidate, config, thresholds, policy=None):
    """Require a rival program to be specific, directional, and competitive.

    Absolute detection alone is not evidence of a second population.  The same
    gate is used for broad T/NK arbitration and ordinary cross-lineage rivals so
    ubiquitous background programs cannot create a mixed-cell call.
    """
    policy = {**config.get("competing_program_policy", {}), **(policy or {})}
    minimum_review = int(policy.get("minimum_core_review", thresholds["rival_core_markers_for_review"]))
    minimum_strong = int(policy.get("minimum_core_strong", thresholds.get("rival_core_strong_for_review", 0)))
    minimum_ratio = float(policy.get("minimum_score_ratio", thresholds["rival_to_primary_score_ratio"]))
    minimum_specificity = float(policy.get("minimum_specificity", 0.0))
    primary_score = float((primary or {}).get("score", 0.0))
    candidate_score = float((candidate or {}).get("score", 0.0))
    checks = {
        "candidate_present": candidate is not None,
        "not_primary_ancestor": bool(
            candidate is not None
            and not _is_identity_ancestor(config, candidate.get("label", ""), (primary or {}).get("label", ""))
        ),
        "formally_coherent": bool(candidate is not None and _formally_coherent(candidate, thresholds)),
        "minimum_core_review": bool(candidate is not None and candidate.get("core_review", 0) >= minimum_review),
        "minimum_core_strong": bool(candidate is not None and candidate.get("core_strong", 0) >= minimum_strong),
        "minimum_specificity": bool(candidate is not None and float(candidate.get("specificity", 0.0)) >= minimum_specificity),
        "minimum_score_ratio": bool(
            candidate is not None
            and (primary_score <= 0.0 or candidate_score >= primary_score * minimum_ratio)
        ),
    }
    return {
        "eligible": all(checks.values()),
        "primary_label": str((primary or {}).get("label", "")),
        "candidate_label": str((candidate or {}).get("label", "")),
        "candidate_score": candidate_score,
        "primary_score": primary_score,
        "score_ratio": round(candidate_score / primary_score, 4) if primary_score > 0 else None,
        "candidate_core_review": int((candidate or {}).get("core_review", 0)),
        "candidate_core_strong": int((candidate or {}).get("core_strong", 0)),
        "candidate_specificity": float((candidate or {}).get("specificity", 0.0)),
        "thresholds": {
            "minimum_core_review": minimum_review,
            "minimum_core_strong": minimum_strong,
            "minimum_score_ratio": minimum_ratio,
            "minimum_specificity": minimum_specificity,
        },
        "checks": checks,
    }


def _cross_identity_competitor_policy(candidate, config, thresholds):
    """Use the stricter off-parent gate inside a lineage-constrained run."""
    policy = {
        "minimum_core_review": (
            4 if candidate["label"] == "plasma"
            else thresholds["rival_core_markers_for_review"]
        ),
        "minimum_core_strong": thresholds.get("rival_core_strong_for_review", 0),
        "minimum_score_ratio": config.get("competing_program_policy", {}).get(
            "minimum_score_ratio", thresholds["rival_to_primary_score_ratio"]
        ),
        "minimum_specificity": config.get("competing_program_policy", {}).get(
            "minimum_specificity", 0.0
        ),
        "policy_source": "generic_competing_program",
        "background_review_score_ratio": config.get("competing_program_policy", {}).get(
            "minimum_score_ratio", thresholds["rival_to_primary_score_ratio"]
        ),
    }
    within_parent_scope = config.get("panel_provenance", {}).get(
        candidate["label"], {}
    ).get("within_parent_scope", True)
    if config.get("restrict_to_parent") and not within_parent_scope:
        off_parent = config.get("off_parent_audit", {})
        policy.update({
            "minimum_core_review": int(off_parent.get("minimum_core_review", 3)),
            "minimum_core_strong": int(off_parent.get("minimum_core_strong", 2)),
            "minimum_score_ratio": float(off_parent.get("conflict_score_ratio", 0.70)),
            "minimum_specificity": float(off_parent.get("minimum_specificity", 0.10)),
            "policy_source": "lineage_constrained_off_parent_conflict",
        })
    return policy


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
            if not candidate.get("mutually_exclusive_program_gate", {}).get("passed", True):
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


def _tnk_arbitration(ranked, config, thresholds):
    if _major_label(config, ranked[0]["label"]) not in {"T_cell", "NK_cell"}:
        return {"status": "not_T_NK", "possible_components": [], "reason": "primary_outside_T_NK"}
    primary = ranked[0]
    primary_major = _major_label(config, primary["label"])
    by_label = {candidate["label"]: candidate for candidate in ranked}
    t_candidate = by_label.get("T_cell")
    nk_candidate = by_label.get("NK_cell") or by_label.get("NK")
    primary_coherent = _formally_coherent(primary, thresholds)
    t_support = bool(primary_coherent and primary_major == "T_cell") or (
        _formally_coherent(t_candidate, thresholds) if t_candidate else False
    )
    nk_support = bool(primary_coherent and primary_major == "NK_cell") or (
        _formally_coherent(nk_candidate, thresholds) if nk_candidate else False
    )
    nk_specific = set(config.get("tnk_rules", {}).get("nk_specific_anchors", []))
    nk_genes = {
        item["gene"]
        for item in (
            (nk_candidate or {}).get("supporting_core", [])
            + (nk_candidate or {}).get("supporting_supportive", [])
        )
    }
    nk_support = nk_support and bool(nk_genes & nk_specific or primary_major == "NK_cell")
    t_competitor = _competing_program_audit(primary, t_candidate, config, thresholds)
    nk_competitor = _competing_program_audit(primary, nk_candidate, config, thresholds)
    if t_support and nk_support:
        if primary_major == "NK_cell" and not t_competitor["eligible"]:
            status = "NK_supported"
            reason = "T_program_present_but_not_dataset_specific_competitor"
        elif primary_major == "T_cell" and not nk_competitor["eligible"]:
            status = "T_supported"
            reason = "NK_program_present_but_not_dataset_specific_competitor"
        else:
            status = "unresolved_T_NK"
            reason = "two_directionally_specific_competing_programs"
        return {
            "status": status,
            "possible_components": ["T_cell", "NK_cell"] if status == "unresolved_T_NK" else [],
            "reason": reason,
            "primary_label": primary["label"],
            "primary_major": primary_major,
            "T_program_supported": t_support,
            "NK_program_supported": nk_support,
            "T_competitor_audit": t_competitor,
            "NK_competitor_audit": nk_competitor,
        }
    if t_support:
        status = "T_supported"
        reason = "T_program_only"
    elif nk_support:
        status = "NK_supported"
        reason = "NK_program_only"
    else:
        status = "not_T_NK"
        reason = "no_coherent_T_or_NK_program"
    return {
        "status": status,
        "possible_components": [],
        "reason": reason,
        "primary_label": primary["label"],
        "primary_major": primary_major,
        "T_program_supported": t_support,
        "NK_program_supported": nk_support,
        "T_competitor_audit": t_competitor,
        "NK_competitor_audit": nk_competitor,
    }


def _tnk_provisional(ranked, config, thresholds):
    """Compatibility wrapper retained for downstream callers and tests."""
    return _tnk_arbitration(ranked, config, thresholds)["status"]


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
    project_major_vocabulary=None,
    project_label_prior=None,
    require_complete_ratio=False,
    sample_context=None,
    user_constraints=None,
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
    snapshot = _validate_runtime_snapshot(config, kb)
    config["project_major_vocabulary"] = [
        str(item).strip() for item in (project_major_vocabulary or [])
        if str(item).strip()
    ]
    config["project_label_prior"] = {
        str(cluster): str(label).strip()
        for cluster, label in (project_label_prior or {}).items()
        if str(label).strip()
    }
    if not config.get("identity_panels"):
        raise ValueError("No approved marker panels remain after species/tissue/parent routing")
    mapping = load_gene_map(gene_map_path)
    clusters = [str(cluster) for cluster in evidence["clusters"]]
    expected_genes = evidence.get("average_gene_names", [])
    ratio_values = load_ratio_table(
        ratio_path,
        clusters,
        mapping,
        expected_genes=expected_genes,
        require_complete=bool(require_complete_ratio and ratio_path),
    )
    full_ratio = ratio_values is not None
    expected_gene_set = {
        canonical_gene(gene, mapping)
        for gene in expected_genes
        if str(gene).strip()
    }
    ratio_complete = bool(
        full_ratio
        and expected_gene_set
        and all(expected_gene_set <= set(cluster_values) for cluster_values in ratio_values.values())
    )
    values = ratio_values if full_ratio else marker_ratio_table(evidence, mapping)
    cell_evidence = load_cell_evidence(cell_evidence_path)
    normalized_constraints = normalize_user_constraints(user_constraints, clusters, mapping)
    thresholds = config["thresholds"]
    decisions = {}
    for cluster in clusters:
        cluster_constraints = _cluster_constraints(normalized_constraints, cluster)
        blocked_positive_genes = set(cluster_constraints["conflict_markers"])
        scored = []
        for name, panel in config["identity_panels"].items():
            candidate = score_panel(
                name, panel, cluster, values, clusters, thresholds, full_ratio,
                blocked_positive_genes=blocked_positive_genes,
            )
            candidate["identity_branch_gate"] = _identity_branch_gate(
                candidate, config, cluster, values, full_ratio
            )
            candidate["major_parent_identity_gate"] = _major_parent_identity_gate(
                candidate, config, cluster, values, full_ratio, annotation_level
            )
            candidate["absolute_program_gate"] = _absolute_program_gate(
                name, config, cluster, values, full_ratio
            )
            candidate["mutually_exclusive_program_gate"] = _mutually_exclusive_program_gate(
                candidate, config, cluster, values, full_ratio
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
        original_ranked = list(ranked)
        excluded_ranked = [
            candidate for candidate in ranked
            if _label_matches_user_exclusion(config, candidate["label"], cluster_constraints["exclude_labels"])
        ]
        allowed_ranked = [candidate for candidate in ranked if candidate not in excluded_ranked]
        user_constraint_conflict = bool(excluded_ranked)
        if allowed_ranked:
            ranked = allowed_ranked + excluded_ranked
        else:
            ranked = original_ranked
        ranked, sibling_projection = _project_supported_sibling(
            ranked, config, thresholds, cluster, values, full_ratio
        )
        ranked, descendant_projection = _project_supported_descendant(ranked, config, thresholds)
        identity_boundary_audit = _myeloid_boundary_audit(
            config, cluster, values, full_ratio, cell_evidence.get(cluster, {})
        )
        primary = ranked[0]
        project_prior_label = config.get("project_label_prior", {}).get(cluster, "")
        project_prior_audit = {
            "provided_label": project_prior_label,
            "applied": False,
            "selected_candidate": "",
            "reason": "not_provided" if not project_prior_label else "no_supported_matching_candidate",
        }
        if annotation_level == "major" and project_prior_label:
            prior_policy = config.get("project_major_vocabulary_policy", {})
            prior_candidates = [
                candidate for candidate in ranked
                if _project_label_matches_identity(config, candidate["label"], project_prior_label)
                and _formally_coherent(candidate, thresholds)
            ]
            if prior_candidates:
                selected = prior_candidates[0]
                original_primary_label = primary["label"]
                minimum_ratio = float(prior_policy.get("minimum_candidate_score_ratio", 0.35))
                boundary = identity_boundary_audit.get("neutrophil_vs_monocyte", {})
                program_supported = bool(
                    selected["label"] == "Neutrophil"
                    and boundary.get("neutrophil_program_passed")
                )
                if selected["score"] >= primary["score"] * minimum_ratio or program_supported:
                    ranked = [selected] + [candidate for candidate in ranked if candidate is not selected]
                    primary = selected
                    project_prior_audit.update({
                        "applied": True,
                        "selected_candidate": selected["label"],
                        "selected_score": selected["score"],
                        "original_primary": original_primary_label,
                        "minimum_candidate_score_ratio": minimum_ratio,
                        "program_supported": program_supported,
                        "reason": "supported_project_major_tiebreaker",
                    })
        neutrophil_boundary = identity_boundary_audit.get("neutrophil_vs_monocyte", {})
        neutrophil_reclassified = bool(neutrophil_boundary.get("neutrophil_blocked_by_monocyte"))
        monocyte_reclassified_to_neutrophil = False
        borderline_neutrophil_retained = False
        if (
            primary["label"] == "Neutrophil"
            and neutrophil_boundary.get("borderline_activated_neutrophil_candidate")
            and not neutrophil_boundary.get("monocyte_program_passed")
        ):
            primary["absolute_program_gate"] = {
                "rule_id": neutrophil_boundary.get("rule_id", ""),
                "assessed": True,
                "passed": True,
                "source": "borderline_activated_neutrophil_review",
                "provisional": True,
            }
            borderline_neutrophil_retained = True
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
            and (
                neutrophil_boundary.get("neutrophil_program_passed")
                or neutrophil_boundary.get("borderline_activated_neutrophil_candidate")
            )
            and not neutrophil_boundary.get("monocyte_program_passed")
        ):
            borderline_candidate = bool(
                neutrophil_boundary.get("borderline_activated_neutrophil_candidate")
                and not neutrophil_boundary.get("neutrophil_program_passed")
            )
            neutrophil_candidate = next(
                (
                    candidate for candidate in ranked
                    if candidate["label"] == "Neutrophil"
                    and candidate.get("core_detected", 0) >= 2
                    and (borderline_candidate or candidate["score"] >= primary["score"] * 0.70)
                ),
                None,
            )
            if neutrophil_candidate is not None:
                neutrophil_candidate["absolute_program_gate"] = {
                    "rule_id": neutrophil_boundary.get("rule_id", ""),
                    "assessed": True,
                    "passed": True,
                    "source": (
                        "borderline_activated_neutrophil_review"
                        if borderline_candidate else "myeloid_boundary_program"
                    ),
                    "provisional": borderline_candidate,
                }
                ranked = [neutrophil_candidate] + [candidate for candidate in ranked if candidate is not neutrophil_candidate]
                primary = neutrophil_candidate
                monocyte_reclassified_to_neutrophil = True
                borderline_neutrophil_retained = borderline_candidate
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
            and off_parent_primary["specificity"] >= float(off_parent_policy.get("minimum_specificity", 0.0))
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
            margin = round(primary["score"] - runner["score"], 4)
        else:
            # A canonical parent is supporting hierarchy evidence for its leaf,
            # not a biological rival.  Exclude ancestors from subtype margins
            # and mixed-population arbitration while retaining descendants so
            # a broad primary can still be resolved to a supported leaf.
            competing = [
                item for item in remaining
                if not _is_identity_ancestor(config, item["label"], primary["label"])
            ]
            runner = competing[0] if competing else remaining[0]
            margin = round(
                primary["score"] - runner["score"] if competing else primary["score"], 4
            )
        runner_group = config["broad_groups"].get(runner["label"], "unknown")
        runner_major = _major_label(config, runner["label"])
        coherent_primary = _formally_coherent(primary, thresholds)
        cross_identity_rivals = []
        cross_identity_audits = {}
        for candidate in competing:
            if not _major_lineages_incompatible(config, primary["label"], candidate["label"]):
                continue
            competitor_policy = _cross_identity_competitor_policy(
                candidate, config, thresholds
            )
            audit = _competing_program_audit(
                primary, candidate, config, thresholds, competitor_policy
            )
            audit["policy_source"] = competitor_policy["policy_source"]
            audit["background_review_signal"] = bool(
                not audit["eligible"]
                and audit["checks"]["formally_coherent"]
                and audit["checks"]["minimum_core_review"]
                and audit["checks"]["minimum_core_strong"]
                and audit["checks"]["minimum_specificity"]
                and float(candidate.get("score", 0.0)) >= float(primary.get("score", 0.0))
                * float(competitor_policy.get("background_review_score_ratio", 0.35))
            )
            cross_identity_audits[candidate["label"]] = audit
            if audit["eligible"]:
                cross_identity_rivals.append(candidate)
        cross_identity_rival = cross_identity_rivals[0] if cross_identity_rivals else None
        cross_identity_background_reviews = [
            candidate for candidate in competing
            if cross_identity_audits.get(candidate["label"], {}).get("background_review_signal")
        ]
        cross_identity_background_review = (
            cross_identity_background_reviews[0] if cross_identity_background_reviews else None
        )
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
        elif monocyte_reclassified_to_neutrophil and not borderline_neutrophil_retained:
            risk = "R1_REVIEW_RETAIN"
            action = (
                "The complete activated-neutrophil program passes while the monocyte program is incomplete. "
                "Retain Neutrophil provisionally and review the granulocyte/monocyte transition at cell level."
            )
        elif borderline_neutrophil_retained or neutrophil_boundary.get("borderline_activated_neutrophil_candidate"):
            risk = "R1_REVIEW_RETAIN"
            action = (
                "A borderline activated-neutrophil program is present: CSF3R and PI3/SLPI/CXCL8 support the branch, "
                "FCGR3B is just below its conservative commitment floor, and the monocyte program is incomplete. "
                "Do not force a monocyte leaf. Complete targeted quantitative-QC/UMAP review and record any identity "
                "override with structured evidence."
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
        elif cross_identity_background_review is not None:
            risk = "R1_REVIEW_RETAIN"
            action = (
                f"A moderate off-parent {cross_identity_background_review['label']} program is directionally enriched "
                "but remains below the lineage-constrained conflict ratio. Retain the coherent parent-lineage identity, "
                "treat the secondary program as a state/background review signal, inspect UMAP and cell-level distribution, "
                "and block automatic merging without labeling the cluster Multi_cell."
            )
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
        evidence_mode = "cell_validated" if cluster in cell_evidence else ("full_ratio" if ratio_complete else ("partial_ratio" if full_ratio else "positive_markers_only"))
        completeness = "full_cell" if evidence_mode == "cell_validated" else ("full_cluster_ratio" if ratio_complete else ("partial_cluster_ratio" if full_ratio else "positive_markers_only"))
        tnk_arbitration = _tnk_arbitration(ranked, config, thresholds)
        tnk_provisional = tnk_arbitration["status"]
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
        cdc2_dominant_review = bool(dc3_boundary.get("cdc2_dominant"))
        if cdc2_dominant_review:
            formal_stable_id = "cDC2"
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = ""
            if risk == "R0_ACCEPT":
                risk, mixed_risk = "R1_REVIEW_RETAIN", "low"
            action = (
                "The complete cDC2 program dominates a weak monocyte-background signal. Retain cDC2, "
                "review the modest CD14/VCAN background, and keep automatic merging blocked until the "
                "cluster context is checked; do not classify it as Multi_cell from pan-myeloid LST1/TYROBP."
            )
        if boundary_validation_required and risk != "R3_DOUBLET_CANDIDATE":
            risk, mixed_risk = "R2_IDENTITY_BOUNDARY_REVIEW", "indeterminate"
            formal_stable_id = "DC3"
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = "dc3_boundary_best_fit"
            action = (
                "A coherent APC/DC-specific program and a coherent monocyte program coexist in cluster-level ratios. "
                "This is the defining aggregate pattern for the best-fit terminal identity DC3, so annotate DC3 rather "
                "than escaping to a broad Myeloid parent. Keep confidence reduced, require manual review, and block "
                "automatic merging. Cluster-level evidence does not establish purity or same-cell coexpression; cell-level "
                "validation or resolving reclustering remains an optional refinement, not a prerequisite for naming."
            )
        elif boundary_validation_resolved and not cell_mixed_population and risk != "R3_DOUBLET_CANDIDATE":
            formal_stable_id = "DC3"
            formal_major_label = _major_label(config, formal_stable_id)
            formal_identity_fallback = "dc3_boundary_cell_validated"
            if risk == "R0_ACCEPT":
                risk, mixed_risk = "R1_REVIEW_RETAIN", "low"
            action = (
                "The registered APC, DC-specific, and monocyte-specific DC3 programs pass and the supplied cell-level "
                "boundary evidence supports their within-cluster relationship. Retain DC3, keep state separate, and "
                "review automatic merging against the validated component structure."
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
        dc_like_activation = identity_boundary_audit.get("dc_like_activation", {})
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
        project_prior_program = _project_prior_identity_program(
            config, cluster, values, project_prior_label, full_ratio
        )
        cell_doublet_supported = bool(
            cell.get("doublet_call") is True
            or float(cell.get("doublet_fraction", 0.0) or 0.0) >= 0.20
        )
        aggregate_mixed_evidence = bool(
            (cross_identity_rival is not None and not cell_mixture_resolved_negative)
            or tnk_provisional == "unresolved_T_NK"
            or sublineage_conflict is not None
            or off_parent_conflict
            or cell_mixed_population
        )
        major_identity_first = bool(
            annotation_level == "major"
            and config.get("major_identity_policy", {}).get("mode") == "major_identity_first"
        )
        formal_multi_cell = bool(
            cell_mixed_population
            or (
                aggregate_mixed_evidence
                and (
                    not major_identity_first
                    or not coherent_primary
                    or cell_doublet_supported
                )
            )
        )
        mixed_population = bool(formal_multi_cell)
        if formal_multi_cell:
            formal_stable_id = "Multi_cell"
            formal_major_label = "Multi_cell"
            formal_identity_fallback = "multi_cell_annotation"
            resolution_search_required = False
        elif annotation_level == "major" and project_prior_label == "debris":
            qc_policy = config.get("major_identity_policy", {}).get("qc_exception", {})
            if (
                qc_policy.get("enabled_with_project_prior", True)
                and qc_fraction >= float(qc_policy.get("minimum_qc_state_fraction_top50", 0.30))
            ):
                formal_stable_id = "debris"
                formal_major_label = "debris"
                formal_identity_fallback = "project_supported_qc_exception"
                resolution_search_required = False
                risk = "R1_REVIEW_RETAIN"
                action = (
                    "The project review assigns an explicit QC/debris bucket and QC/state genes dominate the cluster. "
                    "Retain this narrow exception without generalizing debris removal to other major clusters; verify "
                    "cell-level complexity and defer any removal decision to QC/subclustering review."
                )
                project_prior_audit.update({
                    "applied": True, "selected_candidate": "debris",
                    "reason": "project_supported_qc_exception",
                    "qc_state_fraction_top50": qc_fraction,
                })
        elif annotation_level == "major" and project_prior_program.get("passed"):
            formal_stable_id = project_prior_label
            formal_major_label = project_prior_label
            formal_identity_fallback = "validated_project_prior_program"
            resolution_search_required = False
            risk = "R1_REVIEW_RETAIN"
            action = (
                f"The project prior {project_prior_label} passes its registered identity program although the identity "
                "is not yet an active ranked knowledge-base candidate. Retain it under reduced confidence, structured "
                "literature/override audit, and manual review; do not use the prior without the program gate."
            )
            project_prior_audit.update({
                "applied": True, "selected_candidate": project_prior_label,
                "reason": "validated_project_prior_program",
                "identity_program": project_prior_program,
            })
        elif annotation_level == "major" and _project_label_matches_identity(
            config, formal_stable_id, project_prior_label
        ):
            formal_major_label = project_prior_label
            project_prior_audit.update({
                "applied": True,
                "selected_candidate": formal_stable_id,
                "reason": "supported_project_output_projection",
            })
        user_constraint_audit = {
            "provided": normalized_constraints["provided"],
            "exclude_labels": cluster_constraints["exclude_labels"],
            "conflict_markers": cluster_constraints["conflict_markers"],
            "excluded_ranked_candidates": [candidate["label"] for candidate in excluded_ranked],
            "selected_candidate_before_constraint": original_ranked[0]["label"] if original_ranked else "",
            "selected_final_identity": formal_stable_id,
            "final_identity_excluded": _label_matches_user_exclusion(
                config, formal_stable_id, cluster_constraints["exclude_labels"]
            ),
            "conflict": user_constraint_conflict,
            "policy": normalized_constraints["semantics"],
        }
        if user_constraint_audit["final_identity_excluded"]:
            alternatives = [
                candidate for candidate in ranked
                if not _label_matches_user_exclusion(
                    config, candidate["label"], cluster_constraints["exclude_labels"]
                ) and _formally_coherent(candidate, thresholds)
            ]
            alternative = alternatives[0] if alternatives else None
            if alternative is not None:
                formal_stable_id = alternative["label"]
                formal_major_label = _major_label(config, formal_stable_id)
                formal_identity_fallback = "user_constraint_alternative"
                user_constraint_audit["selected_final_identity"] = formal_stable_id
                user_constraint_audit["final_identity_excluded"] = False
                risk = "R1_REVIEW_RETAIN"
                action = (
                    "The highest-scoring identity was explicitly excluded for this run. Retain the highest-scoring "
                    "allowed coherent alternative under manual review and preserve the excluded candidate in the audit trail."
                )
            else:
                formal_stable_id = ""
                formal_major_label = ""
                formal_identity_fallback = "user_constraint_no_allowed_candidate"
                resolution_search_required = True
                risk = "R2_IDENTITY_BOUNDARY_REVIEW"
                action = (
                    "All supported candidates are explicitly excluded for this run. Formal delivery is blocked until "
                    "the user permits a candidate or supplies a defensible replacement identity with evidence."
                )
                user_constraint_audit["selected_final_identity"] = ""
        elif user_constraint_conflict:
            risk = "R1_REVIEW_RETAIN" if risk == "R0_ACCEPT" else risk
            action = (
                f"User constraints exclude candidate(s): {', '.join(user_constraint_audit['excluded_ranked_candidates'])}. "
                "Keep the allowed identity provisional, retain excluded candidates as conflicts, and block automatic merging."
            )
        state_result = score_states(
            config, cluster, values, clusters, thresholds, full_ratio, formal_stable_id,
            blocked_positive_genes=blocked_positive_genes,
        )
        if dc_like_activation.get("passed") and formal_stable_id not in {"cDC1", "cDC2", "Migratory_DC", "DC3"}:
            state_result["detected"].append({
                "state": "dc_like_activation",
                "marker_count": len(dc_like_activation.get("marker_hits", [])),
                "genes": [item.get("gene", "") for item in dc_like_activation.get("marker_hits", [])],
                "interpretation": "state_support_only_not_DC_identity",
            })
            if "DC_like" not in state_result["state_list"]:
                state_result["state_list"].append("DC_like")
            if not state_result["primary_state"]:
                state_result["primary_state"] = "DC_like"
        mixed_evidence = bool(aggregate_mixed_evidence and not mixed_population)
        review_in_subcluster = bool(
            mixed_evidence
            or mixed_population
            or formal_identity_fallback == "project_supported_qc_exception"
        )
        if major_identity_first and mixed_evidence:
            action = (
                f"Retain the coherent major identity {formal_major_label or formal_stable_id}. "
                "Record the competing program as mixed evidence, block automatic merging, inspect UMAP/cell-level "
                "distribution, and resolve contamination, substructure, or doublets during the relevant subcluster/QC stage."
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
            "user_constraint_audit": user_constraint_audit,
            "user_constraint_conflict": user_constraint_conflict,
            "excluded_candidate_labels": user_constraint_audit["excluded_ranked_candidates"],
            "user_conflict_markers": cluster_constraints["conflict_markers"],
            "expected_parent_id": config.get("resolved_parent_id", ""),
            "off_parent_detected": bool(off_parent_dominant or off_parent_conflict),
            "off_parent_reassignment": bool(off_parent_dominant and not off_parent_conflict),
            "off_parent_candidate": off_parent_primary["label"] if off_parent_primary else "",
            "off_parent_candidate_score": off_parent_primary["score"] if off_parent_primary else 0.0,
            "parent_path": (
                ["Multi_cell"] if formal_multi_cell
                else project_prior_program.get("parent_path", [])
                if formal_identity_fallback == "validated_project_prior_program"
                else provenance.get("parent_path", [])
            ),
            "tissue_module": [] if formal_multi_cell else provenance.get("tissue_module", []),
            "developmental_stage": "" if formal_multi_cell else provenance.get("developmental_stage", ""),
            "ontology_node_kind": "multi_cell_review" if formal_multi_cell else provenance.get("node_kind", "identity"),
            "tissue_scope": ["multi_tissue"] if formal_multi_cell else provenance.get("tissue_scope", []),
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
            "mixed_evidence": mixed_evidence,
            "review_in_subcluster": review_in_subcluster,
            "mixed_population": mixed_population,
            "suspected_doublet": (
                cell_doublet_supported
                if major_identity_first
                else cell_doublet_supported
                if cell_mixed_population
                else False if boundary_validation_required
                else risk in {"R2_RECLUSTER_OR_DOUBLET_REVIEW", "R3_DOUBLET_CANDIDATE"}
            ),
            "auto_merge_allowed": bool(
                not mixed_population
                and not mixed_evidence
                and not user_constraint_conflict
                and not (off_parent_dominant and not off_parent_conflict)
                and not neutrophil_reclassified
                and not borderline_neutrophil_retained
                and not boundary_validation_required
                and not cdc2_dominant_review
                and cross_identity_background_review is None
            ),
            "mixture_type": (
                "cell_validated_mixed_population" if cell_mixed_population
                else "incompatible_T_sublineages" if sublineage_conflict
                else "parent_off_parent_lineages" if off_parent_conflict
                else "off_parent_contaminant" if off_parent_dominant
                else "dc3_monocyte_identity_boundary_review" if boundary_validation_required
                else "cdc2_dominant_monocyte_background_review" if cdc2_dominant_review
                else "off_parent_background_program_review" if cross_identity_background_review is not None
                else "neutrophil_monocyte_boundary_review" if neutrophil_reclassified
                else "borderline_activated_neutrophil_review" if borderline_neutrophil_retained
                else "incompatible_T_NK_programs" if tnk_provisional == "unresolved_T_NK"
                else "major_identity_with_cross_lineage_review" if mixed_evidence
                else ""
            ),
            "possible_components": (
                resolved_cell_components if cell_mixed_population
                else [sublineage_conflict["primary_label"], sublineage_conflict["rival_label"]]
                if sublineage_conflict
                else [parent_primary["label"], off_parent_primary["label"]] if off_parent_conflict
                else [off_parent_primary["label"]] if off_parent_dominant
                else [] if boundary_validation_required
                else ["Neutrophil", primary["label"]] if neutrophil_reclassified
                else tnk_arbitration.get("possible_components", []) if tnk_provisional == "unresolved_T_NK"
                else [primary["label"], risk_rival["label"]] if (mixed_population or mixed_evidence)
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
                "major_parent_identity_gate": primary.get("major_parent_identity_gate", {}),
                "absolute_program_gate": primary.get("absolute_program_gate", {}),
                "mutually_exclusive_program_gate": primary.get("mutually_exclusive_program_gate", {}),
                "dataset_relative_negative_conflicts": relative_negative_conflicts,
                "descendant_projection": descendant_projection,
                "sibling_projection": sibling_projection,
                "competing_program_policy": config.get("competing_program_policy", {}),
                "cross_identity_competitor_audits": cross_identity_audits,
                "cross_identity_background_review": (
                    cross_identity_background_review["label"]
                    if cross_identity_background_review is not None else ""
                ),
                "tnk_arbitration": tnk_arbitration,
                "identity_boundary_audit": identity_boundary_audit,
                "neutrophil_reclassified_to_monocyte": neutrophil_reclassified,
                "monocyte_reclassified_to_neutrophil": monocyte_reclassified_to_neutrophil,
                "borderline_neutrophil_retained": borderline_neutrophil_retained,
                "boundary_validation_required": boundary_validation_required,
                "boundary_validation_resolved": boundary_validation_resolved,
                "cdc2_dominant_review": cdc2_dominant_review,
                "major_identity_first": major_identity_first,
                "mixed_evidence": mixed_evidence,
                "review_in_subcluster": review_in_subcluster,
                "project_prior_audit": project_prior_audit,
                "user_constraint_audit": user_constraint_audit,
                "formal_multi_cell": formal_multi_cell,
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
        "policy": (
            "Resolve T/NK independently per cluster. In major-identity-first mode retain a coherent dominant major "
            "identity, record unresolved T/NK as mixed evidence, and block automatic merging; use Multi_cell only "
            "when no coherent dominant identity or cell-level mixed/doublet evidence exists."
        ),
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
        "major_identity_policy": config.get("major_identity_policy", {}),
        "project_major_vocabulary": config.get("project_major_vocabulary", []),
        "project_label_prior": config.get("project_label_prior", {}),
        "user_constraints": normalized_constraints,
        "snapshot": snapshot,
        "annotation_level_scored": annotation_level,
        "thresholds": thresholds,
        "ratio_input": str(Path(ratio_path).resolve()) if ratio_path else None,
        "gene_map_input": str(Path(gene_map_path).resolve()) if gene_map_path else None,
        "cell_evidence_input": str(Path(cell_evidence_path).resolve()) if cell_evidence_path else None,
        "ratio_validation": {
            "provided": bool(ratio_path),
            "strict_requested": bool(require_complete_ratio and ratio_path),
            "complete": ratio_complete,
            "expected_gene_count": len(expected_gene_set),
        },
        "sample_context": sample_context or {},
        "limitations": [
            "Cluster-level ratios can flag but cannot confirm ambient RNA, mixed clusters, or doublets.",
            "Missing genes in positive-marker-only mode are unknown, not zero.",
            "Engineering thresholds are versioned starting defaults, not universal biological cutoffs.",
        ],
    }
    return evidence
