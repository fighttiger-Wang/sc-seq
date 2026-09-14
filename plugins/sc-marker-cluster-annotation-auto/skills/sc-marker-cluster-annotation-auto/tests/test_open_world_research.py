#!/usr/bin/env python3
"""Regression checks for open-world research triggering and admission."""

import argparse
import copy
import json
import sys
from pathlib import Path


def expect_failure(callback, text):
    try:
        callback()
    except ValueError as exc:
        assert text in str(exc), str(exc)
        return
    raise AssertionError(f"Expected failure containing: {text}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    skill = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(skill / "scripts"))
    from research_workflow import (
        apply_research_stage,
        complete_calibration_use,
        validate_formal_research_binding,
    )

    policy = work / "calibration-policy.json"
    policy.write_text(json.dumps({
        "version": "test-v1",
        "counters": {
            "sc-marker-cluster-annotation-auto": {
                "required_online_verification_uses": 5,
                "current_count": 0,
            }
        },
        "after_calibration": {"retrieve_when": ["knowledge_base_gap"]},
    }), encoding="utf-8")
    state = work / "calibration-state.json"
    evidence = {
        "clusters": ["0"],
        "confirmed_metadata": {
            "species": "Mouse", "tissue": "Aorta", "parent_population": "Stromal_cell",
            "sample_context": {"disease": "vascular injury"},
        },
        "cluster_profiles": {
            "0": {
                "top_markers": [{"gene": "COL1A1"}, {"gene": "ACTA2"}, {"gene": "TAGLN"}],
                "top_informative_markers": [{"gene": "COL1A1"}, {"gene": "ACTA2"}],
            }
        },
        "qualitative_annotation_evidence": {
            "0": {
                "stable_id": "Fibroblast",
                "primary_program": "Fibroblast",
                "qualitative_gates": {"sibling_competition": "通过"},
                "auto_binding_eligible_candidates": ["Fibroblast"],
                "candidate_program_audits": [
                    {
                        "label": "Fibroblast", "program_gate": "通过",
                        "parent_lineage_gate": "通过", "tissue_scope_match": True,
                        "supporting_core": [{"gene": "COL1A1"}],
                        "supporting_supportive": [{"gene": "DCN"}],
                        "conflicting_markers": [], "missing_core_markers": [],
                    }
                ],
                "supporting_markers": [{"gene": "COL1A1"}, {"gene": "ACTA2"}],
                "identity_arbitration": [], "off_parent_detected": False,
            }
        },
        "annotation_evidence_policy": {
            "core_version": "test-core", "config_version": "test-config",
            "knowledge_base_version": "test-kb",
        },
    }

    first = copy.deepcopy(evidence)
    requests, normalized, external = apply_research_stage(
        first, policy, state, "0.6.10-test"
    )
    assert normalized is None
    assert external == []
    assert requests["requests"][0]["trigger_reasons"] == ["calibration_verification"]
    assert first["qualitative_annotation_evidence"]["0"]["formal_identity_binding_allowed"] is False
    assert first["annotation_evidence_policy"]["open_world_research"]["formal_delivery_blocked"] is True

    second = copy.deepcopy(evidence)
    requests_again, _, _ = apply_research_stage(second, policy, state, "0.6.10-test")
    assert requests_again["request_sha256"] == requests["request_sha256"]

    expect_failure(
        lambda: validate_formal_research_binding(
            [{"cluster_id": "0", "stable_id": "Fibroblast", "label_basis": "researched_registered_candidate"}],
            first,
        ),
        "research is pending",
    )

    source_a = {
        "title": "Independent atlas A", "doi_or_pmid_or_url": "DOI:10.1/A",
        "retrieval_date": "2026-09-14", "species": "Mouse", "tissue": "Aorta",
        "supported_program": "fibroblast contractile program", "exclusions": "not mature SMC alone",
        "adoption_or_rejection_reason": "supports the boundary",
    }
    source_b = {
        "title": "Independent atlas B", "doi_or_pmid_or_url": "PMID:2",
        "retrieval_date": "2026-09-14", "species": "Mouse", "tissue": "Aorta",
        "supported_program": "fibroblast contractile program", "exclusions": "not pericyte alone",
        "adoption_or_rejection_reason": "independent validation",
    }
    resolution = {
        "status": "resolved", "query": "mouse aorta myofibroblast COL1A1 ACTA2 TAGLN",
        "retrieval_date": "2026-09-14", "candidate_label": "Myofibroblast",
        "label_basis": "validated_external_candidate",
        "current_case_support_markers": ["COL1A1", "ACTA2"],
        "exclusions": ["mature SMC and pericyte programs reviewed"],
        "adoption_or_rejection_rationale": "Current case retains fibroblast and contractile programs.",
        "sources": [source_a, source_b],
    }

    stale = work / "stale.json"
    stale.write_text(json.dumps({
        "request_sha256": "stale", "resolutions": {"0": resolution}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", stale),
        "request_sha256",
    )

    duplicate = copy.deepcopy(resolution)
    duplicate["sources"] = [source_a, copy.deepcopy(source_a)]
    duplicate_path = work / "duplicate.json"
    duplicate_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": duplicate}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", duplicate_path),
        "not independent",
    )

    one_marker = copy.deepcopy(resolution)
    one_marker["current_case_support_markers"] = ["COL1A1"]
    one_marker_path = work / "one-marker.json"
    one_marker_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": one_marker}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", one_marker_path),
        "at least two current-case",
    )

    wrong_basis = copy.deepcopy(resolution)
    wrong_basis["label_basis"] = "researched_registered_candidate"
    wrong_basis_path = work / "wrong-basis.json"
    wrong_basis_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": wrong_basis}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", wrong_basis_path),
        "validated_external_candidate",
    )

    valid_path = work / "valid.json"
    valid_path.write_text(json.dumps({
        "schema_version": "1.0.0",
        "request_sha256": requests["request_sha256"],
        "resolutions": {"0": resolution},
    }), encoding="utf-8")
    resolved = copy.deepcopy(evidence)
    _, normalized, external = apply_research_stage(
        resolved, policy, state, "0.6.10-test", valid_path
    )
    decision = resolved["qualitative_annotation_evidence"]["0"]
    assert normalized["research_artifact_sha256"] == decision["research_artifact_sha256"]
    assert decision["research_selected_identity"] == "Myofibroblast"
    assert decision["formal_identity_binding_allowed"] is True
    assert external[0]["candidate_label"] == "Myofibroblast"
    records = [{
        "cluster_id": "0", "stable_id": "Myofibroblast",
        "label_basis": "validated_external_candidate",
    }]
    assert validate_formal_research_binding(records, resolved) is True
    expect_failure(
        lambda: validate_formal_research_binding(
            [{"cluster_id": "0", "stable_id": "Fibroblast", "label_basis": "validated_external_candidate"}],
            resolved,
        ),
        "does not match researched identity",
    )
    completion = complete_calibration_use(resolved)
    assert completion["updated"] is True
    assert json.loads(state.read_text(encoding="utf-8"))["completed_uses"]
    assert complete_calibration_use(resolved)["updated"] is False

    print(json.dumps({"status": "pass", "checks": 22}, ensure_ascii=False))


if __name__ == "__main__":
    main()
