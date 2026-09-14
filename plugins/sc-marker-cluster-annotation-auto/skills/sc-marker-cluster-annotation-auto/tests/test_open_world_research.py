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
        "claim_level": "identity", "source_wording": "Myofibroblast",
        "lineage_requirement": "not_required", "native_or_disease_induced": "context_dependent",
    }
    source_b = {
        "title": "Independent atlas B", "doi_or_pmid_or_url": "PMID:2",
        "retrieval_date": "2026-09-14", "species": "Mouse", "tissue": "Aorta",
        "supported_program": "fibroblast contractile program", "exclusions": "not pericyte alone",
        "adoption_or_rejection_reason": "independent validation",
        "claim_level": "identity", "source_wording": "Myofibroblast",
        "lineage_requirement": "not_required", "native_or_disease_induced": "context_dependent",
    }
    resolution = {
        "status": "resolved", "query": "mouse aorta myofibroblast COL1A1 ACTA2 TAGLN",
        "retrieval_date": "2026-09-14", "candidate_label": "Myofibroblast",
        "label_basis": "validated_external_candidate",
        "claim_level": "identity", "source_supported_label": "Myofibroblast",
        "source_wording": "Both independent sources use Myofibroblast as an identity.",
        "identity_derivation": "source_exact_identity",
        "lineage_requirement": "not_required", "native_or_disease_induced": "context_dependent",
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

    legacy = copy.deepcopy(resolution)
    legacy["sources"] = [copy.deepcopy(source_a), copy.deepcopy(source_b)]
    legacy["sources"][0].pop("claim_level")
    legacy_path = work / "legacy-missing-claim.json"
    legacy_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": legacy}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", legacy_path),
        "missing fields",
    )

    like_a = {
        **source_a,
        "doi_or_pmid_or_url": "DOI:10.1161/CIRCULATIONAHA.120.048378",
        "claim_level": "identity_like", "source_wording": "fibrochondrocyte-like cells",
        "supported_program": "fibrochondrocyte-like extracellular-matrix program",
        "native_or_disease_induced": "disease_induced",
    }
    like_b = {
        **source_b,
        "doi_or_pmid_or_url": "PMID:33303074",
        "claim_level": "identity_like", "source_wording": "fibrochondrocyte-like cells",
        "supported_program": "fibrochondrocyte-like extracellular-matrix program",
        "native_or_disease_induced": "disease_induced",
    }
    unqualified = {
        **resolution,
        "candidate_label": "Fibrochondrocyte",
        "claim_level": "identity_like", "source_supported_label": "Fibrochondrocyte_like",
        "source_wording": "Both sources say fibrochondrocyte-like cells.",
        "identity_derivation": "neutral_contextual_identity",
        "qualified_label": "Fibrochondrocyte_like",
        "native_or_disease_induced": "disease_induced",
        "sources": [like_a, like_b],
    }
    unqualified_path = work / "unqualified-like.json"
    unqualified_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": unqualified}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", unqualified_path),
        "cannot remove the literature qualifier",
    )

    misclassified = copy.deepcopy(resolution)
    misclassified["candidate_label"] = "Fibrochondrocyte"
    misclassified["source_supported_label"] = "Fibrochondrocyte"
    misclassified["sources"] = [copy.deepcopy(like_a), copy.deepcopy(like_b)]
    for source in misclassified["sources"]:
        source["claim_level"] = "identity"
    misclassified_path = work / "misclassified-like-as-identity.json"
    misclassified_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": misclassified}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", misclassified_path),
        "source_wording does not support claim_level=identity",
    )

    state_source = {
        **source_b,
        "doi_or_pmid_or_url": "DOI:10.1161/ATVBAHA.124.322045",
        "claim_level": "state", "source_wording": "osteochondrogenic state",
        "supported_program": "osteochondrogenic state",
        "native_or_disease_induced": "disease_induced",
    }
    mixed_claim = {
        **resolution,
        "candidate_label": "Osteochondrogenic_stromal_cell",
        "claim_level": "program", "source_supported_label": "Fibrochondrocyte_like",
        "source_wording": "One source says fibrochondrocyte-like; one says osteochondrogenic state.",
        "identity_derivation": "neutral_contextual_identity",
        "qualified_label": "Fibrochondrocyte_like", "state_label": "osteochondrogenic",
        "program_label": "osteochondrogenic_matrix_program",
        "native_or_disease_induced": "disease_induced",
        "sources": [like_a, state_source],
    }
    mixed_claim_path = work / "mixed-claim.json"
    mixed_claim_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": mixed_claim}
    }), encoding="utf-8")
    mixed_resolved = copy.deepcopy(evidence)
    _, mixed_normalized, mixed_external = apply_research_stage(
        mixed_resolved, policy, state, "0.6.10-test", mixed_claim_path
    )
    mixed_decision = mixed_resolved["qualitative_annotation_evidence"]["0"]
    assert mixed_normalized["resolutions"]["0"]["claim_level"] == "program"
    assert mixed_decision["stable_id"] == "Osteochondrogenic_stromal_cell"
    assert mixed_decision["lower_level_subtype"] == "Fibrochondrocyte_like"
    assert mixed_decision["state"] == "osteochondrogenic"
    assert mixed_external[0]["claim_level"] == "program"
    expect_failure(
        lambda: validate_formal_research_binding([{
            "cluster_id": "0", "stable_id": "Osteochondrogenic_stromal_cell",
            "label_basis": "validated_external_candidate", "state": "osteochondrogenic",
        }], mixed_resolved),
        "must retain research qualifier",
    )
    assert validate_formal_research_binding([{
        "cluster_id": "0", "stable_id": "Osteochondrogenic_stromal_cell",
        "label_basis": "validated_external_candidate", "state": "osteochondrogenic",
        "lower_level_subtype": "Fibrochondrocyte_like",
    }], mixed_resolved) is True

    lineage_a = {
        **source_a,
        "doi_or_pmid_or_url": "DOI:10.2/LINEAGE-A",
        "claim_level": "lineage_identity", "source_wording": "SMC-derived lineage identity",
        "lineage_requirement": "lineage_tracing_required",
    }
    lineage_b = {
        **source_b,
        "doi_or_pmid_or_url": "PMID:LINEAGE-B",
        "claim_level": "lineage_identity", "source_wording": "fate-mapped SMC-derived lineage",
        "lineage_requirement": "lineage_tracing_required",
    }
    lineage_resolution = {
        **resolution,
        "candidate_label": "SMC_derived_fibroblast",
        "claim_level": "lineage_identity", "source_supported_label": "SMC_derived_fibroblast",
        "source_wording": "Both sources claim an SMC-derived lineage identity.",
        "identity_derivation": "source_exact_identity",
        "lineage_requirement": "lineage_tracing_required",
        "sources": [lineage_a, lineage_b],
    }
    lineage_path = work / "lineage-without-case-evidence.json"
    lineage_path.write_text(json.dumps({
        "request_sha256": requests["request_sha256"], "resolutions": {"0": lineage_resolution}
    }), encoding="utf-8")
    expect_failure(
        lambda: apply_research_stage(copy.deepcopy(evidence), policy, state, "0.6.10-test", lineage_path),
        "lacks current-case lineage evidence",
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

    print(json.dumps({"status": "pass", "checks": 36}, ensure_ascii=False))


if __name__ == "__main__":
    main()
