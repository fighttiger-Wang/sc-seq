#!/usr/bin/env python3
"""Regression checks for the model-facing blind-test evidence contract."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    from prepare_annotation import evidence_digest

    decision = {
        "stable_id": "candidate_a",
        "suggested_identity": "candidate_a",
        "primary_program": "candidate_a",
        "primary_major_label": "parent_lineage",
        "biological_precedence_trace": ["candidate_a"],
        "recommended_action": "retain candidate_a",
        "decision_rationale": "candidate_a was selected",
        "candidate_program_audits": [
            {"label": "candidate_a", "program_gate": "pass"},
            {"label": "candidate_b", "program_gate": "fail"},
        ],
        "supporting_markers": [{"gene": "GENE_A", "p_in": 0.8}],
        "qualitative_gates": {"identity_anchor": "pass"},
    }
    evidence = {
        "schema_version": "test",
        "average_reader": "synthetic",
        "average_gene_header": "gene",
        "average_gene_header_normalized_to": "GeneName",
        "average_shape": [1, 2],
        "average_matrix_semantics": {},
        "clusters": ["0"],
        "cluster_profiles": {
            "0": {
                "marker_count": 1,
                "top_markers": [{"gene": "GENE_A"}],
                "raw_top_marker": "GENE_A",
                "naming_top_marker": "GENE_A",
                "excluded_naming_markers": [],
                "top_informative_markers": [{"gene": "GENE_A"}],
                "signature_marker_support": {},
                "qc_state_fraction_top50": 0.0,
                "alerts": [],
            }
        },
        "qualitative_annotation_evidence": {"0": decision},
        "canonical_expression_by_gene": {},
        "confirmed_metadata": {
            "blind_test": True,
            "project_prior_clusters": [],
            "annotation_constraints": {},
        },
        "source_paths": {},
        "naming_marker_policy": {},
        "annotation_evidence_policy": {"user_constraints": {}},
        "qualitative_tnk_audit": {},
    }
    digest = evidence_digest(evidence, blind_test=True)
    assert digest["blind_test"] is True
    for cluster, item in digest["cluster_profiles"].items():
        qualitative = item["qualitative_evidence"]
        for key in ("stable_id", "suggested_identity", "primary_program", "primary_major_label", "decision_rationale", "recommended_action"):
            assert qualitative.get(key, "") == "", f"blind digest leaked {key} for cluster {cluster}"
        assert qualitative["candidate_program_audits"], f"candidate alternatives missing for cluster {cluster}"
        assert qualitative["supporting_markers"] == decision["supporting_markers"]

    assert evidence["qualitative_annotation_evidence"]["0"]["stable_id"] == "candidate_a"
    print(json.dumps({"status": "pass", "checks": 10}, ensure_ascii=False))


if __name__ == "__main__":
    main()
