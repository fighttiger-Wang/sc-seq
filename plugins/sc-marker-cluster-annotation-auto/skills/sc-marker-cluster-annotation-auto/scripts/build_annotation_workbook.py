#!/usr/bin/env python3
"""Build the standardized qualitative subcluster annotation workbook."""

import argparse
import json
import sys
from pathlib import Path

from umap_audit import load_umap_audit, validate_umap_audit


SKILL_NAME = "sc-marker-cluster-annotation-auto"
SKILL_VERSION = "0.6.3"


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


def hierarchy_depth_conflicts(records):
    def allowed_multi_cell(record):
        return str(record.get("stable_id", "")) == "Multi_cell" and not bool(record.get("auto_merge_allowed", True))

    labels = {str(item.get("stable_id", "")) for item in records if item.get("stable_id") and not allowed_multi_cell(item)}
    conflicts = []
    for record in records:
        if allowed_multi_cell(record):
            continue
        child = str(record.get("stable_id", ""))
        for ancestor in _structured_list(record.get("parent_path", []))[:-1]:
            if ancestor in labels:
                conflicts.append({"ancestor": ancestor, "descendant": child})
    return sorted(conflicts, key=lambda item: (item["ancestor"], item["descendant"]))


def validate(records, clusters, evidence):
    normalized = _SHARED.normalize_records(records, evidence)
    records[:] = normalized
    result = _SHARED.validate(records, clusters, evidence, annotation_level="subcluster")
    conflicts = hierarchy_depth_conflicts(records)
    if conflicts:
        raise ValueError(f"Subcluster table mixes ancestor and descendant identities: {conflicts}")
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
    clusters = sorted((str(item) for item in evidence.get("clusters", [])), key=cluster_sort_key)
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
    output.with_suffix(".qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(qa, ensure_ascii=False))
    return qa


if __name__ == "__main__":
    main()
