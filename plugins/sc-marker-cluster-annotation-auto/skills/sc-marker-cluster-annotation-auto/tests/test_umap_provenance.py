#!/usr/bin/env python3
"""Regression tests for image-bound, fail-closed UMAP auditing."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve()
for parent in ROOT.parents:
    shared = parent / "shared" / "sc-annotation-evidence-core"
    if (shared / "umap_facts.py").is_file():
        sys.path.insert(0, str(shared))
        break
sys.path.insert(0, str(ROOT.parent.parent / "scripts"))

import umap_facts
import umap_image_facts
import umap_audit


def _audit_entry(cluster, nearest, label, peers, relation="concordant", topology="not_applicable"):
    return {
        "reviewed": True,
        "topology_summary": f"Independent geometry reviewed for cluster {cluster}",
        "nearest_clusters": nearest,
        "marker_umap_relation": relation,
        "research_required": False,
        "research_status": "not_required",
        "conflict_resolution_basis": "none",
        "evidence_ids": [],
        "review_action": "retain",
        "identity_action": "retain",
        "provisional_label": label,
        "resolved_label": label,
        "same_label_clusters": peers,
        "same_label_topology": topology,
        "separation_explanation": "none",
        "separation_evidence": "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    work = Path(parser.parse_args().work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    image_path = work / "umap.png"
    image = Image.new("RGB", (40, 40), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 5, 5), fill=(242, 156, 43))
    draw.rectangle((6, 2, 9, 5), fill=(70, 149, 214))
    draw.rectangle((28, 28, 31, 31), fill=(234, 112, 112))
    image.save(image_path)
    colors = {"13": [242, 156, 43], "16": [70, 149, 214], "0": [234, 112, 112]}
    facts = umap_image_facts.generate(image_path, colors, (0, 0, 40, 40), nearest_k=2, adjacency_px=1)
    facts_path = work / "umap_facts.json"
    facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    assert not umap_facts.validate_umap_facts(facts, ["0", "13", "16"], image_path, facts_path)

    records = [
        {"cluster_id": "0", "stable_id": "Fibroblast", "celltype_en": "Fibroblast", "label_basis": "registered"},
        {"cluster_id": "13", "stable_id": "Fibroblast", "celltype_en": "Fibroblast", "label_basis": "registered"},
        {"cluster_id": "16", "stable_id": "Mesothelial_cell", "celltype_en": "Mesothelial_cell", "label_basis": "registered"},
    ]
    evidence = {
        "confirmed_metadata": {"parent_population": "Stromal_cell"},
        "qualitative_annotation_evidence": {
            str(cluster): {"research_required": False}
            for cluster in ("0", "13", "16")
        },
    }
    entries = {}
    for cluster, record in ((item["cluster_id"], item) for item in records):
        entries[cluster] = _audit_entry(
            cluster,
            facts["clusters"][cluster]["nearest_clusters"],
            record["stable_id"],
            [peer["cluster_id"] for peer in records if peer["cluster_id"] != cluster and peer["stable_id"] == record["stable_id"]],
            topology="adjacent" if cluster == "13" else "disconnected" if cluster == "0" else "not_applicable",
        )
    audit = {"schema_version": "1.0.0", "clusters": entries}
    try:
        umap_audit.validate_umap_audit(
            audit, ["0", "13", "16"], formal=True, records=records,
            evidence=evidence, facts=facts, image_path=image_path, facts_path=facts_path,
        )
    except ValueError as error:
        message = str(error)
        assert "same_label_topology" in message or "cannot be concordant" in message
    else:
        raise AssertionError("Contradictory same-label geometry was accepted")

    try:
        umap_audit.validate_umap_audit(audit, ["0", "13", "16"], formal=True, records=records, evidence=evidence)
    except ValueError as error:
        assert "requires an independent UMAP facts artifact" in str(error)
    else:
        raise AssertionError("Formal audit without geometry facts was accepted")
    print("umap provenance and contradictory-topology regression: pass")


if __name__ == "__main__":
    main()
