#!/usr/bin/env python3
"""Synchronize skill-pack versions from the canonical plugin manifests."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "skill-pack.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def synchronize(check: bool = False) -> dict:
    pack = load_json(PACK)
    mismatches = []
    for entry in pack.get("plugins", []):
        plugin_id = str(entry["id"])
        manifest_path = ROOT / "plugins" / plugin_id / ".codex-plugin" / "plugin.json"
        manifest = load_json(manifest_path)
        actual = str(manifest.get("version") or "")
        expected = str(entry.get("version") or "")
        if actual != expected:
            mismatches.append({"id": plugin_id, "skill_pack": expected, "plugin_manifest": actual})
            if not check:
                entry["version"] = actual
    if check and mismatches:
        raise RuntimeError(f"skill-pack version mismatch: {mismatches}")
    if not check and mismatches:
        atomic_json(PACK, pack)
    return {"status": "verified" if check else "synchronized", "changes": mismatches}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(synchronize(check=args.check), ensure_ascii=False))


if __name__ == "__main__":
    main()
