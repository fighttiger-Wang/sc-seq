#!/usr/bin/env python3
"""Regression checks for the model-facing blind-test evidence contract."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from openpyxl import Workbook


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    marketplace = Path(__file__).resolve().parents[5]
    root = marketplace.parent
    prepare = marketplace / "plugins/sc-marker-cluster-annotation-auto/skills/sc-marker-cluster-annotation-auto/scripts/prepare_annotation.py"
    source = work / "fixture"
    source.mkdir(parents=True, exist_ok=True)
    (source / "avg_expr_result.txt").write_text(
        "GeneName\t0\t1\nCCR7\t2.4\t0.3\nFGFBP2\t0.2\t4.6\nTRDC\t0.4\t3.1\n",
        encoding="utf-8",
    )
    marker_book = Workbook()
    marker_sheet = marker_book.active
    marker_sheet.append(["Target_Cluster", "GeneName", "log2FC", "pct.1", "pct.2"])
    marker_sheet.append(["0", "CCR7", 1.4, 0.7, 0.2])
    marker_sheet.append(["1", "FGFBP2", 1.7, 0.7, 0.1])
    marker_sheet.append(["1", "TRDC", 1.2, 0.6, 0.1])
    marker_book.save(source / "Markergene_list.xlsx")
    (source / "umap.png").write_bytes(b"fixture")
    output = work / "blind_prepare"
    command = [
        sys.executable, str(prepare),
        "--avg", str(source / "avg_expr_result.txt"),
        "--markers", str(source / "Markergene_list.xlsx"),
        "--umap", str(source / "umap.png"),
        "--output-dir", str(output),
        "--workspace-root", str(root),
        "--species", "human", "--tissue", "fetal lung",
        "--annotation-level", "subcluster",
        "--parent-population", "T_NK_2_2", "--blind-test",
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)

    manifest = json.loads((output / "annotation_run_manifest.json").read_text(encoding="utf-8"))
    digest = json.loads((output / "annotation_evidence_digest.json").read_text(encoding="utf-8"))
    assert manifest["metadata"]["blind_test"] is True
    assert manifest["metadata"]["project_prior_clusters"] == []
    assert manifest["metadata"]["annotation_constraints"].get("by_cluster", {}) == {}
    assert digest["blind_test"] is True
    for cluster, item in digest["cluster_profiles"].items():
        qualitative = item["qualitative_evidence"]
        for key in ("stable_id", "suggested_identity", "primary_program", "primary_major_label", "decision_rationale", "recommended_action"):
            assert qualitative.get(key, "") == "", f"blind digest leaked {key} for cluster {cluster}"
        assert qualitative["candidate_program_audits"], f"candidate alternatives missing for cluster {cluster}"

    print(json.dumps({"status": "pass", "checks": 4 + len(digest["cluster_profiles"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
