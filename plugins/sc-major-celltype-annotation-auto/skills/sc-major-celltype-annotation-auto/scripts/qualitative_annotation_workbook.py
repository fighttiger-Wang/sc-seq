#!/usr/bin/env python3
"""Shared qualitative workbook contract for major and subcluster annotation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from qualitative_umap_resolution import apply_identity_resolution, normalize_relation, validate_identity_resolution


GATE_VALUES = {"通过", "不通过", "未确定", "不适用"}
PLOT_LABEL = re.compile(r"^[A-Za-z0-9_]+$")
INVALID_LABEL = re.compile(r"[^A-Za-z0-9_]+")

ANNO_HEADERS = [
    "Cluster", "中文名称", "Celltype_EN", "细胞谱系", "发育/成熟阶段",
    "细胞状态", "组织/疾病相关角色", "关键 Marker", "支持 Marker 证据",
    "冲突/缺失 Marker", "主要身份程序", "主要竞争候选", "定性门控审计",
    "UMAP 判断摘要", "异常/边界标记", "可能组成", "判定依据与论证", "证据缺口",
]
ANNO_FIELDS = [
    "cluster_id", "celltype_cn", "celltype_en", "broad_type", "developmental_stage",
    "state", "disease_role", "key_markers", "supporting_marker_evidence",
    "conflict_missing_markers", "primary_program", "candidate_labels",
    "gate_audit_summary", "umap_summary", "boundary_flags", "possible_components",
    "rationale", "evidence_gaps",
]

COLOR_HEADERS = ["细胞类型", "色号"]

LITERATURE_HEADERS = [
    "细胞类型(Celltype_EN)",
    "文献标识 (DOI/PMID)",
    "文献来源与标题",
    "研究物种与组织",
    "权威经典标记 (Classic Markers)",
    "本次鉴定使用的主要 Marker (Sample Evidence)",
    "核心生物学论证与功能定位",
]
SOURCE_HEADERS = ["项目", "内容"]

# Backward-compatibility aliases
PLOT_FIELDS = ["cluster_id", "celltype_en"]
PLOT_HEADERS = ["Cluster", "Celltype_EN"]
RESULT_FIELDS = ANNO_FIELDS
RESULT_HEADERS = ANNO_HEADERS
EVIDENCE_FIELDS = ANNO_FIELDS
EVIDENCE_HEADERS = ANNO_HEADERS


from functools import lru_cache


@lru_cache(maxsize=1)
def _ontology_index():
    path = Path(__file__).resolve().parent / "knowledge-base" / "cell-annotation-knowledge-base.v2.json"
    if not path.is_file():
        path = Path(__file__).resolve().parent.parent / "references" / "cell-annotation-knowledge-base.v2.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}
    nodes = {
        str(item.get("cell_id", "")).strip(): item
        for item in payload.get("ontology", [])
        if str(item.get("cell_id", "")).strip()
    }
    parents = {node_id: str(item.get("parent_id", "")).strip() for node_id, item in nodes.items()}
    return nodes, parents


def _ontology_path(stable_id):
    nodes, parents = _ontology_index()
    stable_id = str(stable_id or "").strip()
    if stable_id not in nodes:
        return []
    path = []
    seen = set()
    current = stable_id
    while current and current not in seen and current in nodes:
        seen.add(current)
        path.append(current)
        current = parents.get(current, "")
    return list(reversed(path))


def validate_taxonomy_depth_consistency(records):
    errors = []
    observed = []
    for record in records:
        cluster = str(record.get("cluster_id", "")).strip()
        stable = normalize_final_label(record.get("stable_id", ""))
        path = _ontology_path(stable)
        if cluster and stable and path:
            observed.append((cluster, stable, path))
    for index, (left_cluster, left_label, left_path) in enumerate(observed):
        for right_cluster, right_label, right_path in observed[index + 1:]:
            if left_label == right_label:
                continue
            if left_label in right_path[:-1]:
                ancestor_cluster, ancestor_label = left_cluster, left_label
                descendant_cluster, descendant_label = right_cluster, right_label
            elif right_label in left_path[:-1]:
                ancestor_cluster, ancestor_label = right_cluster, right_label
                descendant_cluster, descendant_label = left_cluster, left_label
            else:
                continue
            errors.append(
                "Final subcluster mapping co-displays ontology ancestor/descendant labels: "
                f"cluster {ancestor_cluster}={ancestor_label} and cluster "
                f"{descendant_cluster}={descendant_label}. Resolve to same-level "
                "identities, use an approved residual leaf, or block/recluster before delivery."
            )
    return errors


def cluster_sort_key(value):
    text = str(value).strip()
    try:
        number = Decimal(text)
        if number.is_finite():
            return (0, number, text)
    except InvalidOperation:
        pass
    natural = tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"(\d+)", text)
    )
    return (1, natural, text)


def normalize_final_label(value):
    text = INVALID_LABEL.sub("_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        raise ValueError(f"Final plotting label is empty after normalization: {value!r}")
    return text


def _as_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, dict):
        return [value]
    text = str(value).strip()
    if text.startswith(("[", "{")):
        try:
            parsed = json.loads(text)
            return _as_list(parsed)
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in re.split(r"[;,；、]", text) if item.strip()]


def human_value(value):
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return "；".join(
            f"{key}：{human_value(item)}" for key, item in value.items()
            if human_value(item) not in (None, "")
        )
    if isinstance(value, (list, tuple, set)):
        return "；".join(str(human_value(item)) for item in value if human_value(item) not in (None, ""))
    return re.sub(r"\s+", " ", str(value).strip())


def _metric_value(item, *names):
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return None


def _number_text(value, percent=False):
    if value in (None, ""):
        return "NA"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if percent:
        if abs(number) <= 1.0:
            number *= 100.0
        return f"{number:.2f}%"
    return f"{number:.2f}"


def format_marker_metric(item):
    if isinstance(item, str):
        return item.strip()
    gene = str(_metric_value(item, "gene", "Gene", "GeneName") or "").strip()
    if not gene:
        return human_value(item)
    mean = _metric_value(item, "mean_expr", "mean", "Target_Cluster_mean", "avg_expr")
    ratio = _metric_value(item, "expr_ratio", "ratio", "detection_ratio", "p_in", "pct.1", "pct1")
    log2fc = _metric_value(item, "log2FC", "avg_log2FC", "avg_logFC")
    pct1 = _metric_value(item, "pct.1", "pct1", "p_in")
    pct2 = _metric_value(item, "pct.2", "pct2", "p_background", "background")
    return (
        f"{gene}(mean={_number_text(mean)}, ratio={_number_text(ratio, True)}, "
        f"log2FC={_number_text(log2fc)}, pct.1={_number_text(pct1, True)}, "
        f"pct.2={_number_text(pct2, True)})"
    )


def _profile_markers(evidence, cluster):
    profile = evidence.get("cluster_profiles", {}).get(str(cluster), {})
    return profile.get("top_markers", []) or profile.get("top_informative_markers", []) or []


def _marker_lookup(evidence, cluster):
    lookup = {}
    for item in _profile_markers(evidence, cluster):
        if isinstance(item, dict):
            gene = str(_metric_value(item, "gene", "Gene", "GeneName") or "").upper()
            if gene:
                lookup[gene] = item
    return lookup


def _marker_evidence(value, evidence, cluster):
    lookup = _marker_lookup(evidence, cluster)
    rendered = []
    for item in _as_list(value):
        if isinstance(item, dict):
            rendered.append(format_marker_metric(item))
            continue
        gene = str(item).strip()
        rendered.append(format_marker_metric(lookup.get(gene.upper(), gene)))
    return "；".join(item for item in rendered if item)


def _gate(value, default="未确定"):
    if isinstance(value, dict):
        value = value.get("status", value.get("result", value.get("gate", "")))
    if isinstance(value, bool):
        return "通过" if value else "不通过"
    text = str(value or "").strip()
    aliases = {
        "pass": "通过", "passed": "通过", "true": "通过",
        "fail": "不通过", "failed": "不通过", "false": "不通过",
        "unknown": "未确定", "uncertain": "未确定", "not_assessed": "未确定",
        "na": "不适用", "n/a": "不适用", "not_applicable": "不适用",
    }
    result = aliases.get(text.lower(), text)
    return result if result in GATE_VALUES else default


def _decision(evidence, cluster):
    return evidence.get("qualitative_annotation_evidence", {}).get(str(cluster), {})


def _umap_entry(umap_audit, cluster):
    return (umap_audit or {}).get("clusters", {}).get(str(cluster), {})


def _first(record, decision, *keys, default=""):
    for source in (record, decision):
        for key in keys:
            value = source.get(key)
            if value not in (None, "", [], {}):
                return value
    return default


GATE_STRICTNESS = {
    "不通过": 3,
    "未确定": 2,
    "通过": 1,
    "不适用": 0,
}


def _merge_gate_monotonic(baseline: str, candidate: Optional[str], justification: str = "") -> str:
    b_val = _gate(baseline)
    if candidate is None or candidate == "":
        return b_val
    c_val = _gate(candidate)
    b_rank = GATE_STRICTNESS.get(b_val, 0)
    c_rank = GATE_STRICTNESS.get(c_val, 0)
    if c_rank >= b_rank:
        return c_val
    else:
        if justification and str(justification).strip():
            return c_val
        return b_val


def _qualitative_gates(record, decision, umap):
    d_gates = dict(decision.get("qualitative_gates", {}))
    r_gates = dict(record.get("qualitative_gates", {}))
    justification = str(record.get("gate_override_justification") or "").strip()

    identity = _merge_gate_monotonic(d_gates.get("identity_anchor"), r_gates.get("identity_anchor"), justification)

    parent = _merge_gate_monotonic(d_gates.get("parent_lineage", "不适用"), r_gates.get("parent_lineage"), justification)
    siblings = _merge_gate_monotonic(d_gates.get("sibling_competition"), r_gates.get("sibling_competition"), justification)
    exclusions = _merge_gate_monotonic(d_gates.get("exclusion"), r_gates.get("exclusion"), justification)
    off_parent = _merge_gate_monotonic(d_gates.get("off_parent", "不适用"), r_gates.get("off_parent"), justification)
    state = _merge_gate_monotonic(d_gates.get("state_program", "不适用"), r_gates.get("state_program"), justification)

    umap_gate = _merge_gate_monotonic(d_gates.get("umap", "未确定"), r_gates.get("umap"), justification)
    relation = normalize_relation(umap.get("marker_umap_relation", ""))
    if relation == "concordant" and umap_gate != "不通过" and _gate(r_gates.get("umap")) != "未确定":
        umap_gate = "通过"
    elif relation == "conflict":
        umap_gate = "不通过"

    mixed = _merge_gate_monotonic(d_gates.get("mixed_doublet", "不适用"), r_gates.get("mixed_doublet"), justification)
    if any(bool(_first(record, decision, key)) for key in ("mixed_population", "suspected_doublet", "mixed_evidence")):
        if _first(record, decision, "mixed_population") or _first(record, decision, "suspected_doublet"):
            mixed = "不通过"
        else:
            mixed = "未确定"

    return identity, parent, siblings, exclusions, off_parent, state, umap_gate, mixed


def normalize_records(records, evidence, umap_audit=None):
    normalized = []
    for raw in records:
        record = dict(raw)
        cluster = str(record.get("cluster_id", "")).strip()
        decision = _decision(evidence, cluster)
        umap = _umap_entry(umap_audit, cluster)
        if umap:
            apply_identity_resolution(record, umap)
        stable = _first(record, decision, "stable_id", "celltype_en", "display_label")
        celltype_en = normalize_final_label(_first(record, decision, "celltype_en", "display_label", default=stable))
        primary_prog = human_value(_first(record, decision, "primary_program", "research_selected_identity", "primary_evidence_label", "stable_id", default=celltype_en))
        self_labels = {
            str(x).strip()
            for x in (celltype_en, normalize_final_label(stable or celltype_en), primary_prog)
            if str(x).strip()
        }
        off_parent_labels = {
            str(item.get("label", "")).strip()
            for item in (decision.get("candidate_program_audits") or [])
            if isinstance(item, dict) and (item.get("within_parent_scope") is False or item.get("off_parent_audit"))
        }
        override_comp = (decision.get("research_current_case_override_audit") or {}).get("competing_labels") or []
        audit_comp = [
            str(item.get("label", "")).strip()
            for item in (decision.get("candidate_program_audits") or [])
            if isinstance(item, dict)
            and str(item.get("label", "")).strip()
            and item.get("within_parent_scope") is not False
            and not item.get("off_parent_audit")
        ]
        raw_comp = _first(record, decision, "competing_programs", "candidate_labels", "possible_components")
        comp_list = []
        if isinstance(raw_comp, list):
            comp_list.extend(str(x).strip() for x in raw_comp if str(x).strip())
        elif isinstance(raw_comp, str) and raw_comp.strip():
            comp_list.extend(str(x).strip() for x in re.split(r"[,;；、\s]+", raw_comp) if str(x).strip())
        comp_list.extend(str(x).strip() for x in override_comp if str(x).strip())
        comp_list.extend(str(x).strip() for x in audit_comp if str(x).strip())
        filtered_comp = [
            x for x in dict.fromkeys(comp_list)
            if x not in self_labels and x not in off_parent_labels
        ]
        comp_text = "；".join(filtered_comp) if filtered_comp else "无显著同级竞争"

        record.update({
            "cluster_id": cluster,
            "celltype_en": celltype_en,
            "celltype_cn": _first(record, decision, "celltype_cn", default=celltype_en),
            "stable_id": normalize_final_label(stable or celltype_en),
            "lower_level_subtype": human_value(_first(record, decision, "lower_level_subtype", "lower_level_subclass")),
            "broad_type": _first(record, decision, "broad_type", "primary_major_label", "expected_parent_id"),
            "developmental_stage": _first(record, decision, "developmental_stage"),
            "state": _first(record, decision, "state", "primary_state"),
            "disease_role": _first(record, decision, "disease_role"),
            "key_markers": human_value(_first(record, decision, "key_markers", "supporting_markers")),
            "candidate_labels": comp_text,
            "possible_components": human_value(_first(record, decision, "possible_components")),
            "rationale": human_value(_first(record, decision, "rationale", "decision_rationale")),
            "validation_advice": human_value(_first(record, decision, "validation_advice", "review_action", "recommended_action")),
            "handling_advice": human_value(_first(record, decision, "handling_advice", "downstream_handling", "review_action", "recommended_action")),
            "umap_summary": human_value(_first(record, umap, "umap_summary", "topology_summary", "review_action")),
            "boundary_flags": human_value(_first(record, decision, "boundary_flags", "abnormality_flags", "interpretation_flags", "mixture_type")),
            "parent_context": human_value(_first(record, decision, "parent_context", "parent_path", "expected_parent_id")),
            "primary_program": primary_prog,
            "competing_programs": comp_text,
            "supporting_marker_evidence": _marker_evidence(
                _first(record, decision, "supporting_marker_evidence", "supporting_markers"), evidence, cluster
            ),
            "conflicting_marker_evidence": _marker_evidence(
                _first(record, decision, "conflicting_marker_evidence", "conflicting_markers", "negative_marker_conflict"), evidence, cluster
            ),
            "missing_markers": human_value(_first(record, decision, "missing_markers", "evidence_gaps")),
            "off_parent_audit": human_value(_first(record, decision, "off_parent_audit", "off_parent_candidate", "tissue_context_review")),
            "developmental_program": human_value(_first(record, decision, "developmental_program", "developmental_stage")),
            "state_program": human_value(_first(record, decision, "state_program", "state_list")),
            "cross_island_audit": human_value(_first(record, umap, "cross_island_audit", "same_label_topology", "separation_explanation", "separation_evidence")),
            "mixed_doublet_explanation": human_value(_first(record, decision, "mixed_doublet_explanation", "mixture_type", "possible_components")),
            "evidence_gaps": human_value(_first(record, decision, "evidence_gaps", "missing_markers")),
        })
        conflicting_text = _marker_evidence(
            _first(record, decision, "conflicting_marker_evidence", "conflicting_markers", "negative_marker_conflict"), evidence, cluster
        )
        missing_text = human_value(_first(record, decision, "missing_markers", "evidence_gaps"))
        if conflicting_text and missing_text and conflicting_text != "无" and missing_text != "无" and conflicting_text != missing_text:
            conflict_missing = f"冲突: {conflicting_text}；缺失: {missing_text}"
        elif conflicting_text and conflicting_text != "无":
            conflict_missing = conflicting_text
        elif missing_text and missing_text != "无":
            conflict_missing = missing_text
        else:
            conflict_missing = "无"
        record["conflict_missing_markers"] = conflict_missing

        gates = _qualitative_gates(record, decision, umap)
        gate_names = [
            ("锚点", "identity_anchor_gate"),
            ("谱系", "parent_lineage_gate"),
            ("同级竞争", "sibling_competition_gate"),
            ("排除", "exclusion_gate"),
            ("跨谱系", "off_parent_gate"),
            ("状态", "state_gate"),
            ("UMAP", "umap_gate"),
            ("双细胞", "mixed_doublet_gate"),
        ]
        gate_entries = []
        for (g_title, field_name), val in zip(gate_names, gates):
            record[field_name] = val
            if val and val != "不适用":
                gate_entries.append(f"{g_title}[{val}]")
        record["gate_audit_summary"] = ", ".join(gate_entries) if gate_entries else "全部通过"

        if not record.get("broad_type"):
            record["broad_type"] = record.get("parent_context") or "常规谱系"
        if not record.get("developmental_stage"):
            record["developmental_stage"] = record.get("developmental_program") or "成熟/常规"
        if not record.get("state"):
            record["state"] = record.get("state_program") or "常规态"
        if not record.get("disease_role"):
            record["disease_role"] = "常规组织驻留"
        if not record.get("key_markers"):
            record["key_markers"] = record.get("supporting_markers") or ""
        if not record.get("candidate_labels"):
            record["candidate_labels"] = record.get("competing_programs") or "无明确竞争候选"
        if not record.get("boundary_flags"):
            record["boundary_flags"] = record.get("off_parent_audit") or "正常纯群"
        if not record.get("possible_components"):
            record["possible_components"] = record.get("mixed_doublet_explanation") or "纯单核群"
        if not record.get("evidence_gaps"):
            record["evidence_gaps"] = "无"

        record["_decision"] = decision
        record["_umap"] = umap
        normalized.append(record)
    return sorted(normalized, key=lambda item: cluster_sort_key(item["cluster_id"]))


def validate(records, clusters, evidence, umap_audit=None, annotation_level="major"):
    errors = []
    expected = sorted((str(item) for item in clusters), key=cluster_sort_key)
    observed = [str(item.get("cluster_id", "")) for item in records]
    if observed != expected:
        errors.append(f"Cluster order/membership mismatch: expected={expected}, records={observed}")
    if len(set(observed)) != len(observed):
        errors.append("Duplicate cluster IDs are not allowed")
    # Formal subcluster delivery must be bound to the output of the biological
    # gate core. A hand-authored trio of records/evidence/UMAP files can
    # otherwise make an incorrect label look internally consistent.
    if annotation_level == "subcluster":
        policy = evidence.get("annotation_evidence_policy", {}) or {}
        decisions = evidence.get("qualitative_annotation_evidence", {}) or {}
        core_mode = str(policy.get("decision_model", "")).strip()
        if core_mode != "qualitative_biological_gates":
            errors.append(
                "Formal subcluster delivery requires evidence produced by "
                "qualitative_evidence_core (decision_model=qualitative_biological_gates)"
            )
        for cluster in expected:
            decision = decisions.get(str(cluster), {})
            if not isinstance(decision, dict):
                errors.append(f"Cluster {cluster} qualitative core decision is missing or invalid")
                continue
            if not str(decision.get("primary_program", "")).strip():
                errors.append(f"Cluster {cluster} qualitative core decision lacks primary_program")
            if not isinstance(decision.get("candidate_program_audits"), list):
                errors.append(f"Cluster {cluster} qualitative core decision lacks candidate_program_audits")
            matching = next((record for record in records if str(record.get("cluster_id", "")) == cluster), {})
            expected_label = normalize_final_label(decision.get("stable_id", "")) if decision.get("stable_id") else ""
            actual_label = normalize_final_label(matching.get("stable_id", "")) if matching.get("stable_id") else ""
            audit = _umap_entry(umap_audit, cluster)
            reassigned = (
                normalize_relation(audit.get("marker_umap_relation", "")) == "conflict"
                and str(audit.get("identity_action", "")).strip() == "reject_and_reassign"
            )
            if expected_label and actual_label != expected_label and not reassigned:
                errors.append(
                    f"Cluster {cluster} final label {actual_label} is not the qualitative-core "
                    f"decision {expected_label}; only a validated UMAP reassignment may change it"
                )
            if reassigned:
                resolved = normalize_final_label(audit.get("resolved_label", "")) if audit.get("resolved_label") else ""
                candidates = {
                    str(item.get("label", "")).strip()
                    for item in decision.get("candidate_program_audits", [])
                    if isinstance(item, dict) and str(item.get("label", "")).strip()
                }
                if resolved != actual_label:
                    errors.append(f"Cluster {cluster} UMAP resolved_label does not match the final record label")
                if resolved and candidates and resolved not in candidates:
                    errors.append(
                        f"Cluster {cluster} UMAP reassignment {resolved} is absent from qualitative-core candidates"
                    )
    umap_source = str(evidence.get("source_paths", {}).get("umap", "")).strip()
    if umap_source:
        if not isinstance(umap_audit, dict):
            errors.append("Formal delivery has a UMAP source but lacks a cluster-complete UMAP audit")
        else:
            audit_clusters = umap_audit.get("clusters", {})
            missing_audit = sorted(set(expected) - set(map(str, audit_clusters)), key=cluster_sort_key)
            if missing_audit:
                errors.append(f"UMAP audit lacks clusters: {missing_audit}")
            for cluster in expected:
                audit = audit_clusters.get(str(cluster), {})
                if not audit.get("reviewed"):
                    errors.append(f"Cluster {cluster} UMAP audit is not marked reviewed")
                if not str(audit.get("topology_summary", "")).strip():
                    errors.append(f"Cluster {cluster} UMAP audit lacks topology_summary")
                relation = normalize_relation(audit.get("marker_umap_relation", ""))
                audit["marker_umap_relation"] = relation
                if relation not in {"concordant", "conflict", "indeterminate"}:
                    errors.append(f"Cluster {cluster} invalid marker_umap_relation: {relation}")
                matching = next((record for record in records if str(record.get("cluster_id", "")) == cluster), {})
                errors.extend(validate_identity_resolution(
                    audit, matching, evidence=evidence, formal=annotation_level == "subcluster"
                ))
                if relation == "conflict":
                    if audit.get("research_status") not in {"resolved", "reused"}:
                        errors.append(f"Cluster {cluster} unresolved marker/UMAP conflict blocks formal delivery")
                    if audit.get("conflict_resolution_basis") == "literature_only":
                        errors.append(f"Cluster {cluster} sample-specific UMAP conflict cannot be resolved by literature alone")
    for record in records:
        cluster = record.get("cluster_id", "")
        for field in ("celltype_cn", "celltype_en", "rationale"):
            if not str(record.get(field, "")).strip():
                errors.append(f"Cluster {cluster} lacks required qualitative field: {field}")
            if not str(record.get(field, "")).strip():
                errors.append(f"Cluster {cluster} lacks required qualitative field: {field}")
        if not PLOT_LABEL.fullmatch(str(record.get("celltype_en", ""))):
            errors.append(f"Cluster {cluster} Celltype_EN violates [A-Za-z0-9_]+")
        for field in ("identity_anchor_gate", "parent_lineage_gate", "sibling_competition_gate",
                      "exclusion_gate", "off_parent_gate", "state_gate", "umap_gate", "mixed_doublet_gate"):
            if record.get(field) not in GATE_VALUES:
                errors.append(f"Cluster {cluster} invalid qualitative gate {field}: {record.get(field)}")
        if annotation_level == "subcluster":
            parent = str(evidence.get("confirmed_metadata", {}).get("parent_population", "")).strip()
            if parent and record.get("celltype_en") == normalize_final_label(parent):
                errors.append(f"Cluster {cluster} retreats to the supplied parent instead of a sibling/leaf identity")
        errors.extend(validate_taxonomy_depth_consistency(records))
    if annotation_level == "major":
        delivered_labels = {normalize_final_label(record.get("celltype_en", "")) for record in records if record.get("celltype_en")}
        epithelial_parents = {"Epithelial_cell", "Epithelial", "Lung_epithelial", "Airway_epithelial"}
        epithelial_subtypes = {
            "Ciliated_cell", "Ciliated", "Pulmonary_neuroendocrine", "Neuroendocrine_cell",
            "PNEC", "Club_cell", "Basal_cell", "Alveolar_type_1", "Alveolar_type_2",
            "AT1_cell", "AT2_cell", "Ionocyte", "Goblet_cell", "Tuft_cell", "Enterocyte"
        }
        active_parents = delivered_labels & epithelial_parents
        active_subtypes = delivered_labels & epithelial_subtypes
        if active_parents and active_subtypes:
            errors.append(
                f"Hierarchy consistency violation in major delivery: Parent lineage {sorted(active_parents)} "
                f"coexists with sub-lineage {sorted(active_subtypes)} in Celltype_EN. "
                f"In major mode, all intra-lineage clusters must be projected to the common parent label "
                f"(e.g. Epithelial_cell) while preserving specific leaf identities in the 'state' column."
            )
        endo_parents = {"Endothelial_cell", "Endothelial"}
        endo_subtypes = {"Capillary_endothelial", "Arterial_endothelial", "Venous_endothelial", "Tip_cell"}
        if (delivered_labels & endo_parents) and (delivered_labels & endo_subtypes):
            errors.append(
                f"Hierarchy consistency violation in major delivery: Endothelial_cell coexists with sub-types "
                f"{sorted(delivered_labels & endo_subtypes)}. Project to Endothelial_cell and record sub-type in state."
            )
        t_parents = {"T_cell"}
        t_subtypes = {"CD4_T_cell", "CD8_T_cell", "CD8_Tem", "CD8_Tcm", "CD4_Tn", "Treg", "Th17", "CD4_Treg"}
        if (delivered_labels & t_parents) and (delivered_labels & t_subtypes):
            errors.append(
                f"Hierarchy consistency violation in major delivery: T_cell coexists with sub-types "
                f"{sorted(delivered_labels & t_subtypes)}. Project to T_cell and record sub-type in state."
            )
        mac_parents = {"Macrophage"}
        sub_macs = delivered_labels & {"Alveolar_macrophage", "Interstitial_macrophage", "TAM"}
        if (delivered_labels & mac_parents) and sub_macs:
            errors.append(
                f"Hierarchy consistency violation in major delivery: Macrophage coexists with sub-types "
                f"{sorted(sub_macs)}. Project to Macrophage and record sub-type in state."
            )
    if errors:
        raise ValueError("\n".join(errors))


def inject_qualitative_evidence(records, evidence):
    """Enrich records with qualitative decision fields only."""
    normalized = normalize_records(records, evidence)
    records[:] = normalized
    return records


# Temporary import compatibility for historical tests; no deterministic
# evidence is read or generated by this alias.
inject_deterministic_evidence = inject_qualitative_evidence


def _warning(record):
    decision = record.get("_decision", {})
    # 权威终审门控：凡经专家复核为 passed、下游可用且边界状态为 none 的纯群，一律不予警示标红
    status = str(record.get("expert_review_status") or record.get("review_status") or "").strip().lower()
    boundary = str(record.get("boundary_status") or "none").strip().lower()
    downstream = record.get("downstream_eligible")
    if status == "passed" and downstream is True and boundary == "none":
        return False

    if record.get("stable_id") == "Multi_cell" or record.get("celltype_en") == "Multi_cell":
        return True
    if record.get("review_status") == "conditional" or record.get("expert_review_status") == "conditional" or record.get("downstream_eligible") is False:
        return True
    for key in (
        "suspected_doublet", "low_quality", "debris", "background_interference",
        "off_parent_detected", "off_parent_reassignment", "mixed_population",
        "mixed_evidence", "lineage_boundary", "abnormal_state",
    ):
        if bool(_first(record, decision, key)):
            return True
    if str(record.get("off_parent_gate", "")).strip() in {"不通过", "fail", "failed"}:
        return True
    boundary = str(record.get("boundary_flags", "")).lower()
    if any(k in boundary for k in ("off_parent", "ambient", "debris", "doublet")):
        return True
    state_program = decision.get("state_program", [])
    if isinstance(state_program, list):
        return any(
            isinstance(item, dict) and int(item.get("marker_count", 0) or 0) >= 2
            for item in state_program
        )
    return False


def _citation_text(source):
    if isinstance(source, str):
        return source.strip(), ""
    author = source.get("first_author") or source.get("author") or source.get("authors") or ""
    year = source.get("year") or ""
    journal = source.get("journal") or ""
    title = source.get("title") or ""
    pmid = source.get("pmid") or ""
    doi = source.get("doi") or ""
    locator = pmid or doi
    text = ", ".join(str(item) for item in (author, year, journal, title, locator) if item)
    url = source.get("url") or source.get("link") or ""
    if not url and doi:
        url = f"https://doi.org/{str(doi).replace('DOI:', '').strip()}"
    if not url and pmid:
        digits = re.sub(r"\D", "", str(pmid))
        if digits:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{digits}/"
    return text, url


def _literature_rows(records, evidence):
    grouped = {}
    for record in records:
        label = record["celltype_en"]
        entry = grouped.setdefault(label, {"sources": [], "classic": [], "used": []})
        entry["classic"].extend(_as_list(record.get("classic_markers")))
        entry["used"].extend(_as_list(record.get("key_markers")))
        sources = record.get("literature_details") or record.get("literature_source")
        entry["sources"].extend(_as_list(sources))
        if not entry["sources"]:
            decision = record.get("_decision", {})
            source_ids = _as_list(decision.get("marker_panel_evidence_ids"))
            registry = evidence.get("annotation_evidence_policy", {}).get("evidence_source_registry", {})
            entry["sources"].extend(registry.get(item, item) for item in source_ids)
    rows = []
    for label, entry in grouped.items():
        sources = entry["sources"] or ["未提供结构化文献；正式交付前需补充"]
        classic = "；".join(dict.fromkeys(str(item) for item in entry["classic"] if str(item).strip()))
        used = "；".join(dict.fromkeys(str(item) for item in entry["used"] if str(item).strip()))
        for source in sources:
            text, url = _citation_text(source)
            rows.append((label, text, classic, used, url))
    return rows


def _source_rows(evidence, annotation_level, records, skill_name, skill_version):
    metadata = evidence.get("confirmed_metadata", {})
    paths = evidence.get("source_paths", {})
    policy = evidence.get("annotation_evidence_policy", {})
    filenames = [Path(str(value)).name for value in paths.values() if str(value).strip()]
    constraints = metadata.get("annotation_constraints") or policy.get("user_constraints") or "无"

    palette_pool = [
        "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B",
        "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF", "#AEC7E8", "#FFBB78",
        "#98DF8A", "#FF9896", "#C5B0D5", "#C49C94", "#F7B6D2", "#C7C7C7",
        "#DBDB8D", "#9EDAE5", "#393B79", "#5254A3", "#6B6ECF", "#9C9EDE",
        "#637939", "#8CA252", "#B5CF6B", "#CEDB9C", "#8C6D31", "#BD9E39",
    ]
    palette_items = []
    hex_list = []
    for idx, r in enumerate(records):
        cid = str(r.get("cluster_id", idx))
        plot_lbl = r.get("approved_plot_label") or r.get("celltype_plot") or r.get("celltype_en") or f"C{cid}"
        c_hex = palette_pool[idx % len(palette_pool)]
        hex_list.append(c_hex)
        palette_items.append(f"Cluster {cid} ({plot_lbl}): {c_hex}")
    palette_desc = "; ".join(palette_items)
    cols_joined = '", "'.join(hex_list)
    r_code = (
        'library(readxl); library(Seurat); library(ggplot2); '
        'anno <- read_excel("cluster注释信息.xlsx"); '
        'seurat_obj$celltype <- anno$Celltype_EN[match(seurat_obj$seurat_clusters, anno$Cluster)]; '
        f'cols_vector <- c("{cols_joined}"); '
        'DimPlot(seurat_obj, group.by="celltype", cols=cols_vector, label=TRUE, pt.size=0.8) + theme_classic()'
    )

def _source_rows(evidence, annotation_level, records, skill_name, skill_version):
    metadata = evidence.get("confirmed_metadata", {}) or {}
    filenames = evidence.get("source_paths", {}).values()
    return [
        ["项目名称", metadata.get("project_name", "") or evidence.get("project_name", "") or "单细胞注释分析交付"],
        ["物种 (Species)", metadata.get("species", "")],
        ["组织/器官来源 (Tissue)", metadata.get("tissue", "")],
        ["注释层级与范围 (Level)", annotation_level],
        ["父群背景 (Parent Population)", metadata.get("parent_population", "") or "不适用"],
        ["输入数据源文件 (Input Files)", "；".join(dict.fromkeys(filenames))],
        ["定量指标定义 (Metrics Definition)", "mean_expr=簇内表达均值；expr_ratio/pct.1=目标簇检出比例；pct.2=背景群检出比例；log2FC=差异倍数对数"],
        ["聚类排列原则 (Cluster Order)", "数值绝对升序结合自然字符顺序（0, 1, 2...）"],
        ["总 Cluster 数量", len(records)],
        ["分析工具与版本 (Skill & Version)", f"{skill_name} v{skill_version}" if skill_version else str(skill_name)],
    ]


def _style_sheet(ws, widths, freeze, row_height=24):
    ws.freeze_panes = freeze
    ws.sheet_view.showGridLines = False
    ws.auto_filter.ref = None
    header_fill = PatternFill("solid", fgColor="D9E1F2")
    thin = Side(style="thin", color="D9D9D9")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = Font(name="Cambria", size=11, bold=True, color="1F4E79")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False, shrink_to_fit=False)
    ws.row_dimensions[1].height = 26
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        ws.row_dimensions[row[0].row].height = row_height
        for cell in row:
            cell.font = Font(name="Cambria", size=11)
            cell.alignment = Alignment(vertical="top", wrap_text=False, shrink_to_fit=False)
            cell.border = Border(bottom=thin)
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width


def build_workbook(records, evidence, output, annotation_level, skill_name, skill_version, umap_audit=None):
    clusters = sorted((str(item) for item in evidence.get("clusters", [])), key=cluster_sort_key)
    records = normalize_records(records, evidence, umap_audit)
    validate(records, clusters, evidence, umap_audit, annotation_level)

    wb = Workbook()
    anno_ws = wb.active
    anno_ws.title = "注释与详细证据"
    colors_ws = wb.create_sheet("细胞配色")
    literature_ws = wb.create_sheet("细胞类型与文献")
    source_ws = wb.create_sheet("说明与数据来源")

    anno_ws.append(ANNO_HEADERS)
    colors_ws.append(COLOR_HEADERS)
    literature_ws.append(LITERATURE_HEADERS)
    source_ws.append(SOURCE_HEADERS)

    for record in records:
        anno_ws.append([human_value(record.get(field, "")) for field in ANNO_FIELDS])

    palette_pool = [
        "#4DAF4A", "#377EB8", "#E41A1C", "#984EA3", "#FF7F00", "#FFFF33",
        "#A65628", "#F781BF", "#999999", "#66C2A5", "#FC8D62", "#8DA0CB",
        "#E78AC3", "#A6D854", "#FFD92F", "#E5C494", "#B3B3B3", "#1B9E77",
        "#D95F02", "#7570B3", "#E7298A", "#66A61E", "#E6AB02", "#A6761D",
        "#666666", "#1F77B4", "#AEC7E8", "#FF7F0E", "#FFBB78", "#2CA02C",
        "#98DF8A", "#D62728", "#FF9896", "#9467BD", "#C5B0D5", "#8C564B",
        "#C49C94", "#E377C2", "#F7B6D2", "#7F7F7F", "#C7C7C7", "#BCBD22",
    ]
    seen_types = []
    for r in records:
        ct = r.get("celltype_en")
        if ct and ct not in seen_types:
            seen_types.append(ct)

    for idx, ctype in enumerate(seen_types):
        c_hex = palette_pool[idx % len(palette_pool)]
        colors_ws.append([ctype, c_hex])

    try:
        from literature_resolver import build_7column_literature_rows
        lit_rows = build_7column_literature_rows(records, evidence)
        for label, locator, citation, study_context, classic, used, rationale, url in lit_rows:
            literature_ws.append([label, locator, citation, study_context, classic, used, rationale])
            if url:
                literature_ws.cell(literature_ws.max_row, 2).hyperlink = url
                literature_ws.cell(literature_ws.max_row, 2).style = "Hyperlink"
    except Exception:
        for label, citation, classic, used, url in _literature_rows(records, evidence):
            literature_ws.append([label, citation, "", "", classic, used, ""])
            if url:
                literature_ws.cell(literature_ws.max_row, 2).hyperlink = url
                literature_ws.cell(literature_ws.max_row, 2).style = "Hyperlink"

    for r_idx in range(2, literature_ws.max_row + 1):
        for c_idx in range(1, 7):
            cell_val = str(literature_ws.cell(r_idx, c_idx).value or "").strip()
            if not cell_val:
                header_name = literature_ws.cell(1, c_idx).value
                row_label = literature_ws.cell(r_idx, 1).value
                raise ValueError(
                    f"Sheet '细胞类型与文献' cell {row_label} col {c_idx} ('{header_name}') must not be empty"
                )
        c7_val = str(literature_ws.cell(r_idx, 7).value or "").strip()
        if not c7_val:
            literature_ws.cell(r_idx, 7, value="依据样本高变与差异 Marker 特异性富集特征独立确立。")

    for row in _source_rows(evidence, annotation_level, records, skill_name, skill_version):
        source_ws.append(row)

    _style_sheet(anno_ws, [10, 22, 22, 18, 18, 18, 22, 28, 48, 36, 28, 28, 38, 36, 20, 28, 44, 28], "D2", 24)
    _style_sheet(colors_ws, [28, 18], "A2", 22)
    _style_sheet(literature_ws, [26, 36, 55, 22, 38, 50, 68], "B2", 24)
    _style_sheet(source_ws, [30, 88], "A2", 24)

    for row_idx in range(2, colors_ws.max_row + 1):
        cell_hex = str(colors_ws.cell(row_idx, 2).value or "").strip()
        if re.match(r"^#[0-9A-Fa-f]{6}$", cell_hex):
            clean_hex = cell_hex.lstrip("#").upper()
            try:
                r_val = int(clean_hex[0:2], 16)
                g_val = int(clean_hex[2:4], 16)
                b_val = int(clean_hex[4:6], 16)
                lum = 0.299 * r_val + 0.587 * g_val + 0.114 * b_val
                font_c = "000000" if lum > 140 else "FFFFFF"
                color_fill = PatternFill(start_color=f"FF{clean_hex}", end_color=f"FF{clean_hex}", fill_type="solid")
                c_cell = colors_ws.cell(row_idx, 2)
                c_cell.fill = color_fill
                c_cell.font = Font(name="Cambria", size=11, bold=True, color=font_c)
                c_cell.alignment = Alignment(horizontal="center", vertical="center")
            except Exception:
                pass

    red_fill = PatternFill("solid", fgColor="FFF8696B")
    for row_index, record in enumerate(records, 2):
        if _warning(record):
            anno_ws.cell(row_index, 2).fill = red_fill

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    check = load_workbook(output, read_only=False, data_only=False)
    expected_sheets = ["注释与详细证据", "细胞配色", "细胞类型与文献", "说明与数据来源"]
    if check.sheetnames != expected_sheets:
        raise RuntimeError(f"Workbook sheet verification failed: {check.sheetnames}")
    for sheet, headers in (
        ("注释与详细证据", ANNO_HEADERS),
        ("细胞配色", COLOR_HEADERS),
        ("细胞类型与文献", LITERATURE_HEADERS),
        ("说明与数据来源", SOURCE_HEADERS),
    ):
        if [cell.value for cell in check[sheet][1]] != headers:
            raise RuntimeError(f"{sheet} header verification failed")
        if check[sheet].auto_filter.ref is not None:
            raise RuntimeError(f"{sheet} must not enable autofilter")
    for sheet in ("注释与详细证据",):
        order = [str(check[sheet].cell(row, 1).value) for row in range(2, len(records) + 2)]
        if order != clusters:
            raise RuntimeError(f"{sheet} cluster order mismatch: {order} != {clusters}")
    deprecated = sorted({key for record in records for key in record if key in {
        "confidence", "quality_score", "primary_evidence_score", "runner_up_evidence_score",
        "score_margin", "rival_lineage_score", "ranked_identity_evidence"
    }})
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "status": "pass", "workbook": str(output), "sheets": expected_sheets,
        "workbook_sha256": digest,
        "record_count": len(records), "cluster_order": clusters,
        "cluster_order_policy": "numeric_ascending_then_natural_alphanumeric",
        "qualitative_gate_values": sorted(GATE_VALUES), "aggregate_scores_exported": False,
        "confidence_exported": False, "deprecated_input_fields_ignored": deprecated,
        "red_fill_column": "中文名称", "auto_filter_enabled": False,
        "fixed_row_height": True, "wrap_text": False, "shrink_to_fit": False,
        "source_files_unchanged": True,
    }


def resolved_e(path, role):
    resolved = Path(path).resolve()
    if platform.system() == "Windows" and os.path.splitdrive(str(resolved))[0].upper() != "E:":
        raise ValueError(f"{role} must be on E: {resolved}")
    return resolved


def within(path, root, role):
    path, root = Path(path).resolve(), Path(root).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{role} must be inside workspace root {root}: {path}") from exc
    return path


def cli_main(annotation_level, skill_name, skill_version):
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--umap-audit")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    workspace = resolved_e(args.workspace_root, "workspace root")
    records_path = within(resolved_e(args.records, "records"), workspace, "records")
    evidence_path = within(resolved_e(args.evidence, "evidence"), workspace, "evidence")
    output = within(resolved_e(args.output, "workbook output"), workspace, "workbook output")
    if output.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing workbook without --force: {output}")
    umap_audit = None
    if args.umap_audit:
        audit_path = within(resolved_e(args.umap_audit, "UMAP audit"), workspace, "UMAP audit")
        umap_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    qa = build_workbook(records, evidence, output, annotation_level, skill_name, skill_version, umap_audit)
    output.with_suffix(".qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False))
