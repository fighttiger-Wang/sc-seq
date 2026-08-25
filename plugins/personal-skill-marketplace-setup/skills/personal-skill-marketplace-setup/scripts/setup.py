#!/usr/bin/env python3
"""Cross-platform bootstrap and lifecycle manager for workspace-local skills."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_REPOSITORY = "https://github.com/fighttiger-Wang/sc-seq.git"
MARKETPLACE_NAME = "workspace-local"
MINIMUM_PYTHON = (3, 10)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def is_marketplace(path: Path) -> bool:
    return (path / "skill-pack.json").is_file() and (path / "tools" / "install_personal_skill_marketplace.py").is_file()


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


def normalized_repository(value: str) -> str:
    text = value.strip().rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    ssh_match = re.fullmatch(r"git@([^:]+):(.+)", text)
    if ssh_match:
        text = f"{ssh_match.group(1)}/{ssh_match.group(2)}"
    text = re.sub(r"^(?:https?|ssh)://(?:git@)?", "", text, flags=re.I)
    return text.lower()


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    dry_run: bool = False,
    show_output: bool = True,
):
    print("+", " ".join(command), flush=True)
    if dry_run:
        return subprocess.CompletedProcess(command, 0, "", "")
    result = subprocess.run(
        command,
        cwd=cwd,
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
    if result.returncode:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")
    return result


def resolve_codex_home(explicit: Path | None) -> Path:
    return (explicit or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))).expanduser().resolve()


def configured_marketplace(codex_home: Path) -> Path | None:
    marker = codex_home / "workspace-local.json"
    if not marker.is_file():
        return None
    value = load_json(marker).get("marketplaceRoot")
    return Path(value).expanduser().resolve() if value else None


def configured_workspace(codex_home: Path, root: Path) -> Path | None:
    marker = codex_home / "workspace-local.json"
    if not marker.is_file():
        return None
    value = load_json(marker)
    if normalized_path(value.get("marketplaceRoot", "")) != normalized_path(root):
        return None
    workspace = value.get("workspaceRoot")
    return Path(workspace).expanduser().resolve() if workspace else None


def locate_marketplace(explicit: Path | None, codex_home: Path, allow_explicit_conflict: bool = False) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        resolved_explicit = explicit.expanduser().resolve()
        if not is_marketplace(resolved_explicit):
            raise FileNotFoundError(f"The explicit marketplace root is invalid: {resolved_explicit}")
        if allow_explicit_conflict:
            return resolved_explicit
        candidates.append(resolved_explicit)
    configured = os.environ.get("CODEX_SHARED_MARKETPLACE_ROOT")
    if configured:
        candidates.append(Path(configured).expanduser())
    marker_root = configured_marketplace(codex_home)
    if marker_root:
        candidates.append(marker_root)
    for start in (Path.cwd(), Path(__file__).resolve()):
        cursor = start if start.is_dir() else start.parent
        candidates.extend([cursor, *cursor.parents])
    valid = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if is_marketplace(resolved) and all(normalized_path(resolved) != normalized_path(item) for item in valid):
            valid.append(resolved)
    if len(valid) > 1:
        raise RuntimeError(f"Multiple marketplace roots were found: {[str(item) for item in valid]}")
    return valid[0] if valid else None


def require_git() -> str:
    git = shutil.which("git")
    if not git:
        raise FileNotFoundError("Git was not found in PATH. Install Git separately or provide an existing downloaded ZIP checkout.")
    return git


def git_facts(root: Path, expected_repository: str) -> dict:
    if not (root / ".git").exists():
        return {"git": False, "remote": None, "branch": None, "commit": None, "dirty": None}
    git = require_git()
    remote = run([git, "remote", "get-url", "origin"], cwd=root, capture=True, show_output=False).stdout.strip()
    if normalized_repository(remote) != normalized_repository(expected_repository):
        raise RuntimeError(f"Repository remote mismatch. Expected {expected_repository}; found {remote}")
    branch_result = subprocess.run([git, "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=root, text=True, capture_output=True, encoding="utf-8", errors="replace")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    commit = run([git, "rev-parse", "HEAD"], cwd=root, capture=True, show_output=False).stdout.strip()
    dirty = bool(run([git, "status", "--porcelain"], cwd=root, capture=True, show_output=False).stdout.strip())
    return {"git": True, "remote": remote, "branch": branch, "commit": commit, "dirty": dirty}


def safe_clone_destination(destination: Path, codex_home: Path) -> Path:
    resolved = destination.expanduser().resolve()
    forbidden = {normalized_path(Path(resolved.anchor)), normalized_path(Path.home())}
    if normalized_path(resolved) in forbidden:
        raise RuntimeError(f"Refusing unsafe clone destination: {resolved}")
    if paths_overlap(resolved, codex_home):
        raise RuntimeError(f"Clone destination and Codex home must not overlap: {resolved} <-> {codex_home}")
    if resolved.exists() and any(resolved.iterdir()):
        if is_marketplace(resolved):
            raise RuntimeError(f"Clone destination already contains a marketplace; use --marketplace-root instead: {resolved}")
        raise RuntimeError(f"Clone destination exists and is not empty: {resolved}")
    return resolved


def clone_repository(destination: Path, repository: str, ref: str | None, codex_home: Path, dry_run: bool) -> Path:
    git = require_git()
    destination = safe_clone_destination(destination, codex_home)
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
    command = [git, "clone"]
    if ref:
        command.extend(["--branch", ref])
    command.extend([repository, str(destination)])
    run(command, dry_run=dry_run)
    if not dry_run and not is_marketplace(destination):
        raise RuntimeError(f"Cloned repository is not a workspace-local marketplace: {destination}")
    return destination


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


def available_bytes(path: Path) -> int | None:
    cursor = path
    while not cursor.exists() and cursor.parent != cursor:
        cursor = cursor.parent
    try:
        return shutil.disk_usage(cursor).free
    except OSError:
        return None


def update_repository(root: Path, repository: str, ref: str | None, dry_run: bool) -> dict:
    facts = git_facts(root, repository)
    if not facts["git"]:
        raise RuntimeError("Update requires a Git checkout; this source appears to be a ZIP or copied directory")
    if facts["dirty"]:
        raise RuntimeError("Update stopped because the marketplace worktree has uncommitted changes")
    if not facts["branch"]:
        raise RuntimeError("Update stopped because the repository is in detached HEAD state")
    if ref and facts["branch"] != ref:
        raise RuntimeError(f"Current branch is {facts['branch']}; requested ref is {ref}")
    git = require_git()
    run([git, "pull", "--ff-only", "origin", facts["branch"]], cwd=root, dry_run=dry_run)
    return facts if dry_run else git_facts(root, repository)


def verify_ref(root: Path, ref: str, head: str) -> None:
    git = require_git()
    resolved = run([git, "rev-parse", f"{ref}^{{commit}}"], cwd=root, capture=True, show_output=False).stdout.strip()
    if resolved != head:
        raise RuntimeError(f"Requested ref {ref} resolves to {resolved}, but the source checkout is {head}")


def resolve_codex_cli(explicit: str | None, root: Path, codex_home: Path) -> str | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Codex CLI was not found: {path}")
        return str(path)
    discovered = shutil.which("codex")
    if discovered and "WindowsApps" not in discovered:
        return discovered
    if os.name == "nt":
        candidate = codex_home / "plugins" / ".plugin-appserver" / "codex.exe"
        if candidate.is_file():
            return str(candidate.resolve())
        cursor = root
        for _ in range(7):
            candidate = cursor / "codex-home" / "plugins" / ".plugin-appserver" / "codex.exe"
            if candidate.is_file():
                return str(candidate.resolve())
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
    return None


def duplicate_findings(root: Path, codex_home: Path, codex_cli: str | None) -> list[str]:
    pack = load_json(root / "skill-pack.json")
    ids = [str(item["id"]) for item in pack.get("plugins", [])]
    warnings = []
    bare_root = codex_home / "skills"
    for plugin_id in ids:
        bare = bare_root / plugin_id / "SKILL.md"
        if bare.is_file():
            warnings.append(f"Bare skill source may duplicate workspace-local: {bare.parent}")
    if codex_cli:
        output = run([codex_cli, "plugin", "list"], capture=True, show_output=False).stdout
        for plugin_id in ids:
            pattern = re.compile(rf"(?m)^\s*{re.escape(plugin_id)}@([^\s]+)\s+installed,\s*enabled")
            for marketplace in pattern.findall(output):
                if marketplace != MARKETPLACE_NAME:
                    warnings.append(f"Enabled plugin duplicate: {plugin_id}@{marketplace}")
    return sorted(set(warnings))


def installation_findings(root: Path, codex_home: Path, codex_cli: str | None) -> dict:
    pack = load_json(root / "skill-pack.json")
    marker = codex_home / "workspace-local.json"
    config = load_json(marker) if marker.is_file() else None
    config_matches = bool(
        config
        and normalized_path(config.get("marketplaceRoot", "")) == normalized_path(root)
    )
    result = {
        "locationConfig": str(marker),
        "locationConfigExists": marker.is_file(),
        "locationConfigMatches": config_matches,
        "expectedPlugins": len(pack.get("plugins", [])),
        "enabledPlugins": 0,
        "missingOrWrongVersion": [],
    }
    if not codex_cli:
        result["status"] = "codex-cli-unavailable"
        return result
    output = run([codex_cli, "plugin", "list"], capture=True, show_output=False).stdout
    missing = []
    for item in pack.get("plugins", []):
        pattern = re.compile(
            rf"(?m)^\s*{re.escape(item['id'])}@{re.escape(MARKETPLACE_NAME)}\s+"
            rf"installed,\s*enabled\s+{re.escape(item['version'])}(?:\s|$)"
        )
        if pattern.search(output):
            result["enabledPlugins"] += 1
        else:
            missing.append(item["id"])
    result["missingOrWrongVersion"] = missing
    result["status"] = "ok" if not missing and config_matches else "needs-repair"
    return result


def run_doctor(root: Path, dry_run: bool) -> None:
    run([sys.executable, str(root / "tools" / "test_personal_skill_marketplace.py"), "--marketplace-root", str(root)], cwd=root, dry_run=dry_run)


def run_installer(args, root: Path, codex_home: Path, workspace_root: Path, codex_cli: str | None) -> None:
    command = [
        sys.executable,
        str(root / "tools" / "install_personal_skill_marketplace.py"),
        "--marketplace-root",
        str(root),
        "--workspace-root",
        str(workspace_root),
        "--codex-home",
        str(codex_home),
    ]
    if codex_cli:
        command.extend(["--codex-cli", codex_cli])
    if args.relocate:
        command.extend(["--replace-location-config", "--replace-marketplace-registration"])
    elif args.replace_location_config:
        command.append("--replace-location-config")
    if args.dry_run:
        command.append("--dry-run")
    command.append("--skip-doctor")
    run(command, cwd=root)


def main() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        raise RuntimeError("Python 3.10 or newer is required")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("audit", "install", "update", "repair"))
    parser.add_argument("--marketplace-root", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--codex-cli")
    parser.add_argument("--repo-url", default=DEFAULT_REPOSITORY)
    parser.add_argument("--ref")
    parser.add_argument("--replace-location-config", action="store_true")
    parser.add_argument("--relocate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    codex_home = resolve_codex_home(args.codex_home)
    os.environ["CODEX_HOME"] = str(codex_home)
    root = locate_marketplace(args.marketplace_root, codex_home, allow_explicit_conflict=args.relocate)
    cloned = False
    if root is None:
        if args.mode != "install":
            raise FileNotFoundError("No source marketplace was found. Use install with an explicit --destination for the first clone.")
        if not args.destination:
            raise ValueError("First installation requires an explicit, user-approved --destination")
        planned_destination = safe_clone_destination(args.destination, codex_home)
        print(
            json.dumps(
                {
                    "bootstrapPreflight": {
                        "mode": args.mode,
                        "repository": args.repo_url,
                        "requestedRef": args.ref or "main",
                        "destination": str(planned_destination),
                        "codexHome": str(codex_home),
                        "destinationFreeBytes": available_bytes(planned_destination),
                        "gitExecutable": require_git(),
                        "networkRequired": True,
                        "gitAuthentication": "may-be-required-by-remote",
                        "dryRun": args.dry_run,
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        root = clone_repository(args.destination, args.repo_url, args.ref or "main", codex_home, args.dry_run)
        cloned = True
    elif args.destination and normalized_path(args.destination.resolve()) != normalized_path(root):
        raise RuntimeError(f"A configured marketplace already exists at {root}; refusing a second source at {args.destination.resolve()}")

    if paths_overlap(root, codex_home):
        raise RuntimeError(f"Marketplace source and Codex home must not overlap: {root} <-> {codex_home}")

    facts_before = git_facts(root, args.repo_url) if not (cloned and args.dry_run) else {"git": True, "remote": args.repo_url, "branch": args.ref or "main", "commit": None, "dirty": False}
    if args.mode != "update" and args.ref and facts_before.get("commit"):
        verify_ref(root, args.ref, facts_before["commit"])

    prior_workspace = configured_workspace(codex_home, root)
    workspace_root = validate_workspace(
        args.workspace_root or prior_workspace or root.parent,
        codex_home,
        create=False,
    )
    codex_cli = resolve_codex_cli(args.codex_cli, root, codex_home)
    pack = load_json(root / "skill-pack.json") if not (cloned and args.dry_run) else {"plugins": []}
    preflight = {
        "mode": args.mode,
        "repository": args.repo_url,
        "marketplaceRoot": str(root),
        "workspaceRoot": str(workspace_root),
        "codexHome": str(codex_home),
        "codexCli": codex_cli,
        "pluginCount": len(pack.get("plugins", [])),
        "platform": {"system": platform.system(), "release": platform.release(), "python": sys.version.split()[0]},
        "workspaceFreeBytes": available_bytes(workspace_root),
        "git": facts_before,
        "networkRequired": args.mode == "update" or cloned,
        "gitAuthentication": "may-be-required-by-remote" if args.mode == "update" or cloned else "not-used",
        "dryRun": args.dry_run,
    }
    print(json.dumps({"preflight": preflight}, ensure_ascii=False, indent=2))

    if cloned and args.dry_run:
        print(json.dumps({"status": "dry-run", "mode": args.mode, "plannedClone": str(root)}, ensure_ascii=False, indent=2))
        return

    if args.mode == "update":
        facts_after = update_repository(root, args.repo_url, args.ref, args.dry_run)
        print(json.dumps({"postUpdateGit": facts_after}, ensure_ascii=False, indent=2))
    else:
        facts_after = facts_before

    if args.mode == "audit":
        run_doctor(root, args.dry_run)
    else:
        if not codex_cli:
            raise FileNotFoundError("Codex CLI was not found. Add codex to PATH or pass --codex-cli with its full path.")
        run_doctor(root, args.dry_run)
        run_installer(args, root, codex_home, workspace_root, codex_cli)

    warnings = [] if args.dry_run else duplicate_findings(root, codex_home, codex_cli)
    if facts_after.get("dirty") and args.mode in {"install", "repair"}:
        warnings.append("Source worktree has uncommitted changes; the installed state is not reproducible from the recorded commit")
    installation = None if args.dry_run else installation_findings(root, codex_home, codex_cli)
    if installation and installation.get("status") == "codex-cli-unavailable":
        warnings.append("Codex CLI is unavailable; installed plugin state was not verified")
    elif installation and installation.get("status") != "ok":
        warnings.append("Installed plugin versions or workspace-local location config need repair")
    result = {
        "status": "audited" if args.mode == "audit" else "dry-run" if args.dry_run else "completed",
        "mode": args.mode,
        "marketplaceRoot": str(root),
        "workspaceRoot": str(workspace_root),
        "codexHome": str(codex_home),
        "pluginCount": len(pack.get("plugins", [])),
        "git": facts_after,
        "installation": installation,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
