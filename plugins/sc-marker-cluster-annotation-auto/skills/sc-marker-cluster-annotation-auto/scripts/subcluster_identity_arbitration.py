#!/usr/bin/env python3
"""Generic staged identity arbitration for subcluster annotation.

The qualitative core generates and audits candidates. This layer deliberately
separates candidate eligibility from final identity selection. Absolute gates,
state programs, and topology never receive automatic selection precedence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PASS_VALUES = {"通过", "pass", "passed", "true"}


def _passes(value):
    if value is True:
        return True
    return str(value).strip().lower() in PASS_VALUES


def _path_get(record, path, default=None):
    current = record
    for part in path or []:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _candidate_eligible(candidate):
    return bool(
        candidate
        and candidate.get("within_parent_scope") is not False
        and _passes(candidate.get("program_gate"))
    )


def _narrow(items, field, prefer_max=True):
    if not items:
        return items
    counts = [len(item.get(field, [])) for item in items]
    target = max(counts) if prefer_max else min(counts)
    return [item for item in items if len(item.get(field, [])) == target]


def _select_supported_candidate(decision, labels):
    """Select within one already-resolved side; never arbitrate between sides."""
    order = {label: index for index, label in enumerate(labels)}
    candidates = [
        item for item in decision.get("candidate_program_audits", [])
        if item.get("label") in order and _candidate_eligible(item)
    ]
    if not candidates:
        return None
    candidates = _narrow(candidates, "strong_core", True)
    candidates = _narrow(candidates, "supporting_core", True)
    candidates = _narrow(candidates, "conflicting_markers", False)
    candidates = _narrow(candidates, "supporting_supportive", True)
    return sorted(candidates, key=lambda item: (order[item["label"]], item["label"]))[0]


def _program_profile(decision, specification):
    audit = decision
    root = specification.get("audit_root", [])
    if root:
        audit = _path_get(decision, root, {})
    hits = list(_path_get(audit, specification.get("hits_path", []), []) or [])
    relative_path = specification.get("relative_hits_path", [])
    relative_hits = list(_path_get(audit, relative_path, []) or []) if relative_path else []
    mean = float(_path_get(audit, specification.get("mean_path", []), 0.0) or 0.0)
    coherent_path = specification.get("coherent_path", [])
    explicit = _path_get(audit, coherent_path, None) if coherent_path else None
    coherent = _passes(explicit) if explicit is not None else len(hits) >= int(specification.get("minimum_hits", 1))
    expected_relative = int(specification.get("expected_relative_hits", 0))
    minimum_relative = int(specification.get("minimum_relative_hits", 0))
    relative_assessed = bool(relative_path and expected_relative > 0)
    return {
        "coherent": bool(coherent),
        "hit_count": len(hits),
        "relative_hit_count": len(relative_hits),
        "relative_program_assessed": relative_assessed,
        "relative_program_coherent": bool(relative_assessed and len(relative_hits) >= minimum_relative),
        "relative_program_complete": bool(relative_assessed and len(relative_hits) >= expected_relative),
        "mean_detection": round(mean, 6),
    }


def arbitrate_program_pair(left, right, dominance):
    """Return left_dominant, right_dominant, unresolved, or insufficient."""
    if left["coherent"] and not right["coherent"]:
        return "left_dominant", "only_left_program_coherent"
    if right["coherent"] and not left["coherent"]:
        return "right_dominant", "only_right_program_coherent"
    if not left["coherent"] and not right["coherent"]:
        return "insufficient", "neither_identity_program_coherent"

    if left["relative_program_assessed"] and right["relative_program_assessed"]:
        left_complete = left["relative_program_complete"]
        right_complete = right["relative_program_complete"]
        if left_complete and right_complete:
            return "unresolved", "both_programs_relatively_complete"
        if left_complete and not right_complete:
            return "left_dominant", "left_relative_identity_program_complete"
        if right_complete and not left_complete:
            return "right_dominant", "right_relative_identity_program_complete"

    ratio = float(dominance.get("minimum_ratio", 1.25))
    margin = float(dominance.get("minimum_absolute_margin", 0.1))
    left_mean = left["mean_detection"]
    right_mean = right["mean_detection"]
    if left_mean >= right_mean * ratio and left_mean - right_mean >= margin:
        return "left_dominant", "left_program_prevalence_dominant"
    if right_mean >= left_mean * ratio and right_mean - left_mean >= margin:
        return "right_dominant", "right_program_prevalence_dominant"
    return "unresolved", "coherent_programs_without_clear_dominance"


def _replace_identity(decision, selected, rule_id, resolution, basis):
    prior = decision.get("stable_id", "")
    decision["stable_id"] = selected["label"]
    decision["suggested_identity"] = selected["label"]
    decision["primary_program"] = selected["label"]
    decision["primary_major_label"] = selected.get("major_label", decision.get("primary_major_label", ""))
    decision["parent_path"] = list(selected.get("parent_path", decision.get("parent_path", [])))
    decision["supporting_markers"] = list(selected.get("supporting_core", [])) + list(selected.get("supporting_supportive", []))
    decision["conflicting_markers"] = list(selected.get("conflicting_markers", []))
    decision["missing_markers"] = list(selected.get("missing_core_markers", []))
    decision["marker_panel_evidence_ids"] = list(selected.get("evidence_ids", []))
    decision["developmental_stage"] = selected.get("developmental_stage", decision.get("developmental_stage", ""))
    decision["panel_species"] = selected.get("panel_species", decision.get("panel_species", ""))
    decision["cross_species_inference"] = bool(selected.get("cross_species_inference", False))
    decision.setdefault("qualitative_gates", {})["sibling_competition"] = "通过"
    trace = list(decision.get("biological_precedence_trace", []))
    trace.append({
        "candidate": selected["label"],
        "compared_with": prior,
        "replace": selected["label"] != prior,
        "biological_precedence": "explicit_competing_program_arbitration",
        "rule_id": rule_id,
        "resolution": resolution,
        "basis": basis,
    })
    decision["biological_precedence_trace"] = trace


def _record_gap(decision, text):
    gaps = list(decision.get("evidence_gaps", []))
    if text not in gaps:
        gaps.append(text)
    decision["evidence_gaps"] = gaps


def _scope_matches(decision, rule):
    expected = set(rule.get("scope", {}).get("expected_parent_ids", []))
    if expected and decision.get("expected_parent_id") not in expected:
        return False
    activation = rule.get("activation", {})
    path = activation.get("path", [])
    if path and _path_get(decision, path, None) != activation.get("equals", True):
        return False
    return True


def _apply_rule(decision, rule):
    left = _program_profile(decision, rule["sides"]["left"]["program"])
    right = _program_profile(decision, rule["sides"]["right"]["program"])
    resolution, basis = arbitrate_program_pair(left, right, rule.get("dominance", {}))
    selected = None
    binding = "none"

    binding_mode = rule.get("bindings", {}).get(resolution, "dominant_side_candidate")
    if resolution in {"left_dominant", "right_dominant"} and binding_mode == "boundary_identity":
        boundary = rule.get("boundary_identity", {})
        eligible = _passes(_path_get(decision, boundary.get("eligibility_path", []), False))
        opposite_coherent = right["coherent"] if resolution == "left_dominant" else left["coherent"]
        if eligible and opposite_coherent:
            selected = _select_supported_candidate(decision, boundary.get("candidate_labels", []))
            binding = "registered_boundary_identity" if selected else "blocked_missing_eligible_boundary_candidate"
    elif resolution in {"left_dominant", "right_dominant"}:
        side = "left" if resolution == "left_dominant" else "right"
        selected = _select_supported_candidate(decision, rule["sides"][side].get("candidate_labels", []))
        binding = "dominant_side_candidate" if selected else "blocked_missing_eligible_candidate"
    elif resolution == "unresolved":
        boundary = rule.get("boundary_identity", {})
        eligible = _passes(_path_get(decision, boundary.get("eligibility_path", []), False))
        if boundary.get("when") == "coherent_without_dominance" and eligible:
            selected = _select_supported_candidate(decision, boundary.get("candidate_labels", []))
            binding = "registered_boundary_identity" if selected else "blocked_missing_eligible_boundary_candidate"

    audit = {
        "rule_id": rule.get("rule_id", ""),
        "stage": "competing_identity_program_arbitration",
        "left_program": left,
        "right_program": right,
        "resolution": resolution,
        "basis": basis,
        "binding": binding,
        "selected_candidate": selected.get("label", "") if selected else "",
        "absolute_gate_role": "eligibility_only",
        "state_role": "not_used_for_identity_selection",
        "topology_role": "post_selection_consistency_audit_only",
    }
    decision.setdefault("identity_arbitration", []).append(audit)

    if selected:
        _replace_identity(decision, selected, rule.get("rule_id", ""), resolution, basis)
        if resolution in {"left_dominant", "right_dominant"}:
            decision["auto_merge_allowed"] = False
    else:
        decision.setdefault("qualitative_gates", {})["sibling_competition"] = "未确定"
        decision["auto_merge_allowed"] = False
        _record_gap(
            decision,
            "Competing identity programs were not bindable to an eligible same-level candidate; state or topology cannot supply the missing identity program.",
        )
    return audit


def apply_subcluster_identity_arbitration(evidence, policy_path=None):
    """Apply every applicable declarative boundary rule to the evidence pack."""
    path = Path(policy_path) if policy_path else Path(__file__).resolve().parents[1] / "references" / "identity-arbitration-policy.v1.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    rules = list(policy.get("rules", []))
    policy_meta = evidence.setdefault("annotation_evidence_policy", {})
    policy_meta["subcluster_identity_arbitration"] = {
        "schema_version": policy.get("schema_version", ""),
        "rule_ids": [rule.get("rule_id", "") for rule in rules],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "stages": list(policy.get("stages", [])),
    }
    for decision in evidence.get("qualitative_annotation_evidence", {}).values():
        decision["identity_arbitration"] = []
        for rule in rules:
            if rule.get("enabled", True) and _scope_matches(decision, rule):
                _apply_rule(decision, rule)
    return evidence
