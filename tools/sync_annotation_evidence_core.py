#!/usr/bin/env python3
"""Synchronize and verify the canonical annotation evidence core snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared" / "sc-annotation-evidence-core"
CANONICAL_SOURCE = "shared/sc-annotation-evidence-core"
TARGETS = (
    ROOT / "plugins" / "sc-marker-cluster-annotation-auto" / "skills" / "sc-marker-cluster-annotation-auto",
    ROOT / "plugins" / "sc-major-celltype-annotation-auto" / "skills" / "sc-major-celltype-annotation-auto",
)
FILES = {
    "annotation_evidence_core.py": ("scripts", "annotation_evidence_core.py"),
    "knowledge_base.py": ("scripts", "knowledge_base.py"),
    "annotation-evidence-config.v1.json": ("references", "annotation-evidence-config.v1.json"),
    "evidence-scoring-policy.md": ("references", "evidence-scoring-policy.md"),
    "knowledge-base/cell-annotation-knowledge-base.v2.json": ("references", "cell-annotation-knowledge-base.v2.json"),
    "knowledge-base/legacy-migration.v2.json": ("references", "legacy-migration.v2.json"),
    "knowledge-base/knowledge-base.manifest.json": ("references", "knowledge-base.manifest.json"),
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_version() -> dict:
    version = load_json(SHARED / "VERSION.json")
    config = load_json(SHARED / "annotation-evidence-config.v1.json")
    knowledge = load_json(SHARED / "knowledge-base" / "cell-annotation-knowledge-base.v2.json")
    manifest = load_json(SHARED / "knowledge-base" / "knowledge-base.manifest.json")
    core_text = (SHARED / "annotation_evidence_core.py").read_text(encoding="utf-8")
    match = re.search(r'^CORE_VERSION\s*=\s*["\']([^"\']+)["\']', core_text, re.MULTILINE)
    if not match:
        raise RuntimeError("Canonical annotation_evidence_core.py does not declare CORE_VERSION")
    checks = {
        "core_version": (version.get("core_version"), match.group(1)),
        "config_version": (version.get("config_version"), config.get("config_version")),
        "knowledge_base_version": (version.get("knowledge_base_version"), knowledge.get("knowledge_base_version")),
        "manifest_knowledge_base_version": (version.get("knowledge_base_version"), manifest.get("knowledge_base_version")),
    }
    mismatches = {name: values for name, values in checks.items() if values[0] != values[1]}
    if mismatches:
        raise RuntimeError(f"Canonical annotation version mismatch: {mismatches}")
    for name, expected in manifest.get("sha256", {}).items():
        path = SHARED / "knowledge-base" / name
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"Canonical knowledge-base manifest mismatch: {path}")
    return version


def expected_snapshot(version: dict, hashes: dict[str, str]) -> dict:
    return {
        **version,
        "canonical_source": CANONICAL_SOURCE,
        "files": hashes,
    }


def synchronize(check: bool = False) -> list[dict]:
    version = canonical_version()
    shared_hashes = {name: sha256(SHARED / name) for name in FILES}
    expected_manifest = expected_snapshot(version, shared_hashes)
    results = []
    for target in TARGETS:
        if not target.is_dir():
            raise FileNotFoundError(f"Plugin skill source missing: {target}")
        for source_name, (folder, destination_name) in FILES.items():
            source = SHARED / source_name
            destination = target / folder / destination_name
            if not check:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            if not destination.is_file():
                raise FileNotFoundError(f"Vendored snapshot missing: {destination}")
            if sha256(destination) != shared_hashes[source_name]:
                raise RuntimeError(f"Snapshot hash mismatch: {destination}")
        manifest_path = target / "references" / "annotation-evidence-core.snapshot.json"
        if check:
            if not manifest_path.is_file():
                raise FileNotFoundError(f"Snapshot manifest missing: {manifest_path}")
            actual_manifest = load_json(manifest_path)
            if actual_manifest != expected_manifest:
                raise RuntimeError(f"Snapshot manifest mismatch: {manifest_path}")
        else:
            manifest_path.write_text(
                json.dumps(expected_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        results.append({
            "status": "verified" if check else "synced",
            "target": str(target),
            "snapshot": str(manifest_path),
            "versions": version,
            "files": shared_hashes,
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify vendored snapshots without writing.")
    args = parser.parse_args()
    for result in synchronize(check=args.check):
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
