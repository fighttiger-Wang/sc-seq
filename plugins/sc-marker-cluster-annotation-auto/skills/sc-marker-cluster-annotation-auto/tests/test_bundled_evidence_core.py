#!/usr/bin/env python3
"""Regression for the evidence core bundled in this installable plugin."""

import argparse
import csv
import json
import sys
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from qualitative_evidence_core import enrich_evidence  # noqa: E402
from knowledge_base import build_runtime_config, load_knowledge_base  # noqa: E402


PROGRAMS = {
    "0": {"EPCAM", "KRT8", "KRT18", "KRT19"},
    "1": {"CD3D", "CD3E", "CD3G", "TRAC", "LCK", "LAT"},
    "2": {"NKG7", "KLRD1", "PRF1", "GNLY", "NCR1", "KLRF1"},
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    work = Path(parser.parse_args().work_dir).resolve()
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
        "cluster_profiles": {cluster: {"top_markers": [], "top_informative_markers": []} for cluster in PROGRAMS},
    }
    result = enrich_evidence(
        evidence, ratio_path=ratios, annotation_level="major", species="Human",
        tissue="fetal lung", parent_population="All_cells", parent_kind="mixed",
        require_complete_ratio=True,
    )
    decisions = result["qualitative_annotation_evidence"]
    assert decisions["0"]["stable_id"] == "Epithelial_cell"
    assert decisions["1"]["stable_id"] == "T_cell"
    assert decisions["2"]["stable_id"] in {"NK", "NK_cell"}
    policy = result["annotation_evidence_policy"]
    assert policy["decision_model"] == "qualitative_biological_gates"
    assert policy["aggregate_identity_scores"] is False
    forbidden = {"score", "quality_score", "confidence", "score_margin", "primary_evidence_score", "runner_up_evidence_score", "ranked_identity_evidence", "rival_lineage_score"}

    def audit(value):
        if isinstance(value, dict):
            assert not (forbidden & set(value))
            for item in value.values():
                audit(item)
        elif isinstance(value, list):
            for item in value:
                audit(item)

    audit(decisions)
    assert all(item["qualitative_gates"]["identity_anchor"] == "通过" for item in decisions.values())
    runtime = build_runtime_config(
        load_knowledge_base(), species="Human", tissue="fetal lung", annotation_level="subcluster",
        parent_population="T_NK_2_2", parent_kind="lineage",
    )
    assert runtime["resolved_parent_id"] == "T_NK_lineage"
    assert "MAIT" in runtime["identity_panels"]
    assert "SLC4A10" not in runtime["identity_panels"]["MAIT"]["core"]
    assert "TRAV1-2" not in runtime["identity_panels"]["MAIT"]["core"]
    assert len(runtime["identity_panels"]["MAIT"]["core"]) >= 5
    print(json.dumps({"status": "pass", "checks": 17, "work_dir": str(work)}))


if __name__ == "__main__":
    main()
