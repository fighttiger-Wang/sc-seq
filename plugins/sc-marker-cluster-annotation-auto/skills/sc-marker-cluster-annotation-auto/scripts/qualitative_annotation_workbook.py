#!/usr/bin/env python3
"""Shared qualitative workbook contract for major and subcluster annotation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from literature_resolver import (
    MARKER_SEPARATOR, NO_DIRECT_LITERATURE, QC_LITERATURE,
    build_7column_literature_rows, is_classic_marker, is_gene_symbol, is_qc_label,
    knowledge_base_core_markers, marker_names,
)
from qualitative_gate_helpers import load_gene_map
from qualitative_umap_resolution import apply_identity_resolution, normalize_relation, validate_identity_resolution


GATE_VALUES = {"通过", "不通过", "未确定", "不适用"}
PLOT_LABEL = re.compile(r"^[A-Za-z0-9_]+$")
INVALID_LABEL = re.compile(r"[^A-Za-z0-9_]+")

SUMMARY_SHEET = "注释结果总览"
AUDIT_SHEET = "质控与深度审计"
COLOR_SHEET = "细胞配色"
LITERATURE_SHEET = "细胞类型与文献"
SOURCE_SHEET = "说明与数据来源"
EXPECTED_SHEETS = [SUMMARY_SHEET, AUDIT_SHEET, COLOR_SHEET, LITERATURE_SHEET, SOURCE_SHEET]

SUMMARY_HEADERS = [
    "Cluster", "中文名称", "Celltype_EN", "大类谱系", "细胞状态",
    "质控结论", "关键 Marker", "核心定量摘要", "UMAP 拓扑位置", "核心判定依据",
]
SUMMARY_FIELDS = [
    "cluster_id", "celltype_cn", "celltype_en", "broad_type", "state",
    "qc_verdict", "key_markers_short", "core_marker_metrics", "umap_summary", "rationale",
]

AUDIT_HEADERS = [
    "Cluster", "中文名称", "Celltype_EN", "质控结论", "定性门控审计",
    "主要竞争候选(Top3)", "完整支持 Marker 定量", "阴性排除验证",
    "异常/边界标记", "可能组成", "证据缺口与复核说明",
]
AUDIT_FIELDS = [
    "cluster_id", "celltype_cn", "celltype_en", "qc_verdict", "gate_audit_summary",
    "candidate_labels", "supporting_marker_evidence", "exclusion_summary",
    "boundary_flags_display", "possible_components", "evidence_gaps",
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

# Styling palette constants (no wrap, fixed compact height)
HEADER_FILL_RGB = "FF1F4E79"
HEADER_FONT_RGB = "FFFFFF"
ZEBRA_FILL_RGB = "FFF7F9FC"
BORDER_GRAY_RGB = "FFE2E8F0"
WARN_FILL_RGB = "FFFDE8E8"
WARN_FONT_RGB = "9C0006"
REVIEW_FILL_RGB = "FFF3F4F6"
REVIEW_FONT_RGB = "374151"
PASS_FILL_RGB = "FFE6F4EA"
PASS_FONT_RGB = "137333"
LEGACY_RED_RGBS = {"FFF8696B", "F8696B", "FFFDE8E8", "FDE8E8"}
SUMMARY_WIDTHS = [10, 22, 26, 16, 18, 11, 30, 40, 28, 44]
AUDIT_WIDTHS = [10, 22, 26, 11, 32, 28, 42, 28, 18, 24, 36]
COLOR_WIDTHS = [26, 14]
LITERATURE_WIDTHS = [26, 32, 40, 22, 32, 42, 44]
SOURCE_WIDTHS = [30, 58]

# Backward-compatibility aliases
PLOT_FIELDS = ["cluster_id", "celltype_en"]
PLOT_HEADERS = ["Cluster", "Celltype_EN"]
ANNO_HEADERS = SUMMARY_HEADERS
ANNO_FIELDS = SUMMARY_FIELDS
RESULT_FIELDS = SUMMARY_FIELDS
RESULT_HEADERS = SUMMARY_HEADERS
EVIDENCE_FIELDS = AUDIT_FIELDS
EVIDENCE_HEADERS = AUDIT_HEADERS


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


def _number_text(value, percent=False, decimals=2):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if percent:
        if abs(number) <= 1.0:
            number *= 100.0
        return f"{number:.{decimals}f}%"
    return f"{number:.{decimals}f}"


def _to_pct_float(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if abs(number) <= 1.0:
        number *= 100.0
    return number


def format_marker_metric(item, compact=False):
    if isinstance(item, str):
        return item.strip()
    gene = str(_metric_value(item, "gene", "Gene", "GeneName") or "").strip()
    if not gene:
        return human_value(item)
    mean = _metric_value(item, "mean_expr", "mean", "Target_Cluster_mean", "avg_expr")
    ratio = _metric_value(item, "expr_ratio", "ratio", "detection_ratio")
    log2fc = _metric_value(item, "log2FC", "avg_log2FC", "avg_logFC")
    pct1 = _metric_value(item, "pct.1", "pct1", "p_in")
    pct2 = _metric_value(item, "pct.2", "pct2", "p_background", "background")

    dec = 1 if compact else 2
    parts = []
    mean_txt = _number_text(mean, percent=False, decimals=dec)
    if mean_txt is not None:
        parts.append(f"mean={mean_txt}")
    fc_txt = _number_text(log2fc, percent=False, decimals=dec)
    if fc_txt is not None:
        parts.append(f"log2FC={fc_txt}")

    r_pct = _to_pct_float(ratio)
    p1_pct = _to_pct_float(pct1)
    p1_eff = pct1 if pct1 not in (None, "") else ratio
    p1_txt = _number_text(p1_eff, percent=True, decimals=dec)
    p2_txt = _number_text(pct2, percent=True, decimals=dec)

    if r_pct is not None and p1_pct is not None and abs(r_pct - p1_pct) > 0.5 and not compact:
        r_txt = _number_text(ratio, percent=True, decimals=dec)
        if r_txt is not None:
            parts.append(f"ratio={r_txt}")
        if p2_txt is not None:
            parts.append(f"pct={_number_text(pct1, True, dec)}/{p2_txt}")
        else:
            parts.append(f"pct.1={_number_text(pct1, True, dec)}")
    elif p1_txt is not None and p2_txt is not None:
        parts.append(f"{p1_txt}/{p2_txt}" if compact else f"pct={p1_txt}/{p2_txt}")
    elif p1_txt is not None:
        parts.append(p1_txt if compact else f"pct={p1_txt}")
    elif p2_txt is not None:
        parts.append(f"bg={p2_txt}" if compact else f"pct.2={p2_txt}")

    return f"{gene}({', '.join(parts)})" if parts else gene


def _gene_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            if isinstance(item, dict):
                items.append(item)
            else:
                items.extend(_gene_list(item))
        return items
    if isinstance(value, dict):
        return [value]
    text = str(value).strip()
    if text.startswith(("[", "{")):
        try:
            return _gene_list(json.loads(text))
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in re.split(r"[,;；、]+", text) if item.strip()]


def _short_key_markers(value, max_genes=6):
    seen = set()
    out = []
    for gene in marker_names(_gene_list(value)):
        key = gene.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(gene)
        if max_genes and len(out) >= max_genes:
            break
    return MARKER_SEPARATOR.join(out)


def _sanitize_plot_markers(records, classic_by_label, evidence, gene_map=None):
    """Return the cluster and cell-type plotting lists using the same marker priorities."""
    matrix_names = set(evidence.get("average_gene_names") or [])
    matrix_lookup = {gene.upper(): gene for gene in evidence.get("average_gene_names") or []}
    reverse_map = defaultdict(set)
    for original, canonical in (gene_map or {}).items():
        if original in matrix_lookup:
            reverse_map[canonical].add(matrix_lookup[original])

    def matrix_gene(gene):
        if not matrix_names:
            return gene if is_gene_symbol(gene) and gene.upper() != "NA" else None
        if gene in matrix_names:
            return gene
        key = gene.upper()
        if key in matrix_lookup:
            return matrix_lookup[key]
        matches = reverse_map.get(key, ())
        return next(iter(matches)) if len(matches) == 1 else None

    def matrix_markers(value):
        return list(dict.fromkeys(match for gene in marker_names(value) if (match := matrix_gene(gene))))

    def format_markers(classic, supporting, top, limit):
        selected = list(dict.fromkeys(classic + supporting))
        if len(selected) < 4:
            selected = list(dict.fromkeys(selected + top))[:4]
        return MARKER_SEPARATOR.join(selected[:limit])

    cluster_indices = {str(cluster): i for i, cluster in enumerate(evidence.get("clusters", []))}
    expressed_by_cluster = defaultdict(set)
    for gene, values in evidence.get("canonical_expression_by_gene", {}).items():
        match = matrix_gene(gene)
        if match:
            for cluster, index in cluster_indices.items():
                if index < len(values) and values[index] is not None and values[index] > 0:
                    expressed_by_cluster[cluster].add(match)

    classic_by_identity = {}
    by_cluster = {}
    by_label = defaultdict(lambda: ([], [], []))
    for record in records:
        cluster = record["cluster_id"]
        label = record["celltype_en"]
        stable = record["stable_id"]
        identity = (label, stable)
        if identity not in classic_by_identity:
            literature = [gene for gene in marker_names(classic_by_label[label]) if is_classic_marker(gene)]
            core = knowledge_base_core_markers(stable) or knowledge_base_core_markers(label)
            classic_by_identity[identity] = matrix_markers(literature + core)

        profile = evidence.get("cluster_profiles", {}).get(cluster, {})
        informative = matrix_markers(profile.get("top_informative_markers"))
        top = informative + matrix_markers(profile.get("top_markers"))
        supporting = matrix_markers(record["key_markers"])
        supported = set(supporting + top) | expressed_by_cluster[cluster]
        classic = [gene for gene in classic_by_identity[identity] if gene in supported]
        by_cluster[cluster] = format_markers(classic, supporting, top, 6)
        for group, genes in zip(by_label[label], (classic, supporting, top)):
            group.extend(genes)

    return by_cluster, {label: format_markers(*groups, 8) for label, groups in by_label.items()}


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


def _marker_evidence(value, evidence, cluster, compact=False, max_genes=None):
    lookup = _marker_lookup(evidence, cluster)
    seen = set()
    rendered = []
    for item in _gene_list(value):
        if isinstance(item, dict):
            gene = str(_metric_value(item, "gene", "Gene", "GeneName") or "").strip()
            key = gene.upper() if gene else repr(item)
            if key in seen:
                continue
            seen.add(key)
            rendered.append(format_marker_metric(item, compact=compact))
        else:
            gene = str(item).strip()
            if not gene:
                continue
            key = gene.upper()
            if key in seen:
                continue
            seen.add(key)
            rendered.append(format_marker_metric(lookup.get(key, gene), compact=compact))
        if max_genes and len(rendered) >= max_genes:
            break
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
    exclusions = _merge_gate_monotonic(d_gates.get("exclusion", "不适用"), r_gates.get("exclusion"), justification)
    exclusions = _merge_gate_monotonic(exclusions, record.get("exclusion_gate"))
    off_parent = _merge_gate_monotonic(d_gates.get("off_parent", "不适用"), r_gates.get("off_parent"), justification)
    off_parent = _merge_gate_monotonic(off_parent, record.get("off_parent_gate"))
    state = _merge_gate_monotonic(d_gates.get("state_program", "不适用"), r_gates.get("state_program"), justification)

    umap_gate = _merge_gate_monotonic(d_gates.get("umap", "未确定"), r_gates.get("umap"), justification)
    relation = normalize_relation(umap.get("marker_umap_relation", ""))
    r_umap_raw = r_gates.get("umap")
    explicit_uncertain = (
        r_umap_raw is not None
        and str(r_umap_raw).strip() != ""
        and _gate(r_umap_raw) == "未确定"
    )
    if relation == "concordant" and umap_gate != "不通过" and not explicit_uncertain:
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


def _active_state_program_text(record, decision):
    r_sp = record.get("state_program")
    if isinstance(r_sp, str) and r_sp.strip():
        return r_sp.strip()
    if isinstance(r_sp, list) and r_sp:
        if all(isinstance(x, dict) for x in r_sp):
            act = [
                str(x.get("program") or "").strip()
                for x in r_sp
                if _gate(x.get("status") or x.get("gate")) == "通过" and str(x.get("program") or "").strip()
            ]
            if act:
                return "；".join(dict.fromkeys(act))
        else:
            vals = [str(x).strip() for x in r_sp if str(x).strip()]
            if vals:
                return "；".join(dict.fromkeys(vals))
    d_sl = decision.get("state_list")
    if isinstance(d_sl, list) and d_sl:
        vals = [str(x).strip() for x in d_sl if str(x).strip()]
        if vals:
            return "；".join(dict.fromkeys(vals))
    elif isinstance(d_sl, str) and d_sl.strip():
        return d_sl.strip()
    d_sp = decision.get("state_program")
    if isinstance(d_sp, list) and d_sp:
        act = [
            str(x.get("program") or "").strip()
            for x in d_sp
            if isinstance(x, dict) and _gate(x.get("status") or x.get("gate")) == "通过" and str(x.get("program") or "").strip()
        ]
        if act:
            return "；".join(dict.fromkeys(act))
    return ""


BOUNDARY_FLAG_LABELS = {
    "none": "正常纯群",
    "normal": "正常纯群",
    "正常纯群": "正常纯群",
    "suspected_doublet": "疑似双细胞",
    "mixed_population": "混合/双细胞群",
    "off_parent_contamination": "跨谱系污染",
    "off_parent_detected": "跨谱系混入",
    "off_parent_reassignment": "跨谱系混入",
    "off_parent": "跨谱系混入",
    "ambient_rna": "背景游离RNA干扰",
    "ambient": "背景游离RNA干扰",
    "background_interference": "背景游离RNA干扰",
    "low_quality": "低质量细胞",
    "debris": "细胞碎片",
    "lineage_boundary": "谱系边界群",
    "abnormal_state": "异常状态",
    "mixed_evidence": "混合特征待复核",
}


def _humanize_boundary_flags(raw_value):
    text = human_value(raw_value)
    if not text:
        return "正常纯群"
    tokens = [tok.strip() for tok in re.split(r"[,;；、|]+", str(text)) if tok.strip()]
    if not tokens:
        return "正常纯群"
    mapped = []
    for tok in tokens:
        low = tok.lower()
        label = BOUNDARY_FLAG_LABELS.get(low)
        if not label:
            for k, v in BOUNDARY_FLAG_LABELS.items():
                if k in low and k not in {"none", "normal"}:
                    label = v
                    break
        mapped.append(label or tok)
    deduped = list(dict.fromkeys(mapped))
    if len(deduped) > 1 and "正常纯群" in deduped:
        deduped = [x for x in deduped if x != "正常纯群"]
    return "；".join(deduped) if deduped else "正常纯群"


def _top_competing_candidates(record, decision, celltype_en, stable, primary_prog, limit=3):
    raw_bflag = str(_first(record, decision, "boundary_flags", "abnormality_flags", "mixture_type") or "").lower()
    is_cross_lineage = (
        str(celltype_en or "").startswith("Multi_cell")
        or record.get("downstream_eligible") is False
        or any(bool(_first(record, decision, k)) for k in (
            "suspected_doublet", "mixed_population", "off_parent_detected", "off_parent_reassignment"
        ))
        or any(k in raw_bflag for k in ("doublet", "off_parent", "mixed_population"))
    )
    self_labels = {
        str(x).strip()
        for x in (celltype_en, normalize_final_label(stable or celltype_en), primary_prog)
        if str(x).strip()
    }
    self_lower = {x.lower() for x in self_labels}
    if str(celltype_en or "").lower() == "plasmacytoid_dc":
        self_lower.add("pdc")

    audits = [item for item in (decision.get("candidate_program_audits") or []) if isinstance(item, dict)]
    off_parent_labels = (
        set() if is_cross_lineage else {
            str(item.get("label", "")).strip()
            for item in audits
            if item.get("within_parent_scope") is False or item.get("off_parent_audit")
        }
    )
    # Require passing gate or multi-gene core evidence (>=2); never pad single-gene hits or unmatched fallbacks.
    audit_evidence = {}
    plausible = []
    for item in audits:
        lbl = str(item.get("label", "")).strip()
        if not lbl:
            continue
        p_gate = _gate(item.get("program_gate"), default="未确定")
        strong_hits = len(item.get("strong_core") or [])
        core_hits = len(item.get("supporting_core") or [])
        anchor_hits = int(item.get("matched_anchor_count", 0) or len(item.get("anchor_hits") or []) or 0)
        evidence_hits = max(strong_hits, core_hits, anchor_hits)
        passed = (p_gate == "通过")
        prev = audit_evidence.get(lbl.lower())
        if prev is None or (passed, evidence_hits) > prev:
            audit_evidence[lbl.lower()] = (passed, evidence_hits)

        is_off = (item.get("within_parent_scope") is False or bool(item.get("off_parent_audit")))
        if is_off and not is_cross_lineage:
            continue
        if passed or evidence_hits >= 2:
            plausible.append((1 if passed else 0, strong_hits, evidence_hits, lbl))
    plausible.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)

    override_comp = (decision.get("research_current_case_override_audit") or {}).get("competing_labels") or []
    raw_comp = _first(record, decision, "competing_programs", "candidate_labels")

    explicit = []
    if isinstance(raw_comp, list):
        explicit.extend(str(x).strip() for x in raw_comp if str(x).strip())
    elif isinstance(raw_comp, str) and raw_comp.strip():
        explicit.extend(str(x).strip() for x in re.split(r"[,;；、/\s]+", raw_comp) if str(x).strip())
    if not explicit:
        for lbl in override_comp:
            cand_s = str(lbl).strip()
            if not cand_s:
                continue
            ov_pass, ov_hits = audit_evidence.get(cand_s.lower(), (False, 0))
            if ov_pass or ov_hits >= 2:
                explicit.append(cand_s)

    combined = explicit + [lbl for _, _, _, lbl in plausible]
    ignore_vals = {"无", "无显著同级竞争", "无明确竞争候选"}
    off_parent_lower = {x.lower() for x in off_parent_labels}
    seen_lower = set()
    filtered = []
    for cand in combined:
        low = cand.lower()
        if low in seen_lower or low in self_lower or low in off_parent_lower or cand in ignore_vals:
            continue
        seen_lower.add(low)
        filtered.append(cand)
        if len(filtered) >= limit:
            break
    return "；".join(filtered) if filtered else "无显著同级竞争"


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
        comp_text = _top_competing_candidates(record, decision, celltype_en, stable, primary_prog, limit=3)

        raw_key_markers = (
            _gene_list(_first(record, decision, "key_markers"))
            + _gene_list(_first(record, decision, "supporting_markers"))
        )
        key_markers = MARKER_SEPARATOR.join(dict.fromkeys(marker_names(raw_key_markers)))
        raw_support_source = _first(record, decision, "supporting_marker_evidence", "supporting_markers", "key_markers")
        raw_excl_source = _first(record, decision, "exclusion_markers", "conflicting_marker_evidence", "conflicting_markers", "negative_marker_conflict")
        excl_formatted = _marker_evidence(raw_excl_source, evidence, cluster, compact=True)
        raw_boundary = human_value(_first(record, decision, "boundary_flags", "abnormality_flags", "interpretation_flags", "mixture_type"))

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
            "key_markers": key_markers,
            "key_markers_short": _short_key_markers(key_markers, max_genes=6),
            "candidate_labels": comp_text,
            "possible_components": human_value(_first(record, decision, "possible_components")),
            "rationale": human_value(_first(record, decision, "rationale", "decision_rationale")),
            "validation_advice": human_value(_first(record, decision, "validation_advice", "review_action", "recommended_action")),
            "handling_advice": human_value(_first(record, decision, "handling_advice", "downstream_handling", "review_action", "recommended_action")),
            "umap_summary": human_value(_first(record, umap, "umap_summary", "topology_summary", "review_action")),
            "boundary_flags": raw_boundary,
            "parent_context": human_value(_first(record, decision, "parent_context", "parent_path", "expected_parent_id")),
            "primary_program": primary_prog,
            "competing_programs": comp_text,
            "supporting_marker_evidence": _marker_evidence(raw_support_source, evidence, cluster, compact=False),
            "core_marker_metrics": _marker_evidence(raw_support_source, evidence, cluster, compact=True, max_genes=3),
            "conflicting_marker_evidence": excl_formatted,
            "missing_markers": human_value(_first(record, decision, "missing_markers", "evidence_gaps")),
            "off_parent_audit": human_value(_first(record, decision, "off_parent_audit", "off_parent_candidate", "tissue_context_review")),
            "developmental_program": human_value(_first(record, decision, "developmental_program", "developmental_stage")),
            "state_program": _active_state_program_text(record, decision),
            "cross_island_audit": human_value(_first(record, umap, "cross_island_audit", "same_label_topology", "separation_explanation", "separation_evidence")),
            "mixed_doublet_explanation": human_value(_first(record, decision, "mixed_doublet_explanation", "mixture_type", "possible_components")),
            "evidence_gaps": human_value(_first(record, decision, "evidence_gaps", "missing_markers")),
        })

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
        if not record.get("candidate_labels"):
            record["candidate_labels"] = record.get("competing_programs") or "无显著同级竞争"
        if not record.get("boundary_flags"):
            record["boundary_flags"] = record.get("off_parent_audit") or "正常纯群"
        record["boundary_flags_display"] = _humanize_boundary_flags(record["boundary_flags"])
        if not record.get("possible_components"):
            record["possible_components"] = record.get("mixed_doublet_explanation") or "纯单核群"
        if not record.get("evidence_gaps"):
            record["evidence_gaps"] = "无"

        record["_decision"] = decision
        record["_umap"] = umap

        # The bundled evidence uses off_parent and mixed_doublet for the
        # cross-lineage and doublet gates when no explicit aliases are supplied.
        off_parent = record["off_parent_gate"]
        exclusion = record["exclusion_gate"]
        cross_lineage = _gate(record.get("cross_lineage_gate"), default=off_parent)
        doublet = _gate(record.get("doublet_gate"), default=record["mixed_doublet_gate"])
        failed_or_uncertain = {"不通过", "未确定"}
        hard_qc_issue = (
            record["celltype_en"].startswith("Multi_cell")
            or any(
                bool(_first(record, decision, key))
                for key in ("suspected_doublet", "mixed_population", "debris", "low_quality", "off_parent_detected")
            )
            or any(
                flag in record["boundary_flags"].lower()
                for flag in ("doublet", "debris", "off_parent", "mixed_population")
            )
            or "不通过" in (off_parent, exclusion, doublet, record["mixed_doublet_gate"])
            or (cross_lineage in failed_or_uncertain and doublet in failed_or_uncertain)
        )
        is_warn = hard_qc_issue or _warning(record)
        record["_is_warning"] = is_warn
        if hard_qc_issue:
            record["qc_verdict"] = "建议过滤"
        elif is_warn:
            record["qc_verdict"] = "复核"
        else:
            record["qc_verdict"] = "保留"

        if excl_formatted and excl_formatted != "无":
            has_conflict = hard_qc_issue or any(
                gate in failed_or_uncertain for gate in (exclusion, off_parent, cross_lineage)
            )
            prefix = "跨谱系冲突" if has_conflict else "已排除"
            record["exclusion_summary"] = f"{prefix}: {excl_formatted}"
        else:
            record["exclusion_summary"] = "无异常冲突"
        record["conflict_missing_markers"] = record["exclusion_summary"]

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


def _source_rows(evidence, annotation_level, records, skill_name, skill_version):
    metadata = evidence.get("confirmed_metadata", {}) or {}
    policy = evidence.get("annotation_evidence_policy", {}) or {}
    raw_paths = (evidence.get("source_paths") or {}).values()
    filenames = [Path(str(v)).name for v in raw_paths if str(v).strip()]
    record_qc_notes = next(
        (human_value(r.get("project_qc_notes")) for r in records if human_value(r.get("project_qc_notes"))),
        "",
    )
    project_qc_notes = (
        human_value(metadata.get("project_qc_notes"))
        or human_value(metadata.get("dataset_background_notes"))
        or record_qc_notes
        or human_value(metadata.get("annotation_constraints"))
        or human_value(policy.get("user_constraints"))
        or "无"
    )
    rows = [
        ["项目名称", metadata.get("project_name", "") or evidence.get("project_name", "") or "单细胞注释分析交付"],
        ["物种 (Species)", metadata.get("species", "")],
        ["组织/器官来源 (Tissue)", metadata.get("tissue", "")],
        ["注释层级与范围 (Level)", annotation_level],
        ["父群背景 (Parent Population)", metadata.get("parent_population", "") or "不适用"],
        ["输入数据源文件 (Input Files)", "；".join(dict.fromkeys(filenames))],
        ["项目共性背景与质控说明", project_qc_notes],
        ["定量指标定义 (Metrics Definition)", "mean=簇内表达均值；log2FC=差异倍数对数；pct=目标簇检出比例/背景群检出比例（缺省指标自动省略，不输出NA）"],
        ["表格结构与标色说明", "Sheet1《注释结果总览》供快速审阅与汇报；Sheet2《质控与深度审计》保留完整门控与定量明细；浅绿底色=保留，浅红底色=疑似双细胞/跨谱系污染/待复核。"],
        ["聚类排列原则 (Cluster Order)", "数值绝对升序结合自然字符顺序（0, 1, 2...）"],
        ["总 Cluster 数量", len(records)],
        ["分析工具与版本 (Skill & Version)", f"{skill_name} v{skill_version}" if skill_version else str(skill_name)],
    ]
    return [[k, v if k == "总 Cluster 数量" else human_value(v)] for k, v in rows]


def _style_sheet(ws, widths, freeze, row_height=24, center_cols=None):
    center_set = set(center_cols or ())
    ws.freeze_panes = freeze
    ws.sheet_view.showGridLines = False
    ws.auto_filter.ref = None
    header_fill = PatternFill("solid", fgColor=HEADER_FILL_RGB)
    zebra_fill = PatternFill("solid", fgColor=ZEBRA_FILL_RGB)
    header_bottom = Side(style="medium", color="163A59")
    thin = Side(style="thin", color=BORDER_GRAY_RGB)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = Font(name="Cambria", size=11, bold=True, color=HEADER_FONT_RGB)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False, shrink_to_fit=False)
        cell.border = Border(bottom=header_bottom)
    ws.row_dimensions[1].height = 26
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        row_idx = row[0].row
        ws.row_dimensions[row_idx].height = row_height
        use_zebra = (row_idx % 2 == 1)
        for cell in row:
            cell.font = Font(name="Cambria", size=11, color="1E293B")
            horiz = "center" if cell.column in center_set else "left"
            cell.alignment = Alignment(horizontal=horiz, vertical="center", wrap_text=False, shrink_to_fit=False)
            if use_zebra:
                cell.fill = zebra_fill
            cell.border = Border(bottom=thin)
    for index, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(index)].width = width


def validate_workbook_content(workbook, average_gene_names=None, *, evidence=None):
    """Validate literature coverage, classic symbols and exact plotting features."""
    if SUMMARY_SHEET not in workbook or LITERATURE_SHEET not in workbook:
        raise ValueError(f"工作簿必须包含 {SUMMARY_SHEET} 和 {LITERATURE_SHEET}")
    summary = workbook[SUMMARY_SHEET]
    literature = workbook[LITERATURE_SHEET]

    summary_headers = [cell.value for cell in summary[1]]
    literature_headers = [cell.value for cell in literature[1]]
    literature_key = LITERATURE_HEADERS[0]
    if "Celltype_EN" not in summary_headers or literature_key not in literature_headers:
        raise ValueError(f"工作簿必须包含 {SUMMARY_SHEET}.Celltype_EN 和 {LITERATURE_SHEET}.{literature_key}")

    summary_col = summary_headers.index("Celltype_EN") + 1
    literature_col = literature_headers.index(literature_key) + 1
    expected = {row[0] for row in summary.iter_rows(min_row=2, min_col=summary_col, max_col=summary_col, values_only=True)}
    matrix_genes = set(average_gene_names or (evidence or {}).get("average_gene_names") or [])

    def check_plot_markers(sheet_name, cell, label):
        if matrix_genes and cell.value not in (None, ""):
            missing = [gene for gene in str(cell.value).split(MARKER_SEPARATOR) if gene not in matrix_genes]
            if missing:
                raise ValueError(f"{sheet_name}!{cell.coordinate}（{label}）的绘图 Marker 与矩阵原名不匹配：{missing}")

    if matrix_genes:
        if "关键 Marker" not in summary_headers:
            raise ValueError(f"工作簿必须包含 {SUMMARY_SHEET}.关键 Marker")
        marker_col = summary_headers.index("关键 Marker") + 1
        for row_index in range(2, summary.max_row + 1):
            label = summary.cell(row_index, summary_col).value
            if not is_qc_label(label):
                check_plot_markers(SUMMARY_SHEET, summary.cell(row_index, marker_col), label)

    labels = Counter()
    for row in literature.iter_rows(min_row=2, max_col=max(7, literature_col)):
        label = row[literature_col - 1].value
        if label is None or not str(label).strip():
            raise ValueError(f"{LITERATURE_SHEET}!{row[literature_col - 1].coordinate} 的 {literature_key} 为空")
        labels[label] += 1
        qc_row = row[1].value == QC_LITERATURE or is_qc_label(label)
        placeholder = bool(re.match(r"^(?:unresolved|unassigned|unannotated)(?:_|$)", str(label), re.I))
        allow_empty_classic = qc_row or placeholder or row[1].value == NO_DIRECT_LITERATURE
        for cell in row[:7]:
            if cell.column == 6 or (cell.column == 5 and allow_empty_classic):
                continue
            if cell.value is None or not str(cell.value).strip():
                raise ValueError(f"{LITERATURE_SHEET}!{cell.coordinate}（{label}）的第 {cell.column} 列为空")
        classic = row[4]
        classic_text = str(classic.value or "").strip()
        if not (qc_row or placeholder) and classic_text and classic_text.upper() != "NA":
            invalid = [gene for gene in classic_text.split(MARKER_SEPARATOR) if not is_classic_marker(gene)]
            if invalid:
                raise ValueError(
                    f"{LITERATURE_SHEET}!{classic.coordinate}（{label}）的第 5 列包含非官方经典基因符号：{invalid}"
                )
        if not qc_row:
            check_plot_markers(LITERATURE_SHEET, row[5], label)

    duplicates = sorted((label for label, count in labels.items() if count > 1), key=str)
    missing = sorted(expected - labels.keys(), key=str)
    extra = sorted(labels.keys() - expected, key=str)
    if duplicates or missing or extra:
        raise ValueError(f"{LITERATURE_SHEET} 标签不匹配：重复 {duplicates}；缺少 {missing}；多余 {extra}")


def build_workbook(records, evidence, output, annotation_level, skill_name, skill_version, umap_audit=None):
    clusters = sorted((str(item) for item in evidence.get("clusters", [])), key=cluster_sort_key)
    records = normalize_records(records, evidence, umap_audit)
    validate(records, clusters, evidence, umap_audit, annotation_level)
    literature_rows = build_7column_literature_rows(records, evidence)
    classic_by_label = {row[0]: row[4] for row in literature_rows}
    gene_map = (
        load_gene_map(evidence.get("source_paths", {}).get("gene_map"))
        if evidence.get("average_gene_names") else None
    )
    cluster_markers, type_markers = _sanitize_plot_markers(records, classic_by_label, evidence, gene_map)

    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = SUMMARY_SHEET
    audit_ws = wb.create_sheet(AUDIT_SHEET)
    colors_ws = wb.create_sheet(COLOR_SHEET)
    literature_ws = wb.create_sheet(LITERATURE_SHEET)
    source_ws = wb.create_sheet(SOURCE_SHEET)

    summary_ws.append(SUMMARY_HEADERS)
    audit_ws.append(AUDIT_HEADERS)
    colors_ws.append(COLOR_HEADERS)
    literature_ws.append(LITERATURE_HEADERS)
    source_ws.append(SOURCE_HEADERS)

    for record in records:
        record["key_markers_short"] = cluster_markers[record["cluster_id"]]
        summary_ws.append([human_value(record.get(field, "")) for field in SUMMARY_FIELDS])
        audit_ws.append([human_value(record.get(field, "")) for field in AUDIT_FIELDS])

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

    for label, locator, citation, study_context, classic, _, rationale, url in literature_rows:
        used = type_markers[label]
        if locator == QC_LITERATURE and not used:
            used = "质控群暂无可绘图标记"
        literature_ws.append([label, locator, citation, study_context, classic, used, rationale])
        if url:
            literature_ws.cell(literature_ws.max_row, 2).hyperlink = url
            literature_ws.cell(literature_ws.max_row, 2).style = "Hyperlink"

    for row in _source_rows(evidence, annotation_level, records, skill_name, skill_version):
        source_ws.append(row)

    _style_sheet(summary_ws, SUMMARY_WIDTHS, "D2", 24, center_cols={1, 4, 6})
    _style_sheet(audit_ws, AUDIT_WIDTHS, "D2", 24, center_cols={1, 4, 9})
    _style_sheet(colors_ws, COLOR_WIDTHS, "A2", 22, center_cols={2})
    _style_sheet(literature_ws, LITERATURE_WIDTHS, "B2", 24, center_cols=set())
    _style_sheet(source_ws, SOURCE_WIDTHS, "A2", 24, center_cols=set())

    link_font = Font(name="Cambria", size=11, color="0563C1", underline="single")
    for r_idx in range(2, literature_ws.max_row + 1):
        link_cell = literature_ws.cell(r_idx, 2)
        if link_cell.hyperlink:
            link_cell.font = link_font

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
                c_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False, shrink_to_fit=False)
            except Exception:
                pass

    qc_colors = {
        "建议过滤": (WARN_FILL_RGB, WARN_FONT_RGB),
        "复核": (REVIEW_FILL_RGB, REVIEW_FONT_RGB),
        "保留": (PASS_FILL_RGB, PASS_FONT_RGB),
    }
    qc_styles = {
        verdict: (
            PatternFill("solid", fgColor=fill_rgb),
            Font(name="Cambria", size=11, bold=True, color=font_rgb),
        )
        for verdict, (fill_rgb, font_rgb) in qc_colors.items()
    }
    for row_index, record in enumerate(records, 2):
        verdict = record["qc_verdict"]
        fill, font = qc_styles[verdict]
        for sheet, qc_column in ((summary_ws, 6), (audit_ws, 4)):
            columns = (qc_column,) if verdict == "保留" else (2, qc_column)
            for column in columns:
                cell = sheet.cell(row_index, column)
                cell.fill = fill
                cell.font = font

    validate_workbook_content(wb, evidence=evidence)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    check = load_workbook(output, read_only=False, data_only=False)
    expected_sheets = list(EXPECTED_SHEETS)
    if check.sheetnames != expected_sheets:
        raise RuntimeError(f"Workbook sheet verification failed: {check.sheetnames}")
    for sheet, headers in (
        (SUMMARY_SHEET, SUMMARY_HEADERS),
        (AUDIT_SHEET, AUDIT_HEADERS),
        (COLOR_SHEET, COLOR_HEADERS),
        (LITERATURE_SHEET, LITERATURE_HEADERS),
        (SOURCE_SHEET, SOURCE_HEADERS),
    ):
        if [cell.value for cell in check[sheet][1]] != headers:
            raise RuntimeError(f"{sheet} header verification failed")
        if check[sheet].auto_filter.ref is not None:
            raise RuntimeError(f"{sheet} must not enable autofilter")
    for sheet in (SUMMARY_SHEET, AUDIT_SHEET):
        order = [str(check[sheet].cell(row, 1).value) for row in range(2, len(records) + 2)]
        if order != clusters:
            raise RuntimeError(f"{sheet} cluster order mismatch: {order} != {clusters}")
    check.close()
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
        "red_fill_column": "中文名称", "red_fill_rgb": WARN_FILL_RGB,
        "auto_filter_enabled": False,
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
