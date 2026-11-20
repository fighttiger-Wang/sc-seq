#!/usr/bin/env python3
"""Atomically bump a skill's semantic version across all 4 metadata targets and cascade sync."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def compute_next_version(current_sem_ver: str, spec: str) -> str:
    spec_clean = spec.strip().lower()
    parts = [int(x) for x in current_sem_ver.split(".")]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[0], parts[1], parts[2]
    if spec_clean in {"auto", "patch"}:
        return f"{major}.{minor}.{patch + 1}"
    if spec_clean == "minor":
        return f"{major}.{minor + 1}.0"
    if spec_clean == "major":
        return f"{major + 1}.0.0"
    clean = spec.lstrip("vV").strip()
    if not re.match(r"^\d+\.\d+\.\d+$", clean):
        raise ValueError(f"Invalid version spec: {spec}. Expected auto, patch, minor, major, or X.Y.Z")
    return clean


def bump_version(skill_id: str, new_version_spec: str, dry_run: bool = False, skip_sync: bool = False) -> dict:
    plugin_dir = ROOT / "plugins" / skill_id
    if not plugin_dir.is_dir():
        raise FileNotFoundError(f"Plugin directory not found: {plugin_dir}")

    pj_path = plugin_dir / ".codex-plugin" / "plugin.json"
    pj_data = json.loads(pj_path.read_text(encoding="utf-8"))
    cur_raw_ver = str(pj_data.get("version") or "0.1.0").split("+", 1)[0].lstrip("vV")
    clean_version = compute_next_version(cur_raw_ver, new_version_spec)

    display_ver = f"v{clean_version}"
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    tech_version = f"{clean_version}+codex.{timestamp}"

    old_display = pj_data.get("interface", {}).get("displayName", "")
    match = re.match(r"^([A-Z]\d{2}|\d{2})\s*·\s*([^v]+?)(?:\s+v\d+\.\d+\.\d+.*)?$", old_display)
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
    skill_new = re.sub(r"(?m)^displayName:\s*.*$", f"displayName: {new_display}", skill_text)
    skill_new = re.sub(
        rf"(?m)^description:\s*{re.escape(order_str)}\s*·\s*[^：:\n]+?\s+v\d+\.\d+\.\d+",
        f"description: {new_display}",
        skill_new,
    )
    skill_new = re.sub(r"(?m)^#\s+([A-Z]\d{2}|\d{2})\s*·\s*[^\n]+", f"# {new_display}", skill_new, count=1)

    sp_path = ROOT / "skill-pack.json"
    sp_data = json.loads(sp_path.read_text(encoding="utf-8"))
    for pl in sp_data.get("plugins", []):
        if pl["id"] == skill_id:
            pl["version"] = tech_version
            if "displayName" in pl:
                pl["displayName"] = new_display

    if not dry_run:
        pj_path.write_text(json.dumps(pj_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        openai_path.write_text(openai_new, encoding="utf-8", newline="\n")
        skill_md_path.write_text(skill_new, encoding="utf-8", newline="\n")
        sp_path.write_text(json.dumps(sp_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

        if not skip_sync:
            setup_py = (
                ROOT
                / "plugins"
                / "personal-skill-marketplace-setup"
                / "skills"
                / "personal-skill-marketplace-setup"
                / "scripts"
                / "setup.py"
            )
            if setup_py.is_file():
                subprocess.run(
                    [sys.executable, str(setup_py), "sync-antigravity", "--marketplace-root", str(ROOT)],
                    cwd=ROOT,
                    check=True,
                )

    return {
        "status": "dry_run" if dry_run else "bumped",
        "skill_id": skill_id,
        "previous_version": cur_raw_ver,
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
    parser.add_argument("new_version", nargs="?", default="auto", help="auto, patch, minor, major, or X.Y.Z")
    parser.add_argument("--dry-run", action="store_true", help="Test without writing")
    parser.add_argument("--skip-sync", action="store_true", help="Skip automatic setup.py sync-antigravity")
    args = parser.parse_args()
    result = bump_version(args.skill_id, args.new_version, args.dry_run, args.skip_sync)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
