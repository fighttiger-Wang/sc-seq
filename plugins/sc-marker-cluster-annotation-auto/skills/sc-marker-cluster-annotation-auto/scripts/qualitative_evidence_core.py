#!/usr/bin/env python3
"""Qualitative biological-gate evidence core for cluster annotation.

The module preserves per-gene quantitative measurements but never calculates
an aggregate identity score, confidence grade, candidate margin, or ranked
candidate table.
"""

from __future__ import annotations

import json
from pathlib import Path

from qualitative_gate_helpers import (
    CORE_VERSION, DEFAULT_CONFIG, _absolute_program_gate, _identity_branch_gate,
    _identity_program_gate, _major_label, _mutually_exclusive_program_gate, _myeloid_boundary_audit,
    _snapshot_metadata, _validate_runtime_snapshot, gene_metric,
    load_cell_evidence, load_gene_map, load_ratio_table, marker_ratio_table,
    normalize_user_constraints,
)
from knowledge_base import build_runtime_config, load_knowledge_base


GATES = {"通过", "不通过", "未确定", "不适用"}


def _status(passed=None, assessed=True, applicable=True):
    if not applicable:
        return "不适用"
    if not assessed:
        return "未确定"
    return "通过" if passed else "不通过"


def _cluster_constraints(constraints, cluster):
    shared = {
        "exclude_labels": list(constraints.get("exclude_labels", [])),
        "conflict_markers": list(constraints.get("conflict_markers", [])),
    }
    specific = constraints.get("by_cluster", {}).get(str(cluster), {})
    shared["exclude_labels"].extend(specific.get("exclude_labels", []))
    shared["conflict_markers"].extend(specific.get("conflict_markers", []))
    shared["exclude_labels"] = sorted({str(item).strip() for item in shared["exclude_labels"] if str(item).strip()})
    shared["conflict_markers"] = sorted({str(item).strip().upper() for item in shared["conflict_markers"] if str(item).strip()})
    return shared


def _candidate_excluded(label, excluded, config):
    if label in excluded:
        return True
    path = config.get("panel_provenance", {}).get(label, {}).get("parent_path", [])
    return any(item in excluded for item in path)


def _evaluate_panel(label, panel, cluster, values, clusters, thresholds, full_ratio, config, blocked):
    core_metrics = [
        metric for gene in panel.get("core", [])
        if gene.upper() not in blocked
        if (metric := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio)) is not None
    ]
    supportive_metrics = [
        metric for gene in panel.get("supportive", [])
        if gene.upper() not in blocked
        if (metric := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio)) is not None
    ]
    negative_metrics = [
        metric for gene in panel.get("negative", [])
        if (metric := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio)) is not None
    ]
    required = int(panel.get("required_core_markers", thresholds.get("minimum_core_markers", 2)))
    supported_core = [item for item in core_metrics if item["review"]]
    strong_core = [item for item in core_metrics if item["strong"]]
    supportive = [item for item in supportive_metrics if item["review"]]
    conflicts = [item for item in negative_metrics if item["review"]]
    missing = [gene for gene in panel.get("core", []) if gene.upper() not in {item["gene"] for item in core_metrics}]

    if full_ratio:
        identity_passed = len(supported_core) >= required and len(strong_core) >= min(required, 2)
        identity_assessed = True
    else:
        identity_passed = len(supported_core) >= required
        identity_assessed = identity_passed

    candidate = {
        "label": label,
        "core_review": len(supported_core),
        "core_strong": len(strong_core),
        "supportive_review": len(supportive),
        "negative_conflicts": conflicts,
    }
    branch = _identity_branch_gate(candidate, config, cluster, values, full_ratio)
    identity_program = _identity_program_gate(label, config, cluster, values, full_ratio)
    absolute = _absolute_program_gate(label, config, cluster, values, full_ratio)
    mutually_exclusive = _mutually_exclusive_program_gate(candidate, config, cluster, values, full_ratio)
    absolute_required = bool(absolute.get("required"))
    absolute_ok = bool(absolute.get("passed")) if absolute_required else True
    # A passed explicit boundary program may reinterpret a broad panel
    # exclusion (for example, non-dominant gamma-delta background in DNT).
    # It cannot bypass the dedicated program's own forbidden/absence checks.
    exclusion_passed = bool(not conflicts or identity_program.get('passed', False))
    identity_passed = bool(identity_passed or identity_program.get('passed', False))
    branch_passed = bool(branch.get('passed', True) or identity_program.get('passed', False))
    program_passed = bool(
        identity_passed
        and branch_passed
        and mutually_exclusive.get("passed", True)
        and absolute_ok
        and exclusion_passed
    )
    provenance = config.get("panel_provenance", {}).get(label, {})
    return {
        "label": label,
        "major_label": _major_label(config, label),
        "parent_path": provenance.get("parent_path", []),
        "within_parent_scope": provenance.get("within_parent_scope", True),
        "off_parent_audit": provenance.get("off_parent_audit", False),
        "tissue_scope_match": provenance.get("tissue_scope_match", True),
        "developmental_stage": provenance.get("developmental_stage", ""),
        "panel_species": provenance.get("panel_species", config.get("species", "")),
        "cross_species_inference": provenance.get("cross_species_inference", False),
        "evidence_ids": provenance.get("evidence_ids", []),
        "identity_anchor_gate": _status(identity_passed, identity_assessed),
        "parent_lineage_gate": _status(provenance.get("within_parent_scope", True), applicable=config.get("resolved_parent_id", "") != ""),
        "exclusion_gate": _status(exclusion_passed, assessed=bool(negative_metrics) or full_ratio),
        "branch_gate": _status(branch.get("passed"), branch.get("assessed", True), bool(branch.get("rule_id"))),
        "identity_program_gate": _status(identity_program.get("passed"), identity_program.get("assessed", False), bool(identity_program.get("rule_id"))),
        "identity_program_priority": int(identity_program.get("priority", 0)),
        "absolute_program_gate": _status(absolute.get("passed"), absolute.get("assessed", False), absolute_required),
        "mutually_exclusive_gate": _status(mutually_exclusive.get("passed"), mutually_exclusive.get("assessed", False), bool(mutually_exclusive.get("rule_id"))),
        "program_gate": _status(program_passed, identity_assessed),
        "required_identity_anchors": required,
        "supporting_core": supported_core,
        "strong_core": strong_core,
        "supporting_supportive": supportive,
        "conflicting_markers": conflicts,
        "missing_core_markers": missing,
        "branch_audit": branch,
        "identity_program_audit": identity_program,
        "absolute_program_audit": absolute,
        "mutually_exclusive_audit": mutually_exclusive,
        "decision_rule": panel.get("decision_rule", ""),
        "confounders": panel.get("confounders", ""),
    }


def _is_more_defensible(candidate, current, prior_label=""):
    """Apply an explicit biological precedence ladder; never combine metrics."""
    if current is None:
        return True, "first_eligible_program"
    if candidate["parent_lineage_gate"] == "通过" and current["parent_lineage_gate"] != "通过":
        return True, "declared_parent_scope_precedence"
    if current["parent_lineage_gate"] == "通过" and candidate["parent_lineage_gate"] != "通过":
        return False, "current_matches_declared_parent_scope"
    if prior_label and candidate["label"] == prior_label and current["label"] != prior_label:
        return True, "project_prior_tiebreaker"
    if candidate.get("identity_program_gate") == "通过" and current.get("identity_program_gate") != "通过":
        return True, "complete_configured_identity_program"
    if current.get("identity_program_gate") == "通过" and candidate.get("identity_program_gate") != "通过":
        return False, "current_has_complete_configured_identity_program"
    if candidate.get("identity_program_gate") == "通过" and current.get("identity_program_gate") == "通过":
        if candidate.get("identity_program_priority", 0) != current.get("identity_program_priority", 0):
            return candidate.get("identity_program_priority", 0) > current.get("identity_program_priority", 0), "configured_identity_specificity_precedence"
    if candidate["program_gate"] == "通过" and current["program_gate"] != "通过":
        return True, "complete_identity_program"
    if current["program_gate"] == "通过" and candidate["program_gate"] != "通过":
        return False, "current_has_complete_identity_program"
    if candidate["absolute_program_gate"] == "通过" and current["absolute_program_gate"] != "通过":
        return True, "required_absolute_program_gate"
    if current["absolute_program_gate"] == "通过" and candidate["absolute_program_gate"] != "通过":
        return False, "current_has_required_absolute_program_gate"
    if candidate["branch_gate"] == "通过" and current["branch_gate"] == "不通过":
        return True, "identity_branch_gate"
    if current["branch_gate"] == "通过" and candidate["branch_gate"] == "不通过":
        return False, "current_has_identity_branch_gate"
    if candidate["program_gate"] == "通过" and current["program_gate"] == "通过":
        if current["label"] in candidate["parent_path"] and candidate["label"] not in current["parent_path"]:
            return True, "complete_supported_descendant"
        if candidate["label"] in current["parent_path"] and current["label"] not in candidate["parent_path"]:
            return False, "current_is_complete_supported_descendant"
    if len(candidate["strong_core"]) != len(current["strong_core"]):
        return len(candidate["strong_core"]) > len(current["strong_core"]), "more_strong_identity_anchors"
    if len(candidate["supporting_core"]) != len(current["supporting_core"]):
        return len(candidate["supporting_core"]) > len(current["supporting_core"]), "more_supported_identity_anchors"
    if len(candidate["conflicting_markers"]) != len(current["conflicting_markers"]):
        return len(candidate["conflicting_markers"]) < len(current["conflicting_markers"]), "fewer_explicit_conflicts"
    if len(candidate["supporting_supportive"]) != len(current["supporting_supportive"]):
        return len(candidate["supporting_supportive"]) > len(current["supporting_supportive"]), "more_supportive_markers"
    if len(candidate["parent_path"]) != len(current["parent_path"]):
        return len(candidate["parent_path"]) > len(current["parent_path"]), "more_specific_supported_leaf"
    return candidate["label"] < current["label"], "deterministic_lexical_tie_only"


def _select_primary(candidates, prior_label=""):
    primary = None
    trace = []
    for candidate in candidates:
        replace, reason = _is_more_defensible(candidate, primary, prior_label)
        trace.append({
            "candidate": candidate["label"],
            "compared_with": primary["label"] if primary else "",
            "replace": bool(replace),
            "biological_precedence": reason,
        })
        if replace:
            primary = candidate
    return primary, trace


def _evaluate_states(config, cluster, values, clusters, thresholds, full_ratio, blocked):
    aliases = {
        "S_phase": "Cycling", "G2M_phase": "Cycling", "interferon": "IFN",
        "activation_APC": "Activated", "exhaustion": "Exhausted", "stress": "Stress",
        "hypoxia": "Hypoxia", "emt": "EMT", "angiogenic": "Angiogenic",
        "myofibroblastic": "Myofibroblastic",
    }
    programs = []
    states = []
    for name, genes in config.get("state_panels", {}).items():
        metrics = [
            metric for gene in genes
            if gene.upper() not in blocked
            if (metric := gene_metric(gene, cluster, values, clusters, thresholds, full_ratio)) is not None
        ]
        active = [item for item in metrics if item["review"]]
        strong_active = [item for item in active if item["strong"]]
        rule = config.get("state_program_rules", {}).get(name, {})
        minimum = int(rule.get("minimum_markers", 4 if name == "exhaustion" else 2))
        minimum_strong = int(rule.get("minimum_strong_markers", min(2, minimum)))
        required_any = set(rule.get("required_any", []))
        active_genes = {item["gene"] for item in active}
        passed = len(active) >= minimum and len(strong_active) >= minimum_strong and (not required_any or bool(active_genes & required_any))
        if name == "exhaustion":
            passed = passed and bool(active_genes & {"TOX", "TOX2"}) and len(active_genes & {"PDCD1", "HAVCR2", "TIGIT", "LAG3", "ENTPD1", "CXCL13"}) >= 2
        if name == "myofibroblastic":
            passed = passed and bool(active_genes & {"ACTA2", "TAGLN", "MYL9", "TPM2"}) and bool(active_genes & {"COL1A1", "COL3A1"})
        programs.append({"program": name, "status": _status(passed, assessed=bool(metrics) or full_ratio), "markers": active, "minimum_markers": minimum, "minimum_strong_markers": minimum_strong})
        normalized = aliases.get(name, name)
        if passed and normalized not in states:
            states.append(normalized)
    return programs, states


def _incompatible_complete_programs(primary, candidates):
    if primary is None:
        return []
    rivals = []
    for candidate in candidates:
        if candidate is primary or candidate["program_gate"] != "通过":
            continue
        if candidate["parent_lineage_gate"] == "不通过":
            continue
        if candidate["major_label"] != primary["major_label"]:
            rivals.append(candidate)
            continue
        mutual = candidate.get("mutually_exclusive_audit", {})
        if mutual.get("unresolved_dual_program"):
            rivals.append(candidate)
    return rivals


def _candidate(candidates, label):
    return next((item for item in candidates if item["label"] == label), None)


def _apply_myeloid_boundary_precedence(primary, candidates, boundary_audit):
    """Resolve declared-Myeloid sibling identities through explicit program gates."""
    if not boundary_audit.get("assessed"):
        return primary, ""
    neutrophil = boundary_audit.get("neutrophil_vs_monocyte", {})
    dc_programs = boundary_audit.get("dc_identity_programs", {})
    dc3 = boundary_audit.get("dc3_vs_monocyte", {})

    macrophage_candidates = [
        item for item in candidates
        if item["label"] in {"Macrophage", "Tissue_resident_macrophage"}
        and item["program_gate"] == "通过"
    ]
    if dc3.get("macrophage_competing") and macrophage_candidates:
        selected, _ = _select_primary(macrophage_candidates)
        return selected, "registered_macrophage_exclusion_gate"

    if dc_programs.get("cDC1", {}).get("passed") and _candidate(candidates, "cDC1"):
        return _candidate(candidates, "cDC1"), "registered_cdc1_program_gate"
    if dc_programs.get("Migratory_DC", {}).get("passed") and _candidate(candidates, "Migratory_DC"):
        return _candidate(candidates, "Migratory_DC"), "registered_migratory_dc_program_gate"

    if dc3.get("dc3_boundary_candidate") and _candidate(candidates, "DC3"):
        return _candidate(candidates, "DC3"), "registered_dc3_boundary_gate"
    if dc_programs.get("cDC2", {}).get("passed") and _candidate(candidates, "cDC2"):
        return _candidate(candidates, "cDC2"), "registered_cdc2_program_gate"
    if neutrophil.get("neutrophil_program_passed") and _candidate(candidates, "Neutrophil"):
        return _candidate(candidates, "Neutrophil"), "registered_neutrophil_program_gate"
    if neutrophil.get("monocyte_program_passed"):
        monocytes = [
            item for item in candidates
            if item["label"] in {"Classical_monocyte", "Nonclassical_monocyte"}
        ]
        if monocytes:
            selected, _ = _select_primary(monocytes)
            return selected, "registered_monocyte_program_gate"
    return primary, ""


def _dominant_over(primary, rival):
    if len(primary["strong_core"]) >= len(rival["strong_core"]) + 2:
        return True
    if primary["absolute_program_gate"] == "通过" and rival["absolute_program_gate"] != "通过":
        return True
    mutual = primary.get("mutually_exclusive_audit", {})
    return bool(mutual.get("candidate_dominant"))


def enrich_evidence(
    evidence, ratio_path=None, gene_map_path=None, cell_evidence_path=None,
    config_path=None, annotation_level="subcluster", species="Human", tissue="",
    parent_population="", parent_kind="unknown", knowledge_base_path=None,
    project_major_vocabulary=None, project_label_prior=None,
    require_complete_ratio=False, sample_context=None, user_constraints=None,
):
    if annotation_level not in {"major", "subcluster"}:
        raise ValueError(f"Unsupported annotation level: {annotation_level}")
    config = json.loads(Path(config_path or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    kb = load_knowledge_base(knowledge_base_path)
    config.update(build_runtime_config(
        kb, species=species, tissue=tissue, annotation_level=annotation_level,
        parent_population=parent_population, parent_kind=parent_kind,
    ))
    snapshot = _validate_runtime_snapshot(config, kb)
    config["project_major_vocabulary"] = [str(item).strip() for item in (project_major_vocabulary or []) if str(item).strip()]
    project_prior = {str(key): str(value).strip() for key, value in (project_label_prior or {}).items() if str(value).strip()}
    config["project_label_prior"] = project_prior
    if not config.get("identity_panels"):
        raise ValueError("No approved marker panels remain after species/tissue/parent routing")

    mapping = load_gene_map(gene_map_path)
    clusters = [str(item) for item in evidence["clusters"]]
    expected_genes = evidence.get("average_gene_names", [])
    ratio_values = load_ratio_table(
        ratio_path, clusters, mapping, expected_genes=expected_genes,
        require_complete=bool(require_complete_ratio and ratio_path),
    )
    full_ratio = ratio_values is not None
    values = ratio_values if full_ratio else marker_ratio_table(evidence, mapping)
    constraints = normalize_user_constraints(user_constraints, clusters, mapping)
    cell_evidence = load_cell_evidence(cell_evidence_path)
    thresholds = config["thresholds"]
    decisions = {}

    for cluster in clusters:
        cluster_rules = _cluster_constraints(constraints, cluster)
        candidates = []
        excluded = []
        for label, panel in config["identity_panels"].items():
            candidate = _evaluate_panel(
                label, panel, cluster, values, clusters, thresholds, full_ratio,
                config, set(cluster_rules["conflict_markers"]),
            )
            if _candidate_excluded(label, cluster_rules["exclude_labels"], config):
                excluded.append(candidate)
            else:
                candidates.append(candidate)
        primary, selection_trace = _select_primary(candidates, project_prior.get(cluster, ""))
        if primary is None:
            raise ValueError(f"Cluster {cluster} has no candidate after explicit exclusions")

        boundary_audit = _myeloid_boundary_audit(config, cluster, values, full_ratio, cell_evidence.get(cluster, {}))
        resolved_parent = str(config.get("resolved_parent_id", ""))
        if resolved_parent in {"Myeloid", "Myeloid_cell"} or "Myeloid" in parent_population:
            boundary_primary, boundary_reason = _apply_myeloid_boundary_precedence(primary, candidates, boundary_audit)
            if boundary_reason:
                selection_trace.append({"candidate": boundary_primary["label"], "replace": boundary_primary is not primary, "biological_precedence": boundary_reason})
                primary = boundary_primary

        complete_rivals = _incompatible_complete_programs(primary, candidates)
        unresolved_rivals = [item for item in complete_rivals if not _dominant_over(primary, item)]
        cell_record = cell_evidence.get(cluster, {})
        cell_mixed = bool(cell_record.get("mixed_population_confirmed"))
        resolved_components = [str(item) for item in cell_record.get("resolved_components", []) if str(item).strip()]
        major_identity_first = annotation_level == "major"
        mixed_population = bool(cell_mixed or (unresolved_rivals and not major_identity_first))
        mixed_evidence = bool(unresolved_rivals and major_identity_first)
        suspected_doublet = bool(cell_record.get("doublet_call"))
        possible_components = (
            resolved_components if resolved_components else
            [primary["label"]] + [item["label"] for item in unresolved_rivals]
            if (mixed_population or mixed_evidence) else []
        )
        final_identity = "Multi_cell" if mixed_population else (
            primary["major_label"] if major_identity_first else primary["label"]
        )

        state_programs, state_list = _evaluate_states(
            config, cluster, values, clusters, thresholds, full_ratio,
            set(cluster_rules["conflict_markers"]),
        )
        parent_gate = primary["parent_lineage_gate"]
        off_parent_candidates = [
            item for item in candidates
            if item["parent_lineage_gate"] == "不通过" and item["program_gate"] == "通过"
        ]
        off_parent = bool(primary.get("off_parent_audit") or off_parent_candidates)
        off_parent_gate = "通过" if off_parent and primary["program_gate"] == "通过" else "不适用"
        sibling_gate = "未确定" if unresolved_rivals else "通过"
        mixed_gate = "通过" if mixed_population else "未确定" if mixed_evidence or suspected_doublet else "不适用"
        evidence_gaps = []
        if primary["program_gate"] != "通过":
            evidence_gaps.append("主要身份程序未达到完整通过；需结合缺失锚点、同级排除和文献继续判断")
        if unresolved_rivals:
            evidence_gaps.append("存在无明确优势的完整竞争程序；Cluster 汇总不能证明同一细胞共表达")
        if primary["tissue_scope_match"] is False:
            evidence_gaps.append("候选身份不属于当前知识库的典型组织范围")

        decisions[cluster] = {
            "evidence_mode": "ratio_enhanced" if full_ratio else "minimal",
            "evidence_completeness": "complete_gene_ratio" if full_ratio else "positive_markers_only_missing_is_unknown",
            "stable_id": final_identity,
            "suggested_identity": final_identity,
            "primary_program": primary["label"],
            "primary_major_label": primary["major_label"],
            "competing_programs": [item["label"] for item in candidates if item is not primary and item["program_gate"] == "通过"],
            "excluded_candidate_labels": [item["label"] for item in excluded],
            "qualitative_gates": {
                "identity_anchor": primary["identity_anchor_gate"],
                "parent_lineage": parent_gate,
                "sibling_competition": sibling_gate,
                "exclusion": primary["exclusion_gate"],
                "off_parent": off_parent_gate,
                "state_program": "通过" if state_list else "不适用",
                "umap": "未确定",
                "mixed_doublet": mixed_gate,
            },
            "supporting_markers": primary["supporting_core"] + primary["supporting_supportive"],
            "conflicting_markers": primary["conflicting_markers"],
            "missing_markers": primary["missing_core_markers"],
            "candidate_program_audits": candidates,
            "biological_precedence_trace": selection_trace,
            "identity_boundary_audit": boundary_audit,
            "parent_path": ["Multi_cell"] if mixed_population else primary["parent_path"],
            "expected_parent_id": config.get("resolved_parent_id", ""),
            "off_parent_detected": off_parent,
            "off_parent_audit": primary.get("off_parent_audit", False),
            "off_parent_programs": [item["label"] for item in off_parent_candidates],
            "developmental_stage": "" if mixed_population else primary["developmental_stage"],
            "panel_species": primary["panel_species"],
            "cross_species_inference": primary["cross_species_inference"],
            "marker_panel_evidence_ids": primary["evidence_ids"],
            "state_program": state_programs,
            "state_list": state_list,
            "primary_state": state_list[0] if state_list else "",
            "mixed_population": mixed_population,
            "mixed_evidence": mixed_evidence,
            "suspected_doublet": suspected_doublet,
            "possible_components": possible_components,
            "auto_merge_allowed": not (mixed_population or mixed_evidence or suspected_doublet or off_parent or unresolved_rivals),
            "evidence_gaps": evidence_gaps,
            "recommended_action": (
                "保留同级最可能身份，结合 UMAP、补充 Marker、细胞级共表达或重聚类验证；不得自动删除或合并。"
                if evidence_gaps or mixed_population or mixed_evidence or off_parent
                else "保留该身份并完成全局 UMAP 一致性复核；不得自动修改原始数据。"
            ),
            "decision_rationale": (
                f"{primary['label']} 通过显式身份锚点、分支和排除门控后被保留。"
                if primary["program_gate"] == "通过"
                else f"在现有不完整证据中，{primary['label']} 是按生物学优先级保留的同级最可能身份。"
            ),
        }

    evidence["qualitative_annotation_evidence"] = decisions
    evidence.pop("deterministic_annotation_evidence", None)
    evidence.pop("deterministic_tnk_arbitration", None)
    evidence["annotation_evidence_policy"] = {
        "decision_model": "qualitative_biological_gates",
        "aggregate_identity_scores": False,
        "candidate_ranking_table": False,
        "confidence_grades": False,
        "raw_marker_metrics_preserved": True,
        "core_version": f"{CORE_VERSION}-qualitative",
        "legacy_helper_version": CORE_VERSION,
        "config_version": config.get("config_version", ""),
        "knowledge_base_version": config.get("knowledge_base_version", ""),
        "knowledge_base_source": config.get("knowledge_base_source", ""),
        "species": config.get("species", species),
        "tissue": config.get("tissue", tissue),
        "active_tissue_modules": config.get("active_tissue_modules", []),
        "ontology_parent_map": config.get("ontology_parent_map", {}),
        "evidence_source_registry": config.get("evidence_source_registry", {}),
        "user_constraints": constraints,
        "snapshot": snapshot or _snapshot_metadata(),
        "ratio_input": str(Path(ratio_path).resolve()) if ratio_path else None,
        "ratio_validation": {"provided": bool(ratio_path), "complete_required": bool(require_complete_ratio and ratio_path)},
    }
    evidence["qualitative_tnk_audit"] = {
        "policy": "TCR identity anchors and NK-specific programs are compared through explicit gates; shared cytotoxic genes alone never define NK or NKT.",
        "by_cluster": {
            cluster: {
                "primary_program": decision["primary_program"],
                "competing_programs": decision["competing_programs"],
                "mixed_doublet_gate": decision["qualitative_gates"]["mixed_doublet"],
            }
            for cluster, decision in decisions.items()
        },
    }
    return evidence
