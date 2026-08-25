#!/usr/bin/env python3
"""Install the shared local marketplace on Windows, macOS, or Linux."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def resolve_codex(explicit: str | None, root: Path) -> str:
    candidates: list[Path | str] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    discovered = shutil.which("codex")
    if discovered and "WindowsApps" not in discovered:
        candidates.append(discovered)
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    candidates.extend(
        [
            codex_home / "plugins" / ".plugin-appserver" / ("codex.exe" if os.name == "nt" else "codex"),
        ]
    )
    cursor = root.resolve()
    for _ in range(7):
        candidates.append(cursor / "codex-home" / "plugins" / ".plugin-appserver" / ("codex.exe" if os.name == "nt" else "codex"))
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    for candidate in candidates:
        path = Path(candidate).expanduser().resolve()
        if path.is_file():
            return str(path)
    raise FileNotFoundError("Codex CLI was not found. Add codex to PATH or pass --codex-cli with its full path.")


def run(command: list[str], *, allow_failure: bool = False, capture: bool = False, dry_run: bool = False) -> subprocess.CompletedProcess:
    print("+", " ".join(command))
    if dry_run:
        return subprocess.CompletedProcess(command, 0, "", "")
    result = subprocess.run(
        command,
        text=True,
        capture_output=capture,
        encoding="utf-8" if capture else None,
        errors="replace" if capture else None,
    )
    if capture:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr and result.returncode:
            print(result.stderr, end="", file=sys.stderr)
    if result.returncode and not allow_failure:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")
    return result


def write_location_config(root: Path, workspace: Path) -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    config = codex_home / "workspace-local.json"
    atomic_json(
        config,
        {
            "schemaVersion": 1,
            "marketplaceRoot": str(root),
            "workspaceRoot": str(workspace),
        },
    )
    return config


def install(root: Path, codex_cli: str | None, skip_doctor: bool, dry_run: bool, skip_user_config: bool = False) -> dict:
    root = root.resolve()
    pack = load_json(root / "skill-pack.json")
    if not skip_doctor:
        run([sys.executable, str(root / "tools" / "test_personal_skill_marketplace.py"), "--marketplace-root", str(root)], dry_run=dry_run)
    codex = resolve_codex(codex_cli, root)
    workspace = root.parent
    os.environ["CODEX_SHARED_MARKETPLACE_ROOT"] = str(root)
    os.environ["CODEX_SHARED_WORKSPACE_ROOT"] = str(workspace)
    config = None if dry_run or skip_user_config else write_location_config(root, workspace)
    run([codex, "plugin", "marketplace", "add", str(root)], allow_failure=True, dry_run=dry_run)
    listed = run([codex, "plugin", "marketplace", "list"], capture=True, dry_run=dry_run)
    if not dry_run and str(pack["name"]) not in (listed.stdout or ""):
        raise RuntimeError(f"Marketplace '{pack['name']}' was not visible after registration")
    for plugin in pack.get("plugins", []):
        run([codex, "plugin", "add", f"{plugin['id']}@{pack['name']}"], dry_run=dry_run)
    plugin_list = run([codex, "plugin", "list"], capture=True, dry_run=dry_run)
    if not dry_run:
        missing = [item["id"] for item in pack.get("plugins", []) if item["id"] not in (plugin_list.stdout or "")]
        if missing:
            raise RuntimeError(f"Codex did not report installed plugins: {', '.join(missing)}")
    result = {
        "status": "dry-run" if dry_run else "installed",
        "marketplace": pack["name"],
        "plugin_count": len(pack.get("plugins", [])),
        "codex_cli": codex,
        "location_config": str(config) if config else None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace-root", type=Path, default=ROOT)
    parser.add_argument("--codex-cli")
    parser.add_argument("--skip-doctor", action="store_true")
    parser.add_argument("--skip-user-config", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    install(args.marketplace_root, args.codex_cli, args.skip_doctor, args.dry_run, args.skip_user_config)


if __name__ == "__main__":
    main()
