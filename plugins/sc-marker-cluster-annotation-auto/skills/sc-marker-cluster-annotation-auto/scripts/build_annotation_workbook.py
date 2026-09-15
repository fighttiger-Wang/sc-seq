#!/usr/bin/env python3
"""Build the standardized qualitative subcluster annotation workbook."""

import argparse
import json
import sys
from pathlib import Path

from research_workflow import (
    complete_calibration_use,
    plugin_version,
    validate_formal_research_binding,
)
from umap_audit import load_umap_audit, validate_umap_audit


SKILL_NAME = "sc-marker-cluster-annotation-auto"
SKILL_VERSION = plugin_version(Path(__file__))


def _load_shared():
    local = Path(__file__).resolve().parent
    if (local / "qualitative_annotation_workbook.py").is_file():
        if str(local) not in sys.path:
            sys.path.insert(0, str(local))
        import qualitative_annotation_workbook as module  # noqa: WPS433
        return module
    for parent in Path(__file__).resolve().parents:
        shared = parent / "shared" / "sc-annotation-evidence-core"
        if (shared / "qualitative_annotation_workbook.py").is_file():
            if str(shared) not in sys.path:
                sys.path.insert(0, str(shared))
            import qualitative_annotation_workbook as module  # noqa: WPS433
            return module
    raise RuntimeError("Shared qualitative annotation workbook module not found")


_SHARED = _load_shared()
cluster_sort_key = _SHARED.cluster_sort_key
normalize_final_label = _SHARED.normalize_final_label
resolved_e = _SHARED.resolved_e
within = _SHARED.within
inject_qualitative_evidence = _SHARED.inject_qualitative_evidence
inject_deterministic_evidence = inject_qualitative_evidence


def _structured_list(value):
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    return []


def validate_expert_review(records):
    """Require an explicit biological review before formal delivery."""
    errors = []
    allowed = {"passed", "conditional"}
    for record in records:
        cluster = str(record.get("cluster_id", ""))
        status = str(record.get("expert_review_status", "")).strip().lower()
        basis = str(record.get("expert_review_basis", "")).strip()
        summary = str(record.get("identity_review_summary", "")).strip()
        recommendation = str(record.get("optimization_recommendations", "")).strip()
        if status not in allowed:
            errors.append(f"Cluster {cluster} requires expert_review_status=passed/conditional")
        if not basis:
            errors.append(f"Cluster {cluster} lacks expert_review_basis")
        if not summary:
            errors.append(f"Cluster {cluster} lacks identity_review_summary")
        if not recommendation:
            errors.append(f"Cluster {cluster} lacks optimization_recommendations")
        if status == "conditional" and not str(record.get("validation_advice", "")).strip():
            errors.append(f"Cluster {cluster} conditional expert review requires validation_advice")
    if errors:
        raise ValueError("\n".join(errors))


def lossy_display_conflicts(records):
    """Reject plotting labels that hide or rewrite the bound biological identity."""
    conflicts = []
    for record in records:
        stable = str(record.get("stable_id", "")).strip()
        display = str(record.get("celltype_en", "")).strip()
        allowed = {stable, f"{stable}_provisional"}
        if record.get("presentation_qualifier") == "state":
            allowed.add(f"{stable}_state_{_SHARED.normalize_final_label(record.get('state'))}")
        if stable and display not in allowed:
            conflicts.append({"stable_id": stable, "plotting_label": display})
    return sorted(conflicts, key=lambda item: (item["stable_id"], item["plotting_label"]))


def validate_candidate_semantics(evidence):
    """Reject a formal core state that passes an identity program without evidence."""
    decisions = evidence.get("qualitative_annotation_evidence", {}) or {}
    errors = []
    for cluster, decision in decisions.items():
        if not isinstance(decision, dict):
            continue
        for candidate in decision.get("candidate_program_audits", []) or []:
            if str(candidate.get("program_gate", "")) not in {"通过", "pass", "passed"}:
                continue
            # Candidate audits contain broad sibling alternatives, many of
            # which intentionally carry a permissive program flag while
            # remaining unbound.  Only an identity-eligible candidate may
            # participate in the formal semantic gate; otherwise a rejected
            # sibling can make an otherwise valid case impossible to rebuild.
            if candidate.get("identity_program_eligible") is False:
                continue
            identity_audit = candidate.get("identity_program_audit", {}) or {}
            explicit_program = bool(
                identity_audit.get("rule_id")
                and identity_audit.get("assessed")
                and identity_audit.get("passed")
            )
            if explicit_program:
                continue
            absolute_audit = candidate.get("absolute_identity_audit", {}) or {}
            if (
                absolute_audit.get("assessed") is True
                and absolute_audit.get("passed") is True
                and str(candidate.get("eligibility_basis", "")).strip()
                == "absolute_panel_identity"
            ):
                continue
            required = int(candidate.get("required_identity_anchors") or 0)
            supported_core = [
                item for item in (candidate.get("supporting_core") or [])
                if isinstance(item, dict) and item.get("review")
            ]
            if len(supported_core) < required:
                errors.append(
                    f"Cluster {cluster} candidate {candidate.get('label', '')} has "
                    f"program_gate=通过 with {len(supported_core)}/{required} supported "
                    "core markers and no applicable explicit identity program"
                )
    if errors:
        raise ValueError("\n".join(errors))
    return True


def validate(records, clusters, evidence):
    normalized = _SHARED.normalize_records(records, evidence)
    records[:] = normalized
    result = _SHARED.validate(records, clusters, evidence, annotation_level="subcluster")
    validate_expert_review(records)
    validate_candidate_semantics(evidence)
    validate_formal_research_binding(records, evidence)
    conflicts = lossy_display_conflicts(records)
    if conflicts:
        raise ValueError(f"Subcluster plotting labels hide or rewrite stable identities: {conflicts}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--umap-audit")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    workspace = _SHARED.resolved_e(args.workspace_root, "workspace root")
    records_path = _SHARED.within(_SHARED.resolved_e(args.records, "records"), workspace, "records")
    evidence_path = _SHARED.within(_SHARED.resolved_e(args.evidence, "evidence"), workspace, "evidence")
    output = _SHARED.within(_SHARED.resolved_e(args.output, "workbook output"), workspace, "workbook output")
    if output.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite existing workbook without --force: {output}")

    records = json.loads(records_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    validate_expert_review(records)
    clusters = sorted((str(item) for item in evidence.get("clusters", [])), key=cluster_sort_key)
    validate_candidate_semantics(evidence)
    validate_formal_research_binding(records, evidence)
    umap_source = str(evidence.get("source_paths", {}).get("umap", "")).strip()
    if not umap_source:
        raise ValueError("Formal subcluster delivery requires a supplied UMAP source")
    if not args.umap_audit:
        raise ValueError("Formal subcluster delivery requires --umap-audit")
    audit_path = _SHARED.within(_SHARED.resolved_e(args.umap_audit, "UMAP audit"), workspace, "UMAP audit")
    audit = load_umap_audit(audit_path)
    validated = validate_umap_audit(audit, clusters, formal=True, records=records, evidence=evidence)
    normalized_audit = {**audit, "clusters": validated["entries"]}
    qa = _SHARED.build_workbook(
        records, evidence, output, "subcluster", SKILL_NAME, SKILL_VERSION, normalized_audit
    )
    qa["open_world_research"] = evidence.get("annotation_evidence_policy", {}).get("open_world_research", {})
    qa["calibration_completion"] = complete_calibration_use(evidence)
    output.with_suffix(".qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(qa, ensure_ascii=False))
    return qa


if __name__ == "__main__":
    main()
