#!/usr/bin/env python3
"""Regression checks for global ancestor-descendant mapping conflicts."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    from qualitative_annotation_workbook import validate_taxonomy_depth_consistency

    mixed = [
        {"cluster_id": "2", "stable_id": "Tissue_resident_macrophage"},
        {"cluster_id": "3", "stable_id": "Macrophage"},
    ]
    mixed_errors = validate_taxonomy_depth_consistency(mixed)
    assert len(mixed_errors) == 1
    assert "ancestor/descendant" in mixed_errors[0]
    assert "cluster 3=Macrophage" in mixed_errors[0]
    assert "cluster 2=Tissue_resident_macrophage" in mixed_errors[0]

    sibling_depths = [
        {"cluster_id": "0", "stable_id": "Tissue_resident_macrophage"},
        {"cluster_id": "1", "stable_id": "Classical_monocyte"},
        {"cluster_id": "2", "stable_id": "cDC1"},
        {"cluster_id": "3", "stable_id": "Tissue_resident_macrophage"},
    ]
    assert validate_taxonomy_depth_consistency(sibling_depths) == []

    (work / "taxonomy_depth_gate.json").write_text(json.dumps({
        "status": "pass", "checks": 6,
        "blocked_pair": ["Macrophage", "Tissue_resident_macrophage"],
        "allowed_labels": ["Tissue_resident_macrophage", "Classical_monocyte", "cDC1"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "pass", "checks": 6}, ensure_ascii=False))


if __name__ == "__main__":
    main()
