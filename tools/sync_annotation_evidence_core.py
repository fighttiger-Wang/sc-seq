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
    "annotation_override_policy.py": ("scripts", "annotation_override_policy.py"),
    "knowledge_base.py": ("scripts", "knowledge_base.py"),
    "qualitative_evidence_core.py": ("scripts", "qualitative_evidence_core.py"),
    "qualitative_gate_helpers.py": ("scripts", "qualitative_gate_helpers.py"),
    "qualitative_override_policy.py": ("scripts", "qualitative_override_policy.py"),
    "qualitative_annotation_workbook.py": ("scripts", "qualitative_annotation_workbook.py"),
    "qualitative_umap_resolution.py": ("scripts", "qualitative_umap_resolution.py"),
    "annotation-evidence-config.v1.json": ("references", "annotation-evidence-config.v1.json"),
    "evidence-scoring-policy.md": ("references", "evidence-scoring-policy.md"),
    "knowledge-base/cell-annotation-knowledge-base.v2.json": ("references", "cell-annotation-knowledge-base.v2.json"),
    "knowledge-base/legacy-migration.v2.json": ("references", "legacy-migration.v2.json"),
    "knowledge-base/knowledge-base.manifest.json": ("references", "knowledge-base.manifest.json"),
    "knowledge-base/decision-rules.v3.json": ("references", "decision-rules.v3.json"),
    "knowledge-base/naming-dictionary.v1.json": ("references", "naming-dictionary.v1.json"),
    "knowledge-base/calibration-policy.v1.json": ("references", "calibration-policy.v1.json"),
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


def synchronize(check: bool = False, skill_ids=None) -> list[dict]:
    version = canonical_version()
    shared_hashes = {name: sha256(SHARED / name) for name in FILES}
    expected_manifest = expected_snapshot(version, shared_hashes)
    results = []
    unknown = set(skill_ids or []) - {target.name for target in TARGETS}
    if unknown:
        raise ValueError(f"Unknown annotation Skill(s): {sorted(unknown)}")
    for target in TARGETS:
        if skill_ids and target.name not in skill_ids:
            continue
        if not target.is_dir():
            raise FileNotFoundError(f"Plugin skill source missing: {target}")
        manifest_path = target / "references" / "annotation-evidence-core.snapshot.json"
        existing = load_json(manifest_path) if manifest_path.is_file() else {}
        overrides = existing.get("plugin_overrides", {})
        target_manifest = {**expected_manifest, "files": dict(shared_hashes)}
        if overrides:
            # An independently released plugin can retain an explicitly hashed
            # runtime fix without silently rebuilding the other annotation Skill.
            for name, override in overrides.items():
                if name not in FILES or not override.get("reason"):
                    raise RuntimeError(f"Invalid plugin snapshot override: {target}: {name}")
                if override.get("base_sha256") != shared_hashes[name]:
                    raise RuntimeError(f"Shared base changed; review plugin override before syncing: {target}: {name}")
                folder, filename = FILES[name]
                if sha256(target / folder / filename) != override.get("sha256"):
                    raise RuntimeError(f"Plugin override hash mismatch: {target}: {name}")
                target_manifest["files"][name] = override["sha256"]
            target_manifest["plugin_overrides"] = overrides
        for source_name, (folder, destination_name) in FILES.items():
            source = SHARED / source_name
            destination = target / folder / destination_name
            if not check and source_name not in overrides:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            if not destination.is_file():
                raise FileNotFoundError(f"Vendored snapshot missing: {destination}")
            if sha256(destination) != target_manifest["files"][source_name]:
                raise RuntimeError(f"Snapshot hash mismatch: {destination}")
        if check:
            if not manifest_path.is_file():
                raise FileNotFoundError(f"Snapshot manifest missing: {manifest_path}")
            actual_manifest = load_json(manifest_path)
            if actual_manifest != target_manifest:
                raise RuntimeError(f"Snapshot manifest mismatch: {manifest_path}")
        else:
            with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(target_manifest, ensure_ascii=False, indent=2) + "\n")
        results.append({
            "status": "verified" if check else "synced",
            "target": str(target),
            "snapshot": str(manifest_path),
            "versions": version,
            "files": target_manifest["files"],
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify vendored snapshots without writing.")
    parser.add_argument("--skill", action="append", help="Limit synchronization to explicitly selected independent Skill(s).")
    args = parser.parse_args()
    for result in synchronize(check=args.check, skill_ids=args.skill):
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
