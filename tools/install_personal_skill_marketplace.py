#!/usr/bin/env python3
"""Install the shared local marketplace on Windows, macOS, or Linux."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MINIMUM_PYTHON = (3, 10)


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
    if os.name == "nt":
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
        candidates.append(codex_home / "plugins" / ".plugin-appserver" / "codex.exe")
        cursor = root.resolve()
        for _ in range(7):
            candidates.append(cursor / "codex-home" / "plugins" / ".plugin-appserver" / "codex.exe")
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
    for candidate in candidates:
        path = Path(candidate).expanduser().resolve()
        if path.is_file():
            return str(path)
    raise FileNotFoundError("Codex CLI was not found. Add codex to PATH or pass --codex-cli with its full path.")


def run(
    command: list[str],
    *,
    allow_failure: bool = False,
    capture: bool = False,
    dry_run: bool = False,
    show_output: bool = True,
) -> subprocess.CompletedProcess:
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
    if capture and show_output:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr and result.returncode:
            print(result.stderr, end="", file=sys.stderr)
    if result.returncode and not allow_failure:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")
    return result


def normalized_path(value: str | Path) -> str:
    text = str(value).strip().removeprefix("\\\\?\\")
    return os.path.normcase(os.path.normpath(text))


def paths_overlap(first: Path, second: Path) -> bool:
    first_value = normalized_path(first.resolve())
    second_value = normalized_path(second.resolve())
    try:
        common = os.path.commonpath([first_value, second_value])
    except ValueError:
        return False
    return common in {first_value, second_value}


def marketplace_roots(output: str, marketplace: str) -> list[str]:
    roots = []
    pattern = re.compile(rf"^\s*{re.escape(marketplace)}\s+(.+?)\s*$", re.M)
    for match in pattern.finditer(output):
        roots.append(match.group(1).strip())
    return roots


def plugin_is_enabled(output: str, plugin_id: str, marketplace: str, version: str) -> bool:
    pattern = re.compile(
        rf"(?m)^\s*{re.escape(plugin_id)}@{re.escape(marketplace)}\s+"
        rf"installed,\s*enabled\s+{re.escape(version)}(?:\s|$)"
    )
    return bool(pattern.search(output))


def location_config_path(codex_home: Path) -> Path:
    return codex_home / "workspace-local.json"


def validate_marketplace_root(root: Path, codex_home: Path) -> Path:
    resolved = root.expanduser().resolve()
    if paths_overlap(resolved, codex_home):
        raise RuntimeError(f"Marketplace source and Codex home must not overlap: {resolved} <-> {codex_home}")
    return resolved


def validate_workspace(workspace: Path, codex_home: Path, create: bool) -> Path:
    resolved = workspace.expanduser().resolve()
    forbidden = {normalized_path(Path(resolved.anchor)), normalized_path(Path.home())}
    if normalized_path(resolved) in forbidden:
        raise RuntimeError(f"Refusing unsafe workspace root: {resolved}")
    if paths_overlap(resolved, codex_home):
        raise RuntimeError(f"Workspace and Codex home must not overlap: {resolved} <-> {codex_home}")
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def verify_location_change(config: Path, root: Path, workspace: Path, allow_replace: bool) -> None:
    if not config.is_file():
        return
    current = load_json(config)
    same = (
        normalized_path(current.get("marketplaceRoot", "")) == normalized_path(root)
        and normalized_path(current.get("workspaceRoot", "")) == normalized_path(workspace)
    )
    if not same and not allow_replace:
        raise RuntimeError(
            f"Existing location config points elsewhere: {config}. "
            "Review it and rerun with --replace-location-config only if the move is intentional."
        )


def write_location_config(config: Path, root: Path, workspace: Path) -> Path:
    atomic_json(
        config,
        {
            "schemaVersion": 1,
            "marketplaceRoot": str(root),
            "workspaceRoot": str(workspace),
        },
    )
    return config


def install(
    root: Path,
    codex_cli: str | None,
    skip_doctor: bool,
    dry_run: bool,
    skip_user_config: bool = False,
    workspace_root: Path | None = None,
    codex_home: Path | None = None,
    replace_location_config: bool = False,
    replace_marketplace_registration: bool = False,
) -> dict:
    resolved_codex_home = (codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))).expanduser().resolve()
    root = validate_marketplace_root(root, resolved_codex_home)
    pack = load_json(root / "skill-pack.json")
    config_path = location_config_path(resolved_codex_home)
    configured_workspace = None
    if workspace_root is None and config_path.is_file():
        existing = load_json(config_path)
        if normalized_path(existing.get("marketplaceRoot", "")) == normalized_path(root) and existing.get("workspaceRoot"):
            configured_workspace = Path(existing["workspaceRoot"])
    workspace = validate_workspace(workspace_root or configured_workspace or root.parent, resolved_codex_home, False)
    if not skip_user_config:
        verify_location_change(config_path, root, workspace, replace_location_config)
    if not skip_doctor:
        run([sys.executable, str(root / "tools" / "test_personal_skill_marketplace.py"), "--marketplace-root", str(root)], dry_run=dry_run)
    os.environ["CODEX_HOME"] = str(resolved_codex_home)
    codex = resolve_codex(codex_cli, root)
    if not dry_run:
        resolved_codex_home.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)
    os.environ["CODEX_SHARED_MARKETPLACE_ROOT"] = str(root)
    os.environ["CODEX_SHARED_WORKSPACE_ROOT"] = str(workspace)
    run([codex, "plugin", "marketplace", "add", str(root)], allow_failure=True, dry_run=dry_run)
    listed = run([codex, "plugin", "marketplace", "list"], capture=True, dry_run=dry_run, show_output=False)
    if not dry_run:
        roots = marketplace_roots(listed.stdout or "", str(pack["name"]))
        matching = [item for item in roots if normalized_path(item) == normalized_path(root)]
        if (len(matching) != 1 or len(roots) != 1) and replace_marketplace_registration:
            run([codex, "plugin", "marketplace", "remove", str(pack["name"])])
            run([codex, "plugin", "marketplace", "add", str(root)])
            listed = run([codex, "plugin", "marketplace", "list"], capture=True, show_output=False)
            roots = marketplace_roots(listed.stdout or "", str(pack["name"]))
            matching = [item for item in roots if normalized_path(item) == normalized_path(root)]
        if len(matching) != 1 or len(roots) != 1:
            raise RuntimeError(
                f"Marketplace '{pack['name']}' did not resolve uniquely to {root}. Reported roots: {roots or '[none]'}"
            )
    for plugin in pack.get("plugins", []):
        run([codex, "plugin", "add", f"{plugin['id']}@{pack['name']}"], dry_run=dry_run)
    plugin_list = run([codex, "plugin", "list"], capture=True, dry_run=dry_run, show_output=False)
    if not dry_run:
        missing = [
            item["id"]
            for item in pack.get("plugins", [])
            if not plugin_is_enabled(plugin_list.stdout or "", item["id"], pack["name"], item["version"])
        ]
        if missing:
            raise RuntimeError(f"Codex did not report expected enabled plugin versions: {', '.join(missing)}")
    config = None
    if not dry_run and not skip_user_config:
        config = write_location_config(config_path, root, workspace)
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
    if sys.version_info < MINIMUM_PYTHON:
        raise RuntimeError("Python 3.10 or newer is required")
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace-root", type=Path, default=ROOT)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--codex-cli")
    parser.add_argument("--skip-doctor", action="store_true")
    parser.add_argument("--skip-user-config", action="store_true")
    parser.add_argument("--replace-location-config", action="store_true")
    parser.add_argument("--replace-marketplace-registration", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    install(
        args.marketplace_root,
        args.codex_cli,
        args.skip_doctor,
        args.dry_run,
        args.skip_user_config,
        args.workspace_root,
        args.codex_home,
        args.replace_location_config,
        args.replace_marketplace_registration,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
