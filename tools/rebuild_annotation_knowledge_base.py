#!/usr/bin/env python3
"""Rebuild the canonical annotation knowledge-base bundle and integrity manifest."""

import hashlib
import json
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


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    version = load(VERSION)
    bundle = load(MONOLITH)
    bundle["schema_version"] = "2.0.0"
    bundle["knowledge_base_version"] = version["knowledge_base_version"]
    bundle["approved_at"] = "2026-08-16"
    for section, filename in SECTIONS.items():
        bundle[section] = load(KB / filename)
    MONOLITH.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    files = ["cell-annotation-knowledge-base.v2.json", *SECTIONS.values()]
    hashes = {filename: sha256(KB / filename) for filename in files}
    manifest = load(MANIFEST)
    manifest["schema_version"] = "2.0.0"
    manifest["knowledge_base_version"] = version["knowledge_base_version"]
    manifest["approved_at"] = "2026-08-16"
    manifest["counts"] = {
        "ontology_nodes": len(bundle["ontology"]),
        "alias_records": len(bundle["aliases"]),
        "marker_panels": len(bundle["marker_panels"]),
        "tissue_modules": len(bundle["tissue_modules"]),
        "state_rules": len(bundle["state_rules"]),
        "decision_rules": len(bundle["decision_rules"]),
        "evidence_sources": len(bundle["evidence_sources"]),
        "legacy_migrations": len(bundle["legacy_migration"]),
    }
    manifest["sha256"] = hashes
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "rebuilt", "version": version, "counts": manifest["counts"], "sha256": hashes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
