#!/usr/bin/env python3
"""Import an approved runtime knowledge base and synchronize plugin snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import rebuild_annotation_knowledge_base as rebuild_tool
import sync_annotation_evidence_core as sync_tool


ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared" / "sc-annotation-evidence-core"
KB = SHARED / "knowledge-base"
VERSION_PATH = SHARED / "VERSION.json"
MONOLITH = KB / "cell-annotation-knowledge-base.v2.json"
SECTIONS = rebuild_tool.SECTIONS
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def discover_workspace_root() -> Path:
    configured = os.environ.get("CODEX_SHARED_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return ROOT.parent


def default_source() -> Path:
    runtime = discover_workspace_root() / ".sc-annotation-knowledge" / "published" / "current" / MONOLITH.name
    return runtime if runtime.is_file() else MONOLITH


def validate_bundle(bundle: dict, source: Path) -> None:
    if bundle.get("schema_version") != "2.0.0":
        raise ValueError(f"Unsupported knowledge-base schema in {source}: {bundle.get('schema_version')}")
    version = str(bundle.get("knowledge_base_version") or "")
    if not SEMVER.fullmatch(version):
        raise ValueError(f"Invalid knowledge_base_version in {source}: {version}")
    for section in SECTIONS:
        if not isinstance(bundle.get(section), list):
            raise ValueError(f"Missing or invalid knowledge-base section '{section}' in {source}")
    if not bundle["ontology"] or not bundle["marker_panels"]:
        raise ValueError("Knowledge base must contain ontology and marker panels")


def affected_paths() -> list[Path]:
    paths = [VERSION_PATH, MONOLITH, KB / "knowledge-base.manifest.json"]
    paths.extend(KB / filename for filename in SECTIONS.values())
    for target in sync_tool.TARGETS:
        paths.append(target / "references" / "annotation-evidence-core.snapshot.json")
        for _, (folder, destination_name) in sync_tool.FILES.items():
            paths.append(target / folder / destination_name)
    return paths


def backup_files(destination: Path) -> int:
    count = 0
    for source in affected_paths():
        if not source.is_file():
            continue
        relative = source.relative_to(ROOT)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        count += 1
    return count


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_current() -> dict:
    version = sync_tool.canonical_version()
    snapshots = sync_tool.synchronize(check=True)
    return {"status": "verified", "versions": version, "snapshots": len(snapshots)}


def release(source: Path, backup_root: Path | None = None) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Approved knowledge base not found: {source}")
    bundle = load_json(source)
    validate_bundle(bundle, source)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = backup_root or (ROOT / "tmp" / "annotation-knowledge-releases" / stamp)
    backup_count = backup_files(backup_root)

    canonical = dict(bundle)
    atomic_json(MONOLITH, canonical)
    for section, filename in SECTIONS.items():
        atomic_json(KB / filename, canonical[section])
    version = load_json(VERSION_PATH)
    version["knowledge_base_version"] = canonical["knowledge_base_version"]
    atomic_json(VERSION_PATH, version)

    rebuilt = rebuild_tool.rebuild()
    snapshots = sync_tool.synchronize(check=False)
    verified = validate_current()
    return {
        "status": "released",
        "source": str(source),
        "knowledge_base_version": canonical["knowledge_base_version"],
        "backup": str(backup_root),
        "backup_files": backup_count,
        "rebuilt": rebuilt,
        "synced_snapshots": len(snapshots),
        "verification": verified,
    }


def publish_runtime() -> dict:
    validation = validate_current()
    bundle = load_json(MONOLITH)
    validate_bundle(bundle, MONOLITH)
    workspace = discover_workspace_root()
    published = workspace / ".sc-annotation-knowledge" / "published"
    version = str(bundle["knowledge_base_version"])
    current = published / "current" / MONOLITH.name
    snapshot = published / "versions" / version / MONOLITH.name
    if snapshot.is_file() and sha256(snapshot) != sha256(MONOLITH):
        raise RuntimeError(f"Runtime version snapshot already exists with different content: {snapshot}")
    atomic_json(snapshot, bundle)
    atomic_json(current, bundle)
    manifest = {
        "status": "repository_release",
        "knowledge_base_version": version,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "sha256": sha256(current),
        "source": "shared/sc-annotation-evidence-core/knowledge-base/cell-annotation-knowledge-base.v2.json",
        "snapshot": str(snapshot),
    }
    atomic_json(current.with_name("publication-manifest.json"), manifest)
    return {"status": "published_runtime", "workspace": str(workspace), "manifest": manifest, "verification": validation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=default_source())
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--check", action="store_true", help="Verify canonical and vendored copies without writing.")
    parser.add_argument("--publish-runtime", action="store_true", help="Publish the verified repository snapshot to the local runtime store.")
    args = parser.parse_args()
    if args.check and args.publish_runtime:
        parser.error("--check and --publish-runtime are mutually exclusive")
    result = validate_current() if args.check else publish_runtime() if args.publish_runtime else release(args.source, args.backup_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
