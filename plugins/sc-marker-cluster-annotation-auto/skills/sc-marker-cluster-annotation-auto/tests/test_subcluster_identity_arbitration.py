#!/usr/bin/env python3
"""Abstract regressions for staged subcluster identity arbitration."""

import argparse
import json
import sys
from pathlib import Path


def candidate(label, strong=2, supported=3, eligible=True, absolute=False):
    return {
        "label": label,
        "major_label": "Synthetic_parent",
        "parent_path": ["Cell", "Synthetic_parent", label],
        "within_parent_scope": True,
        "program_gate": "通过" if eligible else "不通过",
        "absolute_program_gate": "通过" if absolute else "不适用",
        "strong_core": [{"gene": f"S{index}"} for index in range(strong)],
        "supporting_core": [{"gene": f"C{index}"} for index in range(supported)],
        "supporting_supportive": [],
        "conflicting_markers": [],
        "missing_core_markers": [],
        "evidence_ids": ["SYNTHETIC"],
        "panel_species": "Synthetic",
        "cross_species_inference": False,
    }


def decision(left_relative, right_relative, include_boundary=True, left_eligible=True):
    audits = [
        candidate("Identity_A", eligible=left_eligible, absolute=True),
        candidate("Identity_B"),
    ]
    if include_boundary:
        audits.append(candidate("Boundary_AB"))
    return {
        "stable_id": "Boundary_AB" if include_boundary else "Identity_B",
        "suggested_identity": "Boundary_AB" if include_boundary else "Identity_B",
        "primary_program": "Boundary_AB" if include_boundary else "Identity_B",
        "primary_major_label": "Synthetic_parent",
        "expected_parent_id": "Synthetic_parent",
        "candidate_program_audits": audits,
        "identity_boundary_audit": {
            "synthetic": {
                "active": True,
                "left_hits": ["L1", "L2"],
                "right_hits": ["R1", "R2"],
                "left_relative": [f"LR{index}" for index in range(left_relative)],
                "right_relative": [f"RR{index}" for index in range(right_relative)],
                "left_mean": 0.5,
                "right_mean": 0.5,
                "boundary_eligible": include_boundary,
            }
        },
        "qualitative_gates": {"sibling_competition": "未确定", "umap": "未确定"},
        "state_list": ["Identity_A_like_state"],
        "state_program": [{"program": "Identity_A_like_state", "gate": "通过"}],
        "umap_audit": {"suggested_label": "Identity_A"},
        "biological_precedence_trace": [],
        "evidence_gaps": [],
        "auto_merge_allowed": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    policy = {
        "schema_version": "test",
        "stages": ["candidate_generation", "identity_eligibility", "competing_program_arbitration", "boundary_resolution", "state_development_separation", "umap_consistency_audit", "final_identity_binding"],
        "rules": [{
            "rule_id": "ABSTRACT_A_VS_B",
            "scope": {"expected_parent_ids": ["Synthetic_parent"]},
            "activation": {"path": ["identity_boundary_audit", "synthetic", "active"], "equals": True},
            "sides": {
                "left": {"candidate_labels": ["Identity_A"], "program": {"audit_root": ["identity_boundary_audit", "synthetic"], "hits_path": ["left_hits"], "relative_hits_path": ["left_relative"], "mean_path": ["left_mean"], "minimum_hits": 2, "minimum_relative_hits": 2, "expected_relative_hits": 3}},
                "right": {"candidate_labels": ["Identity_B"], "program": {"audit_root": ["identity_boundary_audit", "synthetic"], "hits_path": ["right_hits"], "relative_hits_path": ["right_relative"], "mean_path": ["right_mean"], "minimum_hits": 2, "minimum_relative_hits": 2, "expected_relative_hits": 3}}
            },
            "dominance": {"minimum_ratio": 1.25, "minimum_absolute_margin": 0.1},
            "boundary_identity": {"candidate_labels": ["Boundary_AB"], "eligibility_path": ["identity_boundary_audit", "synthetic", "boundary_eligible"], "when": "coherent_without_dominance"}
        }]
    }
    policy_path = work / "abstract-policy.json"
    policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    from subcluster_identity_arbitration import apply_subcluster_identity_arbitration

    evidence = {
        "annotation_evidence_policy": {},
        "qualitative_annotation_evidence": {
            "left": decision(3, 2),
            "right": decision(2, 3),
            "boundary": decision(3, 3),
            "state_cannot_choose": decision(3, 3, include_boundary=False),
            "absolute_not_victory": decision(1, 3),
            "topology_cannot_rescue": decision(3, 2, include_boundary=False, left_eligible=False),
        },
    }
    result = apply_subcluster_identity_arbitration(evidence, policy_path)
    decisions = result["qualitative_annotation_evidence"]

    assert decisions["left"]["stable_id"] == "Identity_A"
    assert decisions["right"]["stable_id"] == "Identity_B"
    assert decisions["boundary"]["stable_id"] == "Boundary_AB"
    assert decisions["boundary"]["identity_arbitration"][0]["resolution"] == "unresolved"
    assert decisions["state_cannot_choose"]["stable_id"] == "Identity_B"
    assert decisions["state_cannot_choose"]["qualitative_gates"]["sibling_competition"] == "未确定"
    assert decisions["absolute_not_victory"]["stable_id"] == "Identity_B"
    assert decisions["absolute_not_victory"]["identity_arbitration"][0]["absolute_gate_role"] == "eligibility_only"
    assert decisions["topology_cannot_rescue"]["stable_id"] == "Identity_B"
    assert decisions["topology_cannot_rescue"]["identity_arbitration"][0]["binding"] == "blocked_missing_eligible_candidate"
    assert decisions["topology_cannot_rescue"]["identity_arbitration"][0]["topology_role"] == "post_selection_consistency_audit_only"
    assert decisions["right"]["state_list"] == ["Identity_A_like_state"]
    assert len(result["annotation_evidence_policy"]["subcluster_identity_arbitration"]["sha256"]) == 64
    assert result["annotation_evidence_policy"]["subcluster_identity_arbitration"]["stages"][-1] == "final_identity_binding"

    print(json.dumps({"status": "pass", "checks": 14, "work_dir": str(work)}))


if __name__ == "__main__":
    main()
