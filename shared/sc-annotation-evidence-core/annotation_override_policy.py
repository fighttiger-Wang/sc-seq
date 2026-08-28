#!/usr/bin/env python3
"""Shared validation for manual/external annotation identity overrides."""

from __future__ import annotations

import json
import re


OVERRIDE_METHODS = {
    "cell_level_coexpression",
    "resolving_reclustering",
    "reference_mapping",
    "quantitative_qc",
    "sample_metadata",
    "trajectory_metric",
}


def _list(value):
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            try:
                decoded = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                decoded = None
            if isinstance(decoded, list):
                return decoded
        return [item.strip() for item in re.split(r"[;,；，]", text) if item.strip()]
    return [value]


def _dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _valid_literature_details(value):
    valid = []
    source_ids = set()
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        identifier = str(item.get("doi") or item.get("pmid") or "").strip().lower()
        species = str(item.get("species", "")).strip()
        tissue = str(item.get("tissue", "")).strip()
        conclusion = str(item.get("supported_conclusion") or item.get("conclusion") or "").strip()
        if title and identifier and species and tissue and conclusion and identifier not in source_ids:
            valid.append(item)
            source_ids.add(identifier)
    return valid


def _ranked_candidate(decision, stable_id):
    for candidate in decision.get("ranked_identity_evidence", []):
        if str(candidate.get("label", "")).strip() == stable_id:
            return candidate
    return None


def _candidate_directionally_supported(candidate):
    supporting = {
        str(item.get("gene", "")).strip()
        for key in ("supporting_core", "supporting_supportive")
        for item in candidate.get(key, [])
        if isinstance(item, dict) and str(item.get("gene", "")).strip()
    }
    branch_gate = candidate.get("identity_branch_gate", {})
    absolute_gate = candidate.get("absolute_program_gate", {})
    return bool(
        len(supporting) >= 2
        or absolute_gate.get("passed") is True
        or (branch_gate.get("assessed") is True and branch_gate.get("passed") is True)
    )


def validate_identity_override(record, decision):
    """Return an auditable result; callers append ``errors`` to formal QA."""
    cluster = str(record.get("cluster_id", ""))
    stable_id = str(record.get("stable_id", "")).strip()
    deterministic_id = str(decision.get("stable_id", "")).strip()
    label_basis = str(record.get("label_basis", "")).strip()
    is_external = label_basis == "validated_external_candidate"
    is_manual_override = stable_id and deterministic_id and stable_id != deterministic_id
    applies = bool(is_external or is_manual_override)
    audit = {
        "applies": applies,
        "cluster_id": cluster,
        "label_basis": label_basis,
        "deterministic_stable_id": deterministic_id,
        "final_stable_id": stable_id,
        "status": "not_required",
        "checks": {},
        "errors": [],
    }
    if not applies:
        return audit

    errors = audit["errors"]
    supporting_markers = {
        str(item).strip().upper()
        for item in _list(record.get("supporting_markers"))
        if str(item).strip()
    }
    candidates = {
        str(item).strip()
        for item in _list(record.get("candidate_labels"))
        if str(item).strip()
    }
    literature = _valid_literature_details(record.get("literature_details"))
    validation = _dict(record.get("override_validation"))
    method = str(validation.get("method", "")).strip()
    evidence_ids = [
        str(item).strip() for item in _list(validation.get("evidence_ids")) if str(item).strip()
    ]
    supported_identity = str(validation.get("supported_identity", "")).strip()
    competing_excluded = validation.get("competing_identity_excluded")

    audit["checks"].update({
        "minimum_supporting_markers": len(supporting_markers) >= 2,
        "final_identity_listed_as_candidate": stable_id in candidates,
        "structured_literature_sources": len(literature),
        "current_case_method": method,
        "current_case_evidence_ids": evidence_ids,
        "supported_identity": supported_identity,
        "competing_identity_excluded": competing_excluded,
    })
    if len(supporting_markers) < 2:
        errors.append(f"Cluster {cluster} identity override requires at least two explicit supporting markers")
    if stable_id not in candidates:
        errors.append(f"Cluster {cluster} identity override requires final Stable_ID {stable_id} in candidate_labels")
    if is_external and len(literature) < 2:
        errors.append(
            f"Cluster {cluster} validated external candidate requires literature_details from at least two independent structured sources"
        )
    if method not in OVERRIDE_METHODS:
        errors.append(f"Cluster {cluster} identity override requires an approved current-case override_validation method")
    if not evidence_ids:
        errors.append(f"Cluster {cluster} identity override requires current-case override_validation evidence_ids")
    if supported_identity != stable_id:
        errors.append(f"Cluster {cluster} override_validation supported_identity must equal final Stable_ID {stable_id}")
    if competing_excluded in (None, "", False, [], {}):
        errors.append(f"Cluster {cluster} identity override must record how the competing identity was excluded")

    if decision.get("mixed_population"):
        errors.append(f"Cluster {cluster} identity override cannot bypass deterministic mixed-population/Multi_cell evidence")
    if decision.get("off_parent_detected") and stable_id != deterministic_id:
        errors.append(f"Cluster {cluster} identity override cannot bypass a deterministic off-parent lineage conflict")

    ranked = _ranked_candidate(decision, stable_id)
    if ranked:
        branch_gate = ranked.get("identity_branch_gate", {})
        absolute_gate = ranked.get("absolute_program_gate", {})
        if ranked.get("absolute_negative_blocked"):
            errors.append(f"Cluster {cluster} identity override cannot bypass the absolute-negative gate for {stable_id}")
        if branch_gate.get("assessed") is True and branch_gate.get("passed") is not True:
            errors.append(f"Cluster {cluster} identity override cannot bypass a failed identity-branch gate for {stable_id}")
        if absolute_gate.get("rule_id") and absolute_gate.get("assessed") is True and absolute_gate.get("passed") is not True:
            errors.append(f"Cluster {cluster} identity override cannot bypass a failed absolute program gate for {stable_id}")
        if not _candidate_directionally_supported(ranked):
            errors.append(
                f"Cluster {cluster} ranked override candidate {stable_id} lacks a directionally coherent marker/program basis"
            )

    audit["status"] = "pass" if not errors else "fail"
    return audit
