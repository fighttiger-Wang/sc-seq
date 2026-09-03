#!/usr/bin/env python3
"""Regression checks for the score-free qualitative evidence core."""

import argparse
import csv
import json
import sys
from pathlib import Path


CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
from qualitative_evidence_core import (  # noqa: E402
    _apply_myeloid_boundary_precedence,
    _incompatible_complete_programs,
    _is_more_defensible,
    enrich_evidence,
)
from knowledge_base import build_runtime_config, load_knowledge_base  # noqa: E402


PROGRAMS = {
    "0": {"EPCAM", "KRT8", "KRT18", "KRT19"},
    "1": {"CD3D", "CD3E", "CD3G", "TRAC", "LCK", "LAT"},
    "2": {"NKG7", "KLRD1", "PRF1", "GNLY", "NCR1", "KLRF1"},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    genes = sorted(set().union(*PROGRAMS.values()))
    ratios = work / "ratios.tsv"
    with ratios.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "group", "expr_ratio"])
        for cluster, active in PROGRAMS.items():
            for gene in genes:
                writer.writerow([gene, cluster, 0.85 if gene in active else 0.01])
    evidence = {
        "clusters": list(PROGRAMS),
        "average_gene_names": genes,
        "cluster_profiles": {
            cluster: {"top_markers": [], "top_informative_markers": []}
            for cluster in PROGRAMS
        },
    }
    result = enrich_evidence(
        evidence, ratio_path=ratios, annotation_level="major", species="Human",
        tissue="fetal lung", parent_population="All_cells", parent_kind="mixed",
        require_complete_ratio=True,
    )
    assert "deterministic_annotation_evidence" not in result
    assert "qualitative_annotation_evidence" in result
    policy = result["annotation_evidence_policy"]
    assert policy["decision_model"] == "qualitative_biological_gates"
    assert policy["aggregate_identity_scores"] is False
    decisions = result["qualitative_annotation_evidence"]
    assert decisions["0"]["stable_id"] == "Epithelial_cell"
    assert decisions["1"]["stable_id"] == "T_cell"
    assert decisions["2"]["stable_id"] in {"NK", "NK_cell"}
    forbidden = {
        "score", "quality_score", "confidence", "score_margin",
        "primary_evidence_score", "runner_up_evidence_score",
        "ranked_identity_evidence", "rival_lineage_score",
    }

    def audit(value, path="root"):
        if isinstance(value, dict):
            overlap = forbidden & set(value)
            assert not overlap, f"forbidden aggregate fields at {path}: {sorted(overlap)}"
            for key, item in value.items():
                audit(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                audit(item, f"{path}[{index}]")

    audit(result["qualitative_annotation_evidence"])
    assert all(
        decision["qualitative_gates"]["identity_anchor"] == "通过"
        for decision in decisions.values()
    )

    # MAIT must not depend on a single canonical TCR transcript in aggregate
    # data; SLC4A10 and TRAV1-2 are confirmatory/supportive evidence, while a
    # coherent alpha-beta branch remains required.
    kb = load_knowledge_base()
    runtime = build_runtime_config(
        kb, species="Human", tissue="fetal lung", annotation_level="subcluster",
        parent_population="T_NK_2_2", parent_kind="lineage",
    )
    assert runtime["resolved_parent_id"] == "T_NK_lineage"
    assert "MAIT" in runtime["identity_panels"]
    assert "SLC4A10" not in runtime["identity_panels"]["MAIT"]["core"]
    assert "TRAV1-2" not in runtime["identity_panels"]["MAIT"]["core"]
    assert len(runtime["identity_panels"]["MAIT"]["core"]) >= 5

    def candidate(label, parent_gate="通过", program_gate="通过", parent_path=None, major="Myeloid_cell"):
        return {
            "label": label,
            "parent_lineage_gate": parent_gate,
            "program_gate": program_gate,
            "absolute_program_gate": "不适用",
            "branch_gate": "不适用",
            "strong_core": [label],
            "supporting_core": [label],
            "conflicting_markers": [],
            "supporting_supportive": [],
            "parent_path": list(parent_path or ["Cell", "Immune_cell", "Myeloid_cell"]),
            "major_label": major,
            "mutually_exclusive_audit": {},
        }

    myeloid = candidate("Classical_monocyte")
    off_parent = candidate("CD4_T", parent_gate="不通过", parent_path=["Cell", "Immune_cell", "T_cell"], major="T_cell")
    replace, reason = _is_more_defensible(myeloid, off_parent)
    assert replace is True and reason == "declared_parent_scope_precedence"

    macrophage = candidate("Macrophage", parent_path=["Cell", "Immune_cell", "Myeloid_cell"])
    resident = candidate("Tissue_resident_macrophage", parent_path=["Cell", "Immune_cell", "Myeloid_cell", "Macrophage"])
    replace, reason = _is_more_defensible(resident, macrophage)
    assert replace is True and reason == "complete_supported_descendant"

    assert _incompatible_complete_programs(myeloid, [myeloid, off_parent]) == []

    cdc1 = candidate("cDC1")
    selected, reason = _apply_myeloid_boundary_precedence(
        myeloid, [myeloid, cdc1, off_parent],
        {
            "assessed": True,
            "neutrophil_vs_monocyte": {},
            "dc_identity_programs": {"cDC1": {"passed": True}, "cDC2": {"passed": False}, "Migratory_DC": {"passed": False}},
            "dc3_vs_monocyte": {"macrophage_competing": False, "dc3_boundary_candidate": False},
        },
    )
    assert selected["label"] == "cDC1" and reason == "registered_cdc1_program_gate"

    selected, reason = _apply_myeloid_boundary_precedence(
        cdc1, [macrophage, cdc1],
        {
            "assessed": True,
            "neutrophil_vs_monocyte": {},
            "dc_identity_programs": {"cDC1": {"passed": True}, "cDC2": {"passed": True}, "Migratory_DC": {"passed": False}},
            "dc3_vs_monocyte": {"macrophage_competing": True, "dc3_boundary_candidate": False},
        },
    )
    assert selected["label"] == "Macrophage" and reason == "registered_macrophage_exclusion_gate"

    print(json.dumps({"status": "pass", "checks": 17, "work_dir": str(work)}))


if __name__ == "__main__":
    main()
