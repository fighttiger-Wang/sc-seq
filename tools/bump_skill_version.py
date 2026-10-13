#!/usr/bin/env python3
"""Atomically bump a skill's semantic version across all 4 metadata targets."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def bump_version(skill_id: str, new_version: str, dry_run: bool = False) -> dict:
    clean_version = new_version.lstrip("v").strip()
    if not re.match(r"^\d+\.\d+\.\d+$", clean_version):
        raise ValueError(f"Invalid semantic version format: {new_version}. Expected X.Y.Z")
    display_ver = f"v{clean_version}"
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    tech_version = f"{clean_version}+codex.{timestamp}"

    plugin_dir = ROOT / "plugins" / skill_id
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"Plugin directory not found: {plugin_dir}")

    pj_path = plugin_dir / ".codex-plugin" / "plugin.json"
    pj_data = json.loads(pj_path.read_text(encoding="utf-8"))
    old_display = pj_data.get("interface", {}).get("displayName", "")
    match = re.match(r"^(\d{2})\s*·\s*([^v]+?)(?:\s+v\d+\.\d+\.\d+.*)?$", old_display)
    if not match:
        raise ValueError(f"Could not parse display name: {old_display}")
    order_str, chinese_name = match.group(1), match.group(2).strip()
    new_display = f"{order_str} · {chinese_name} {display_ver}"

    pj_data["version"] = tech_version
    pj_data.setdefault("interface", {})["displayName"] = new_display

    openai_path = plugin_dir / "skills" / skill_id / "agents" / "openai.yaml"
    openai_text = openai_path.read_text(encoding="utf-8")
    openai_new = re.sub(r'display_name:\s*"[^"]*"', f'display_name: "{new_display}"', openai_text)

    skill_md_path = plugin_dir / "skills" / skill_id / "SKILL.md"
    skill_text = skill_md_path.read_text(encoding="utf-8")
    skill_new = re.sub(r"displayName:\s*.*", f"displayName: {new_display}", skill_text)
    skill_new = re.sub(r"#\s+\d{2}\s*·\s*[^\n]+", f"# {new_display}", skill_new, count=1)

    sp_path = ROOT / "skill-pack.json"
    sp_data = json.loads(sp_path.read_text(encoding="utf-8"))
    for pl in sp_data.get("plugins", []):
        if pl["id"] == skill_id:
            pl["version"] = tech_version

    if not dry_run:
        pj_path.write_text(json.dumps(pj_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        openai_path.write_text(openai_new, encoding="utf-8")
        skill_md_path.write_text(skill_new, encoding="utf-8")
        sp_path.write_text(json.dumps(sp_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "dry_run" if dry_run else "bumped",
        "skill_id": skill_id,
        "new_semantic_version": clean_version,
        "technical_version": tech_version,
        "display_name": new_display,
        "updated_files": [
            str(pj_path),
            str(openai_path),
            str(skill_md_path),
            str(sp_path),
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Bump skill version atomically")
    parser.add_argument("skill_id", help="Plugin/Skill ID, e.g. skill-writing")
    parser.add_argument("new_version", help="New semantic version, e.g. 0.3.3 or v0.3.3")
    parser.add_argument("--dry-run", action="store_true", help="Test without writing")
    args = parser.parse_args()
    result = bump_version(args.skill_id, args.new_version, args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
