#!/usr/bin/env python3
"""Rebuild the canonical annotation knowledge-base bundle and manifest."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared" / "sc-annotation-evidence-core"
KB = SHARED / "knowledge-base"
MONOLITH = KB / "cell-annotation-knowledge-base.v2.json"
MANIFEST = KB / "knowledge-base.manifest.json"
VERSION = SHARED / "VERSION.json"
SECTIONS = {
    "ontology": "ontology.v2.json",
    "aliases": "aliases.v2.json",
    "marker_panels": "marker-panels.v2.json",
    "tissue_modules": "tissue-modules.v2.json",
    "state_rules": "state-rules.v2.json",
    "decision_rules": "decision-rules.v2.json",
    "evidence_sources": "evidence-sources.v2.json",
    "legacy_migration": "legacy-migration.v2.json",
}
SUPPLEMENTARY = {
    "annotation_decision_rules": "decision-rules.v3.json",
    "naming_dictionary": "naming-dictionary.v1.json",
    "calibration_policy": "calibration-policy.v1.json",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rebuild() -> dict:
    version = load(VERSION)
    bundle = load(MONOLITH)
    bundle["schema_version"] = "2.0.0"
    bundle["knowledge_base_version"] = version["knowledge_base_version"]
    for section, filename in SECTIONS.items():
        value = load(KB / filename)
        if not isinstance(value, list):
            raise ValueError(f"Knowledge-base section must be a JSON array: {filename}")
        bundle[section] = value
    for section, filename in SUPPLEMENTARY.items():
        bundle[section] = load(KB / filename)
    atomic_json(MONOLITH, bundle)

    files = ["cell-annotation-knowledge-base.v2.json", *SECTIONS.values(), *SUPPLEMENTARY.values()]
    hashes = {filename: sha256(KB / filename) for filename in files}
    previous_manifest = load(MANIFEST) if MANIFEST.is_file() else {}
    source_workbook = str(previous_manifest.get("source_workbook") or "").replace("\\", "/")
    manifest = {
        "schema_version": "2.0.0",
        "approved_at": bundle.get("approved_at", previous_manifest.get("approved_at", "")),
        "source": "shared/sc-annotation-evidence-core/knowledge-base",
        "source_workbook": Path(source_workbook).name if source_workbook else "",
        "counts": {
            "ontology_nodes": len(bundle["ontology"]),
            "alias_records": len(bundle["aliases"]),
            "marker_panels": len(bundle["marker_panels"]),
            "tissue_modules": len(bundle["tissue_modules"]),
            "state_rules": len(bundle["state_rules"]),
            "decision_rules": len(bundle["decision_rules"]),
            "evidence_sources": len(bundle["evidence_sources"]),
            "legacy_migrations": len(bundle["legacy_migration"]),
            "annotation_decision_rules": 1,
            "naming_dictionary": 1,
            "calibration_policy": 1,
        },
        "sha256": hashes,
        "knowledge_base_version": version["knowledge_base_version"],
    }
    atomic_json(MANIFEST, manifest)
    return {"status": "rebuilt", "version": version, "counts": manifest["counts"], "sha256": hashes}


def main() -> None:
    print(json.dumps(rebuild(), ensure_ascii=False))


if __name__ == "__main__":
    main()
