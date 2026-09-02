#!/usr/bin/env python3
"""Build a temporary two-column cluster-to-suggested-celltype mapping."""

import argparse
import csv
import json
from pathlib import Path

from build_annotation_workbook import cluster_sort_key, resolved_e, within
from umap_audit import apply_umap_audit, load_umap_audit, validate_umap_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--umap-audit")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    workspace = resolved_e(args.workspace_root, "workspace root")
    records_path = within(resolved_e(args.records, "records"), workspace, "records")
    evidence_path = within(resolved_e(args.evidence, "evidence"), workspace, "evidence")
    output = within(resolved_e(args.output, "temporary mapping output"), workspace, "temporary mapping output")
    if output.exists() and not args.force:
        raise FileExistsError(f"Refusing to overwrite without --force: {output}")

    records = json.loads(records_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    expected = sorted((str(cluster) for cluster in evidence["clusters"]), key=cluster_sort_key)
    by_cluster = {str(record.get("cluster_id", "")): record for record in records}
    if sorted(by_cluster, key=cluster_sort_key) != expected:
        raise ValueError("Temporary mapping records do not cover the evidence cluster set exactly")

    umap_source = str(evidence.get("source_paths", {}).get("umap", "")).strip()
    audit_summary = None
    if umap_source:
        if not args.umap_audit:
            raise ValueError("UMAP was supplied; all-cluster --umap-audit is required before temporary mapping")
        audit_path = within(resolved_e(args.umap_audit, "UMAP audit"), workspace, "UMAP audit")
        audit_summary = validate_umap_audit(
            load_umap_audit(audit_path), expected, formal=False, records=records, evidence=evidence
        )
        apply_umap_audit(records, audit_summary)
        by_cluster = {str(record.get("cluster_id", "")): record for record in records}

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["cluster", "suggested_cell_type"])
        for cluster in expected:
            record = by_cluster[cluster]
            label = str(record.get("celltype_en") or record.get("display_label") or record.get("stable_id") or "").strip()
            if not label:
                raise ValueError(f"Cluster {cluster} lacks a suggested cell type")
            writer.writerow([cluster, label])

    qa = {
        "status": "temporary",
        "formal_delivery_blocked": True,
        "reason": "skill_regression_or_publication_pending" if umap_source else "missing_umap",
        "umap_supplied": bool(umap_source),
        "umap_all_clusters_reviewed": bool(audit_summary),
        "cluster_count": len(expected),
    }
    output.with_suffix(output.suffix + ".qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({**qa, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
