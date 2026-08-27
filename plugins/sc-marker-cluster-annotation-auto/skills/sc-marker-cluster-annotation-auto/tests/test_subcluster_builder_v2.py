#!/usr/bin/env python3
"""Regression test for repeated canonical labels and structured v2 fields."""

import argparse
import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from annotation_evidence_core import enrich_evidence  # noqa: E402
from build_annotation_workbook import hierarchy_depth_conflicts, inject_deterministic_evidence, validate  # noqa: E402
from umap_audit import apply_umap_audit, validate_umap_audit  # noqa: E402


PROGRAMS = {
    "0": ["CD3D", "CD3E", "TRAC", "GZMK", "CCL5", "CD8A", "IL7R", "TOX", "PDCD1", "LAG3", "HAVCR2", "TIGIT", "ENTPD1"],
    "1": ["CD3D", "CD3E", "TRAC", "GZMK", "CCL5", "CD8A", "CXCR3"],
    "2": ["CD3D", "CD3E", "TRAC", "CD4", "FOXP3", "IL2RA", "CTLA4", "TIGIT"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    input_dir = work / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    source_paths = {}
    for key, name in {
        "cell_avg_exp": "cell_avg_exp.tsv",
        "marker_table": "marker_table.tsv",
        "umap": "umap.png",
    }.items():
        path = input_dir / name
        path.write_text("test\n", encoding="utf-8")
        source_paths[key] = str(path)
    genes = sorted({gene for values in PROGRAMS.values() for gene in values} | {"CCR7", "SELL", "TCF7", "LEF1", "GZMB", "PRF1", "NKG7"})
    ratio = work / "ratios.tsv"
    with ratio.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "group", "expr_ratio"])
        for cluster, active in PROGRAMS.items():
            for gene in genes:
                writer.writerow([gene, cluster, 0.8 if gene in active else 0.01])
    evidence = {
        "clusters": list(PROGRAMS),
        "cluster_profiles": {
            cluster: {
                "top_markers": [], "qc_state_fraction_top50": 0.0,
                "naming_top_marker": {"gene": active[0]}, "raw_top_marker": {"gene": active[0]},
                "top_informative_markers": [{"gene": gene} for gene in active], "excluded_naming_markers": [],
            }
            for cluster, active in PROGRAMS.items()
        },
        "average_shape": [len(genes), len(PROGRAMS)], "average_reader": "test",
        "confirmed_metadata": {"species": "Human", "tissue": "blood", "annotation_level": "subcluster", "parent_population": "T_cell", "parent_kind": "lineage", "interpretation_rule": "test"},
        "source_paths": source_paths,
    }
    evidence = enrich_evidence(
        evidence, ratio_path=ratio, annotation_level="subcluster", species="Human", tissue="blood",
        parent_population="T_cell", parent_kind="lineage",
    )
    assert evidence["deterministic_annotation_evidence"]["0"]["stable_id"] == "CD8_Tem"
    assert evidence["deterministic_annotation_evidence"]["1"]["stable_id"] == "CD8_Tem"
    records = []
    for cluster in PROGRAMS:
        decision = evidence["deterministic_annotation_evidence"][cluster]
        label = decision["stable_id"]
        display = decision["display_label"]
        records.append({
            "cluster_id": cluster, "celltype_cn": display, "celltype_en": display,
            "label_basis": "canonical_subtype", "canonical_subtype": label,
            "top_marker_gene": PROGRAMS[cluster][0], "literature_source": "approved knowledge base",
            "naming_grammar": "state_first_v2", "contextually_excluded_naming_markers": [],
            "broad_type": "T_cell", "fine_type": label, "state": "",
            "supporting_markers": ";".join(PROGRAMS[cluster]), "conflicting_markers": "",
            "candidate_labels": label, "confidence": "medium-high", "quality_score": 82,
            "mixed_or_doublet": False, "mixture_type": "none", "possible_components": "",
            "rationale": "Approved node-specific Marker program.",
            "manual_review": decision["risk_level"] != "R0_ACCEPT", "review_action": decision["recommended_action"],
        })
    evidence_path = work / "evidence.json"
    records_path = work / "records.json"
    umap_audit_path = work / "umap_review.json"
    output = work / "subcluster_v2.xlsx"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    umap_audit = {
        "source_image": "umap.png",
        "method": "visual_cluster_topology_review",
        "clusters": {
            cluster: {
                "reviewed": True,
                "topology_summary": f"Cluster {cluster} topology reviewed",
                "nearest_clusters": [item for item in PROGRAMS if item != cluster][:1],
                "marker_umap_relation": "concordant",
                "conflict_reason": "",
                "research_required": False,
                "research_status": "not_required",
                "evidence_ids": [],
                "review_action": "retain marker-supported identity",
                "same_label_clusters": (
                    [item for item in PROGRAMS if item != cluster and item in {"0", "1"}]
                    if cluster in {"0", "1"} else []
                ),
                "same_label_topology": "adjacent" if cluster in {"0", "1"} else "not_applicable",
                "separation_explanation": "none",
                "separation_evidence": "",
            }
            for cluster in PROGRAMS
        },
    }
    umap_audit_path.write_text(json.dumps(umap_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    completed = subprocess.run([
        sys.executable, str(SKILL / "scripts" / "build_annotation_workbook.py"),
        "--records", str(records_path), "--evidence", str(evidence_path),
        "--umap-audit", str(umap_audit_path),
        "--output", str(output), "--workspace-root", str(work.parents[1]), "--force",
    ], text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    qa = json.loads(output.with_suffix(".qa.json").read_text(encoding="utf-8"))
    assert qa["status"] == "pass"
    assert qa["hierarchy_depth_conflicts"] == []
    assert qa["umap_all_clusters_reviewed"] is True
    assert qa["umap_conflict_clusters"] == []
    workbook = load_workbook(output, data_only=False)
    assert workbook.sheetnames == ["注释结果", "详细证据", "说明与数据来源"]
    assert "简化映射" not in workbook.sheetnames
    for sheet in workbook.worksheets:
        assert sheet.auto_filter.ref is None
    result = workbook["注释结果"]
    headers = {cell.value: cell.column for cell in result[1]}
    assert result.cell(2, headers["Celltype_EN"]).value == "CD8_Tem"
    assert result.cell(2, headers["细胞状态"]).value == "Exhausted"
    assert isinstance(result.cell(2, headers["质量评分"]).value, (int, float))
    celltype_cn_col = get_column_letter(headers["中文名称"])
    quality_col = get_column_letter(headers["质量评分"])
    celltype_cn_range = f"{celltype_cn_col}2:{celltype_cn_col}{result.max_row}"
    low_quality_name_rules = [
        rule
        for conditional_formatting, rules in result.conditional_formatting._cf_rules.items()
        if str(conditional_formatting.sqref) == celltype_cn_range
        for rule in rules
    ]
    assert len(low_quality_name_rules) == 1
    assert low_quality_name_rules[0].formula == [
        f"${quality_col}2=MIN(${quality_col}$2:${quality_col}${result.max_row})"
    ]
    assert low_quality_name_rules[0].dxf.fill.fgColor.rgb == "00F8696B"
    assert max((row.height or 15) for row in result.row_dimensions.values()) <= 54
    main_values = [cell.value for row in result.iter_rows() for cell in row]
    assert not any(isinstance(value, str) and value.lstrip().startswith(("{", "[")) for value in main_values)
    assert not any(isinstance(value, str) and ":\\" in value for value in main_values)
    assert records[0]["celltype_en"] == records[1]["celltype_en"]
    conflict = hierarchy_depth_conflicts([
        {"stable_id": "Mature_B", "parent_path": ["Cell", "Immune_cell", "B_cell", "Mature_B"]},
        {"stable_id": "Naive_B", "parent_path": ["Cell", "Immune_cell", "B_cell", "Mature_B", "Naive_B"]},
    ])
    assert conflict == [{"ancestor": "Mature_B", "descendant": "Naive_B"}]
    mixed_parent_fallback = hierarchy_depth_conflicts([
        {
            "stable_id": "T_cell", "parent_path": ["Cell", "Immune_cell", "T_NK_lineage", "T_cell"],
            "formal_identity_fallback": "mixed_incompatible_sublineages",
            "mixed_population": True, "auto_merge_allowed": False,
        },
        {"stable_id": "CD4_Tn", "parent_path": ["Cell", "Immune_cell", "T_NK_lineage", "T_cell", "CD4_T", "CD4_Tn"]},
    ])
    assert mixed_parent_fallback == []
    off_parent_mixed_fallback = hierarchy_depth_conflicts([
        {
            "stable_id": "T_NK_lineage", "parent_path": ["Cell", "Immune_cell", "T_NK_lineage"],
            "formal_identity_fallback": "mixed_parent_off_parent_lineages",
            "mixed_population": True, "auto_merge_allowed": False,
        },
        {"stable_id": "CD4_Tn", "parent_path": ["Cell", "Immune_cell", "T_NK_lineage", "T_cell", "CD4_T", "CD4_Tn"]},
    ])
    assert off_parent_mixed_fallback == []
    evidence_limited_branch = hierarchy_depth_conflicts([
        {
            "stable_id": "CD4_T", "parent_path": ["Cell", "Immune_cell", "T_NK_lineage", "T_cell", "CD4_T"],
            "formal_identity_fallback": "branch_identity_no_supported_leaf", "manual_review": True,
        },
        {"stable_id": "CD4_Tn", "parent_path": ["Cell", "Immune_cell", "T_NK_lineage", "T_cell", "CD4_T", "CD4_Tn"]},
    ])
    assert evidence_limited_branch == [{"ancestor": "CD4_T", "descendant": "CD4_Tn"}]
    confirmed_parent_records = copy.deepcopy(records)
    inject_deterministic_evidence(confirmed_parent_records, evidence)
    confirmed_parent_records[0].update({
        "stable_id": "B_cell",
        "canonical_subtype": "B_cell",
        "display_label": "B_cell",
        "celltype_en": "B_cell",
        "celltype_cn": "B_cell",
        "fine_type": "B_cell",
        "parent_path": ["Cell", "Immune_cell", "B_cell"],
        "formal_identity_fallback": "confirmed_parent",
        "label_basis": "canonical_subtype",
    })
    evidence_with_confirmed_parent = copy.deepcopy(evidence)
    evidence_with_confirmed_parent["deterministic_annotation_evidence"][str(confirmed_parent_records[0]["cluster_id"])]["resolution_search_required"] = True
    evidence_with_confirmed_parent["deterministic_annotation_evidence"][str(confirmed_parent_records[0]["cluster_id"])]["formal_identity_fallback"] = "confirmed_parent"
    evidence_with_confirmed_parent["deterministic_annotation_evidence"][str(confirmed_parent_records[0]["cluster_id"])]["stable_id"] = "B_cell"
    try:
        validate(confirmed_parent_records, list(PROGRAMS), evidence_with_confirmed_parent)
    except ValueError as exc:
        assert "temporary confirmed-parent mapping cannot be published" in str(exc)
        assert "formal_identity_fallback=confirmed_parent" in str(exc)
    else:
        raise AssertionError("Builder QA must reject unresolved confirmed-parent records")
    inconsistent_depth_records = copy.deepcopy(records)
    inject_deterministic_evidence(inconsistent_depth_records, evidence)
    unresolved = inconsistent_depth_records[0]
    unresolved.update({
        "stable_id": "CD4_T",
        "display_label": "CD4_T",
        "celltype_en": "CD4_T",
        "celltype_cn": "CD4_T",
        "fine_type": "CD4_T",
        "canonical_subtype": "CD4_T",
        "formal_identity_fallback": "branch_identity_no_supported_leaf",
        "parent_path": json.dumps(["Cell", "Immune_cell", "T_NK_lineage", "T_cell", "CD4_T"]),
        "label_basis": "researched_branch_fallback",
        "literature_source": "source-one;source-two",
        "candidate_labels": "CD4_Tn;CD4_Treg",
        "conflicting_markers": "No coherent leaf after targeted review",
        "confidence": "medium",
        "manual_review": True,
    })
    descendant = inconsistent_depth_records[2]
    descendant.update({
        "stable_id": "CD4_Treg",
        "display_label": "CD4_Treg",
        "celltype_en": "CD4_Treg",
        "celltype_cn": "CD4_Treg",
        "fine_type": "CD4_Treg",
        "canonical_subtype": "CD4_Treg",
        "parent_path": json.dumps(["Cell", "Immune_cell", "T_NK_lineage", "T_cell", "CD4_T", "CD4_Treg"]),
    })
    try:
        validate(inconsistent_depth_records, list(PROGRAMS), evidence)
    except ValueError as exc:
        assert "mandatory resolution-search pass" in str(exc)
        assert '"ancestor": "CD4_T"' in str(exc)
    else:
        raise AssertionError("Builder QA must reject CD4_T together with CD4_Treg")
    invalid_records = copy.deepcopy(records)
    inject_deterministic_evidence(invalid_records, evidence)
    invalid_records[0]["stable_id"] = "CD8_Tex"
    invalid_records[0]["canonical_subtype"] = "CD8_Tex"
    invalid_records[0]["display_label"] = "Exhausted_CD8_Tex"
    invalid_records[0]["celltype_en"] = "Exhausted_CD8_Tex"
    try:
        validate(invalid_records, list(PROGRAMS), evidence)
    except ValueError as exc:
        assert "deprecated identity/state boundary" in str(exc)
        assert "repeats exhaustion semantics" in str(exc)
    else:
        raise AssertionError("Builder QA must reject deprecated Tex identities and redundant labels")
    incomplete_audit = copy.deepcopy(umap_audit)
    incomplete_audit["clusters"].pop("2")
    try:
        validate_umap_audit(incomplete_audit, list(PROGRAMS), formal=False)
    except ValueError as exc:
        assert "Missing UMAP audit clusters" in str(exc)
    else:
        raise AssertionError("UMAP audit must cover every cluster")
    pending_audit = copy.deepcopy(umap_audit)
    pending_audit["clusters"]["1"].update({
        "marker_umap_relation": "conflict",
        "conflict_reason": "separated topology despite interwoven marker programs",
        "research_required": True,
        "research_status": "pending",
    })
    validate_umap_audit(pending_audit, list(PROGRAMS), formal=False)
    try:
        validate_umap_audit(pending_audit, list(PROGRAMS), formal=True)
    except ValueError as exc:
        assert "not resolved or reused" in str(exc)
    else:
        raise AssertionError("Formal delivery must block unresolved marker/UMAP conflict")
    literature_only_audit = copy.deepcopy(umap_audit)
    literature_only_audit["clusters"]["1"].update({
        "marker_umap_relation": "conflict",
        "conflict_reason": "detached topology",
        "research_required": True,
        "research_status": "resolved",
        "evidence_ids": ["PMID:literature"],
        "conflict_resolution_basis": "literature_only",
    })
    try:
        validate_umap_audit(literature_only_audit, list(PROGRAMS), formal=True)
    except ValueError as exc:
        assert "cannot be resolved by literature alone" in str(exc)
    else:
        raise AssertionError("Literature alone must not resolve a sample-specific marker/UMAP conflict")
    cell_resolved_audit = copy.deepcopy(literature_only_audit)
    cell_resolved_audit["clusters"]["1"]["conflict_resolution_basis"] = "cell_level_coexpression"
    validate_umap_audit(cell_resolved_audit, list(PROGRAMS), formal=True)
    disconnected_state_records = copy.deepcopy(records)
    inject_deterministic_evidence(disconnected_state_records, evidence)
    disconnected_state_records[0]["state_list"] = ["Cycling"]
    disconnected_state_audit = copy.deepcopy(umap_audit)
    for cluster in ("0", "1"):
        disconnected_state_audit["clusters"][cluster].update({
            "same_label_topology": "disconnected",
            "separation_explanation": "state_dominant",
            "separation_evidence": "Cluster 0 has a dominant Cycling program that separates it from cluster 1.",
        })
    validate_umap_audit(
        disconnected_state_audit, list(PROGRAMS), formal=True, records=disconnected_state_records
    )
    validated_disconnected = validate_umap_audit(
        disconnected_state_audit, list(PROGRAMS), formal=True, records=disconnected_state_records
    )
    apply_umap_audit(disconnected_state_records, validated_disconnected)
    assert disconnected_state_records[0]["auto_merge_allowed"] is False
    assert disconnected_state_records[1]["auto_merge_allowed"] is False
    unexplained_disconnected = copy.deepcopy(disconnected_state_audit)
    for cluster in ("0", "1"):
        unexplained_disconnected["clusters"][cluster].update({
            "marker_umap_relation": "concordant",
            "research_required": False,
            "research_status": "not_required",
            "separation_explanation": "none",
            "separation_evidence": "",
        })
    try:
        validate_umap_audit(
            unexplained_disconnected, list(PROGRAMS), formal=True, records=disconnected_state_records
        )
    except ValueError as exc:
        assert "disconnected same-label island without explanation" in str(exc)
    else:
        raise AssertionError("Unexplained disconnected same-label islands must block formal QA")
    interim = work / "temporary_mapping.tsv"
    completed = subprocess.run([
        sys.executable, str(SKILL / "scripts" / "build_interim_mapping.py"),
        "--records", str(records_path), "--evidence", str(evidence_path),
        "--umap-audit", str(umap_audit_path), "--output", str(interim),
        "--workspace-root", str(work.parents[1]), "--force",
    ], text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    with interim.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    assert rows[0] == ["cluster", "suggested_cell_type"]
    assert len(rows) == len(PROGRAMS) + 1
    no_umap_evidence = copy.deepcopy(evidence)
    no_umap_evidence["source_paths"]["umap"] = ""
    no_umap_evidence_path = work / "evidence_without_umap.json"
    no_umap_evidence_path.write_text(json.dumps(no_umap_evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    no_umap_interim = work / "temporary_mapping_without_umap.tsv"
    completed = subprocess.run([
        sys.executable, str(SKILL / "scripts" / "build_interim_mapping.py"),
        "--records", str(records_path), "--evidence", str(no_umap_evidence_path),
        "--output", str(no_umap_interim), "--workspace-root", str(work.parents[1]), "--force",
    ], text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    no_umap_qa = json.loads(no_umap_interim.with_suffix(".tsv.qa.json").read_text(encoding="utf-8"))
    assert no_umap_qa["reason"] == "missing_umap"
    blocked = subprocess.run([
        sys.executable, str(SKILL / "scripts" / "build_annotation_workbook.py"),
        "--records", str(records_path), "--evidence", str(no_umap_evidence_path),
        "--umap-audit", str(umap_audit_path), "--output", str(work / "blocked.xlsx"),
        "--workspace-root", str(work.parents[1]), "--force",
    ], text=True, capture_output=True)
    assert blocked.returncode != 0
    assert "no UMAP source" in blocked.stderr

    # Myeloid DC/monocyte boundaries may be delivered conservatively as a blocked mixed-parent
    # fallback from aggregate evidence, while resolving reclustering confirms components without
    # automatically implying doublets.
    myeloid_genes = [
        "HLA-DRA", "HLA-DPA1", "HLA-DPB1", "CD74", "CD1C", "CLEC10A", "FCER1A",
        "CD14", "FCN1", "VCAN", "FCGR3A", "LST1", "LYZ", "TYROBP",
        "C1QA", "C1QB", "C1QC", "MERTK", "FOLR2", "CSF3R", "FCGR3B",
    ]
    myeloid_ratio = work / "myeloid_ratios.tsv"
    with myeloid_ratio.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "group", "expr_ratio"])
        for cluster in ("0", "1", "2"):
            for gene in myeloid_genes:
                if cluster == "0":
                    value = 0.8 if gene not in {"CSF3R", "FCGR3B"} else 0.05
                elif cluster == "1":
                    value = 0.8 if gene in {"CD14", "FCN1", "VCAN", "LST1", "LYZ", "TYROBP"} else 0.02
                else:
                    value = 0.8 if gene in {"C1QA", "C1QB", "C1QC", "MERTK", "FOLR2", "LST1", "LYZ", "TYROBP"} else 0.02
                writer.writerow([gene, cluster, value])
    myeloid_evidence = {
        "clusters": ["0", "1", "2"],
        "cluster_profiles": {
            cluster: {
                "top_markers": [], "qc_state_fraction_top50": 0.0,
                "naming_top_marker": {"gene": "HLA-DRA" if cluster == "0" else "LYZ"},
                "raw_top_marker": {"gene": "HLA-DRA" if cluster == "0" else "LYZ"},
                "top_informative_markers": [{"gene": gene} for gene in myeloid_genes],
                "excluded_naming_markers": [],
            }
            for cluster in ("0", "1", "2")
        },
        "average_shape": [len(myeloid_genes), 3], "average_reader": "test",
        "confirmed_metadata": {
            "species": "Human", "tissue": "lung", "annotation_level": "subcluster",
            "parent_population": "Myeloid", "parent_kind": "lineage", "interpretation_rule": "test",
        },
        "source_paths": source_paths,
    }
    aggregate_myeloid = enrich_evidence(
        copy.deepcopy(myeloid_evidence), ratio_path=myeloid_ratio,
        annotation_level="subcluster", species="Human", tissue="lung",
        parent_population="Myeloid", parent_kind="lineage",
    )
    aggregate_decision = aggregate_myeloid["deterministic_annotation_evidence"]["0"]
    assert aggregate_decision["boundary_validation_required"] is True
    assert aggregate_decision["stable_id"] == "Myeloid_cell"
    assert aggregate_decision["formal_identity_fallback"] == "mixed_incompatible_sublineages"
    assert aggregate_decision["mixed_population"] is True
    assert aggregate_decision["suspected_doublet"] is False
    assert aggregate_decision["auto_merge_allowed"] is False

    myeloid_cell_evidence = work / "myeloid_cell_evidence.json"
    myeloid_cell_evidence.write_text(json.dumps({
        "0": {
            "doublet_call": False, "doublet_fraction": 0.0,
            "mixed_population_confirmed": True, "reclustering_resolved": True,
            "resolved_components": ["cDC2", "Monocyte", "Macrophage"],
            "identity_boundary_validation": {
                "rule_id": "MYELOID_DC3_VS_MONOCYTE_COEXPRESSION_GATE",
                "coexpression_validated": True,
                "method": "Per-cell program review plus resolving reclustering.",
            },
        }
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    validated_myeloid = enrich_evidence(
        copy.deepcopy(myeloid_evidence), ratio_path=myeloid_ratio,
        cell_evidence_path=myeloid_cell_evidence,
        annotation_level="subcluster", species="Human", tissue="lung",
        parent_population="Myeloid", parent_kind="lineage",
    )
    validated_decision = validated_myeloid["deterministic_annotation_evidence"]["0"]
    assert validated_decision["boundary_validation_resolved"] is True
    assert validated_decision["stable_id"] == "Myeloid_cell"
    assert validated_decision["formal_identity_fallback"] == "mixed_incompatible_sublineages"
    assert validated_decision["mixed_population"] is True
    assert validated_decision["suspected_doublet"] is False
    assert validated_decision["auto_merge_allowed"] is False
    assert validated_decision["possible_components"] == ["cDC2", "Monocyte", "Macrophage"]
    print(json.dumps({"status": "pass", "checks": 57, "output": str(output)}))


if __name__ == "__main__":
    main()
