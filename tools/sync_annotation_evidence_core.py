#!/usr/bin/env python3
"""Vendor the canonical annotation evidence core into self-contained plugins."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared" / "sc-annotation-evidence-core"
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify vendored snapshots without writing.")
    args = parser.parse_args()
    version = json.loads((SHARED / "VERSION.json").read_text(encoding="utf-8"))
    shared_hashes = {name: sha256(SHARED / name) for name in FILES}
    for target in TARGETS:
        if not target.is_dir():
            raise FileNotFoundError(f"Plugin skill source missing: {target}")
        for source_name, (folder, destination_name) in FILES.items():
            destination = target / folder / destination_name
            if not args.check:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(SHARED / source_name, destination)
            if not destination.is_file():
                raise FileNotFoundError(f"Vendored snapshot missing: {destination}")
            if sha256(destination) != shared_hashes[source_name]:
                raise RuntimeError(f"Snapshot hash mismatch: {destination}")
        manifest = {
            **version,
            "canonical_source": str(SHARED),
            "files": shared_hashes,
        }
        manifest_path = target / "references" / "annotation-evidence-core.snapshot.json"
        if args.check:
            actual_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if actual_manifest != manifest:
                raise RuntimeError(f"Snapshot manifest mismatch: {manifest_path}")
        else:
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "verified" if args.check else "synced", "target": str(target), "snapshot": str(manifest_path), "files": shared_hashes}))


if __name__ == "__main__":
    main()
