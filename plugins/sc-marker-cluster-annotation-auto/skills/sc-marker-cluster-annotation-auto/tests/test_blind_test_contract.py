#!/usr/bin/env python3
"""Regression checks for the model-facing blind-test evidence contract."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    marketplace = Path(__file__).resolve().parents[5]
    root = marketplace.parent
    prepare = marketplace / "plugins/sc-marker-cluster-annotation-auto/skills/sc-marker-cluster-annotation-auto/scripts/prepare_annotation.py"
    source = Path(r"E:\Desktop\售后\N135-郭致远-人-胎肺\2-替换样本后\N002-亚群注释\测试\T_NK_2_2")
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
