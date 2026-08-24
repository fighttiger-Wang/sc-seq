#!/usr/bin/env python3
"""Exercise major workbook QA for per-cluster T/NK, mixed blocking, and confidence caps."""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from annotation_evidence_core import enrich_evidence  # noqa: E402


PANELS = {
    "epi": ["EPCAM", "KRT8", "KRT18", "KRT19"],
    "endo": ["PECAM1", "CDH5", "VWF", "KDR"],
    "t": ["CD3D", "CD3E", "CD3G", "TRAC"],
    "nk": ["NKG7", "KLRD1", "NCR1", "GNLY"],
}


def base_evidence(programs):
    profiles = {}
    for cluster, active in programs.items():
        marker = PANELS[active[0]][0]
        profiles[cluster] = {
            "top_markers": [], "qc_state_fraction_top50": 0.0,
            "naming_top_marker": {"gene": marker}, "raw_top_marker": {"gene": marker},
            "top_informative_markers": [{"gene": marker}], "excluded_naming_markers": [],
        }
    return {
        "clusters": list(programs), "cluster_profiles": profiles,
        "average_shape": [len({g for panel in PANELS.values() for g in panel}), len(programs)],
        "average_reader": "test", "confirmed_metadata": {"species": "test", "tissue": "test", "annotation_level": "major", "parent_population": "All_cells", "parent_kind": "mixed", "interpretation_rule": "test"},
        "source_paths": {"cell_avg_exp": "test", "marker_table": "test"},
    }


def write_ratios(path, programs):
    genes = sorted({gene for panel in PANELS.values() for gene in panel})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "group", "expr_ratio"])
        for cluster, active in programs.items():
            active_genes = {gene for name in active for gene in PANELS[name]}
            for gene in genes:
                writer.writerow([gene, cluster, 0.8 if gene in active_genes else 0.01])


def record(cluster, label, evidence, mixed=False):
    decision = evidence["deterministic_annotation_evidence"][cluster]
    marker = evidence["cluster_profiles"][cluster]["naming_top_marker"]["gene"]
    supporting = "CD3D; CD3E; TRAC; NKG7; KLRD1; GNLY" if mixed else "; ".join(PANELS[{"Epithelial_cell": "epi", "Endothelial_cell": "endo", "T_cell": "t", "NK_cell": "nk"}.get(label, "t")])
    return {
        "cluster_id": cluster, "celltype_cn": label, "celltype_en": label,
        "label_basis": "canonical_subtype", "canonical_subtype": label,
        "top_marker_gene": marker, "literature_source": "Cell Ontology", "naming_grammar": "major_v1",
        "contextually_excluded_naming_markers": [], "broad_type": label, "fine_type": "", "state": "",
        "supporting_markers": supporting, "conflicting_markers": "",
        "candidate_labels": "T_cell; NK_cell" if mixed else label,
        "confidence": "medium-high", "quality_score": 80,
        "mixed_or_doublet": False, "mixture_type": "none", "possible_components": "",
        "rationale": "Deterministic major-lineage regression record.",
        "manual_review": decision["risk_level"] != "R0_ACCEPT", "review_action": decision["recommended_action"],
    }


def build(work, name, programs, labels):
    ratio = work / f"{name}.tsv"
    write_ratios(ratio, programs)
    evidence = enrich_evidence(base_evidence(programs), ratio_path=ratio, annotation_level="major")
    records = [record(cluster, labels[cluster], evidence, evidence["deterministic_annotation_evidence"][cluster]["tnk_provisional"] == "unresolved_T_NK") for cluster in programs]
    evidence_path, records_path, output = work / f"{name}.evidence.json", work / f"{name}.records.json", work / f"{name}.xlsx"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [sys.executable, str(SKILL / "scripts" / "build_annotation_workbook.py"), "--records", str(records_path), "--evidence", str(evidence_path), "--output", str(output), "--workspace-root", str(work.parents[1]), "--force"]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout + completed.stderr)
    qa = json.loads(output.with_suffix(".qa.json").read_text(encoding="utf-8"))
    assert qa["status"] == "pass"
    workbook = load_workbook(output, data_only=False)
    assert workbook.sheetnames == ["注释结果", "详细证据", "说明与数据来源"]
    assert "简化映射" not in workbook.sheetnames
    for sheet in workbook.worksheets:
        assert sheet.auto_filter.ref is None
    assert max((row.height or 15) for row in workbook["注释结果"].row_dimensions.values()) <= 54
    main_values = [cell.value for row in workbook["注释结果"].iter_rows() for cell in row]
    assert not any(isinstance(value, str) and value.lstrip().startswith(("{", "[")) for value in main_values)
    assert not any(isinstance(value, str) and ":\\" in value for value in main_values)
    quality_col = [cell.value for cell in workbook["注释结果"][1]].index("质量评分") + 1
    assert isinstance(workbook["注释结果"].cell(2, quality_col).value, (int, float))
    return evidence, records, command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    split_programs = {"0": ["epi"], "1": ["endo"], "2": ["t"], "3": ["nk"]}
    split_labels = {"0": "Epithelial_cell", "1": "Endothelial_cell", "2": "T_cell", "3": "NK_cell"}
    split_evidence, split_records, split_command = build(work, "split", split_programs, split_labels)
    assert split_evidence["deterministic_tnk_arbitration"]["recommended_regime"] == "per_cluster"

    mixed_programs = {"0": ["t", "nk"], "1": ["epi"]}
    mixed_labels = {"0": "T_cell", "1": "Epithelial_cell"}
    mixed_evidence, _, _ = build(work, "mixed", mixed_programs, mixed_labels)
    assert mixed_evidence["deterministic_tnk_arbitration"]["recommended_regime"] == "per_cluster"
    assert mixed_evidence["deterministic_annotation_evidence"]["0"]["auto_merge_allowed"] is False

    minimal_evidence = json.loads(json.dumps(split_evidence))
    minimal_records = json.loads(json.dumps(split_records))
    for decision in minimal_evidence["deterministic_annotation_evidence"].values():
        decision["evidence_mode"] = "minimal"
        decision["evidence_completeness"] = "positive_markers_only"
    minimal_records[0]["confidence"] = "high"
    minimal_evidence_path, minimal_records_path = work / "minimal.evidence.json", work / "minimal.records.json"
    minimal_evidence_path.write_text(json.dumps(minimal_evidence, ensure_ascii=False), encoding="utf-8")
    minimal_records_path.write_text(json.dumps(minimal_records, ensure_ascii=False), encoding="utf-8")
    failed = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "build_annotation_workbook.py"), "--records", str(minimal_records_path), "--evidence", str(minimal_evidence_path), "--output", str(work / "minimal.xlsx"), "--workspace-root", str(work.parents[1]), "--force"],
        text=True, capture_output=True,
    )
    assert failed.returncode != 0 and "cannot receive high confidence" in (failed.stdout + failed.stderr)
    print(json.dumps({"status": "pass", "checks": 12, "work_dir": str(work)}))


if __name__ == "__main__":
    main()
