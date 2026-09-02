#!/usr/bin/env python3
"""Validation for qualitative manual or literature-supported identity overrides."""

import re


def _items(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [item.strip() for item in re.split(r"[;,；、]", str(value)) if item.strip()]


def validate_identity_override(record, decision):
    basis = str(record.get("label_basis", "canonical_subtype"))
    audit = {"status": "not_required", "errors": [], "qualitative_only": True}
    if basis != "validated_external_candidate":
        return audit
    audit["status"] = "assessed"
    final_id = str(record.get("stable_id") or record.get("celltype_en") or "").strip()
    supporting = _items(record.get("supporting_markers"))
    candidates = _items(record.get("candidate_labels"))
    literature = record.get("literature_details") or []
    validation = record.get("override_validation") or {}
    if len(supporting) < 2:
        audit["errors"].append("External identity requires at least two explicit supporting Markers")
    if final_id not in candidates:
        audit["errors"].append("External identity must be present in candidate_labels")
    if not isinstance(literature, list) or len(literature) < 2:
        audit["errors"].append("External identity requires at least two independent structured sources")
    for field in ("method", "evidence_ids", "supported_identity", "competing_identity_excluded"):
        if not validation.get(field):
            audit["errors"].append(f"override_validation lacks {field}")
    if validation.get("supported_identity") and str(validation["supported_identity"]) != final_id:
        audit["errors"].append("override_validation.supported_identity does not match the final identity")
    gates = decision.get("qualitative_gates", {})
    if gates.get("exclusion") == "不通过" or gates.get("identity_anchor") == "不通过":
        audit["errors"].append("External identity cannot bypass a failed identity or exclusion gate")
    if decision.get("mixed_population") and final_id != "Multi_cell":
        audit["errors"].append("External identity cannot bypass a cell-level confirmed mixed population")
    audit["status"] = "pass" if not audit["errors"] else "fail"
    return audit
