#!/usr/bin/env python3
"""Cross-platform bootstrap and lifecycle manager for workspace-local skills."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path


DEFAULT_REPOSITORY = "https://github.com/fighttiger-Wang/sc-seq.git"
MARKETPLACE_NAME = "workspace-local"
MINIMUM_PYTHON = (3, 10)
STABLE_REF = "main"
SETUP_SKILL_ID = "personal-skill-marketplace-setup"
GUIDANCE_BEGIN = "<!-- BEGIN WORKSPACE-LOCAL SKILL SYNC -->"
GUIDANCE_END = "<!-- END WORKSPACE-LOCAL SKILL SYNC -->"
UNSAFE_REGISTRATION_STATUSES = {
    "dirty-source-retained",
    "divergent-source-retained",
    "development-source-retained",
    "detached-source-retained",
    "non-git-source-retained",
}
QUARANTINE_NAME_TOKENS = (
    "dirty",
    "quarantine",
    "backup",
    "disabled",
    "rollback",
    "legacy",
    "retired",
)


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


def subprocess_environment(command: list[str], cwd: Path | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    executable = Path(command[0]).name.lower() if command else ""
    if cwd is not None and executable in {"git", "git.exe"}:
        environment["GIT_CONFIG_COUNT"] = "1"
        environment["GIT_CONFIG_KEY_0"] = "safe.directory"
        environment["GIT_CONFIG_VALUE_0"] = str(cwd.resolve())
    return environment


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    dry_run: bool = False,
    show_output: bool = True,
    log_stream=None,
):
    print("+", " ".join(command), file=log_stream or sys.stdout, flush=True)
    if dry_run:
        return subprocess.CompletedProcess(command, 0, "", "")
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=capture,
        encoding="utf-8" if capture else None,
        errors="replace" if capture else None,
        env=subprocess_environment(command, cwd),
    )
    if capture and show_output:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr and result.returncode:
            print(result.stderr, end="", file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")
    return result


def git_output(git: str, root: Path, *arguments: str) -> str:
    return run([git, *arguments], cwd=root, capture=True, show_output=False).stdout.strip()


def git_commit_identity(git: str, root: Path) -> tuple[str, str]:
    """Reuse the repository's existing author for an isolated release commit.

    The release flow must not mutate global Git configuration.  A candidate
    clone can legitimately have no user.name/user.email configured, while its
    existing history still provides a stable identity for the automated
    commit.
    """
    output = git_output(git, root, "show", "-s", "--format=%an%n%ae", "HEAD")
    lines = [line.strip() for line in output.splitlines()]
    if len(lines) < 2 or not lines[0] or not lines[1]:
        raise RuntimeError("Cannot create release commit: no usable author identity was found in repository history")
    return lines[0], lines[1]


def git_ref_exists(git: str, root: Path, ref: str) -> bool:
    result = subprocess.run(
        [git, "rev-parse", "--verify", "--quiet", ref],
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=subprocess_environment([git], root),
    )
    return result.returncode == 0


def git_is_ancestor(git: str, root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        [git, "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        capture_output=True,
        env=subprocess_environment([git], root),
    ).returncode == 0


def changed_paths_between(git: str, root: Path, before: str, after: str) -> list[str]:
    output = git_output(git, root, "diff", "--name-only", f"{before}..{after}")
    return sorted({line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()})


def changed_worktree_paths(git: str, root: Path) -> list[str]:
    tracked = git_output(git, root, "diff", "--name-only", "HEAD")
    untracked = git_output(git, root, "ls-files", "--others", "--exclude-standard")
    return sorted(
        {
            line.strip().replace("\\", "/")
            for line in f"{tracked}\n{untracked}".splitlines()
            if line.strip()
        }
    )


def mixed_staging_paths(git: str, root: Path) -> list[str]:
    """Return paths modified in both the index and the worktree."""
    output = git_output(git, root, "status", "--porcelain=v1")
    paths = []
    for line in output.splitlines():
        if len(line) >= 3 and line[0] not in {" ", "?"} and line[1] not in {" ", "?"}:
            paths.append(line[3:].strip())
    return sorted(paths)


def unsafe_source_path(root: Path) -> bool:
    """Return true for any path explicitly classified as inactive or unsafe."""
    return any(
        token in part.casefold()
        for part in root.expanduser().resolve().parts
        for token in QUARANTINE_NAME_TOKENS
    )


def affected_plugins(root: Path, paths: list[str]) -> list[str]:
    pack = load_json(root / "skill-pack.json")
    plugin_ids = [str(item["id"]) for item in pack.get("plugins", [])]
    found: set[str] = set()
    reinstall_all = False
    for relative in paths:
        parts = Path(relative).parts
        if len(parts) >= 2 and parts[0] == "plugins" and parts[1] in plugin_ids:
            found.add(parts[1])
        elif parts and parts[0] == "shared":
            reinstall_all = True
        elif relative in {".agents/plugins/marketplace.json", ".codex-plugin/marketplace.json"}:
            reinstall_all = True
        elif relative in {
            "tools/install_personal_skill_marketplace.py",
            "Setup-PersonalSkillMarketplace.ps1",
            "Setup-PersonalSkillMarketplace.sh",
        }:
            found.add(SETUP_SKILL_ID)
    return plugin_ids if reinstall_all else [plugin_id for plugin_id in plugin_ids if plugin_id in found]


def changed_plugin_ids(paths: list[str]) -> list[str]:
    return sorted(
        {
            Path(relative).parts[1]
            for relative in paths
            if len(Path(relative).parts) >= 2 and Path(relative).parts[0] == "plugins"
        }
    )


def publication_plugins(root: Path, paths: list[str]) -> list[str]:
    pack = load_json(root / "skill-pack.json")
    registered = [str(item["id"]) for item in pack.get("plugins", [])]
    selected = set(changed_plugin_ids(paths))
    if any(
        relative
        in {
            "tools/install_personal_skill_marketplace.py",
            "Setup-PersonalSkillMarketplace.ps1",
            "Setup-PersonalSkillMarketplace.sh",
        }
        for relative in paths
    ):
        selected.add(SETUP_SKILL_ID)
    return [plugin_id for plugin_id in registered if plugin_id in selected]


def unregistered_changed_plugins(root: Path, paths: list[str]) -> list[str]:
    pack = load_json(root / "skill-pack.json")
    registered = {str(item["id"]) for item in pack.get("plugins", [])}
    return [plugin_id for plugin_id in changed_plugin_ids(paths) if plugin_id not in registered]


def managed_guidance_block() -> str:
    return "\n".join(
        (
            GUIDANCE_BEGIN,
            "## Shared personal Skill synchronization",
            "",
            "- Once per Codex task, before using or editing a Skill supplied by the `workspace-local` marketplace, invoke `$personal-skill-marketplace-setup` in `preflight` mode.",
            "- Do not run that preflight recursively when the active Skill is `personal-skill-marketplace-setup` itself.",
            "- If preflight reports that plugins were updated or `restartRequired` is true, stop the current workflow and ask the user to restart Codex and open a new task before using the updated Skill.",
            "- If preflight reports `up-to-date`, do not repeat the network check again in the same task.",
            "- Create or update maintained plugins through `$skill-writing`. A new plugin must be present in `skill-pack.json` and both marketplace manifests before publication.",
            "- Before the final response after changing files inside the configured marketplace source, inspect the changed Skills, present the read-only release plan, and request one task-scoped authorization for the complete one-step closeout: version update, commit, push, PR, CI, SHA-pinned merge, stable verification, cache refresh, restart notice, and new-task pickup. Never commit or push without that explicit confirmation.",
            "- After that one-step authorization, invoke `publish --one-step` (equivalent to `--confirm-publish --confirm-merge`) and continue automatically through every technical gate; do not ask separate PR, merge, installation, restart, or cache questions. Stop only on a failed gate or an explicit user scope limitation. If the user explicitly requests publication only, PR only, no merge, or no install, use the narrower flags and stop at the requested boundary.",
            "- Treat merge verification, cache directory/manifest/hash verification, restart, and new-task Skill-path pickup as separate execution gates. The last gate is not another human approval.",
            "- Never restore a dirty, divergent, detached, development, or non-Git marketplace source as the runtime registration; preserve it and register a persistent clean stable clone.",
            GUIDANCE_END,
        )
    )


def install_managed_guidance(workspace_root: Path, dry_run: bool) -> dict:
    path = workspace_root / "AGENTS.md"
    block = managed_guidance_block()
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    pattern = re.compile(rf"{re.escape(GUIDANCE_BEGIN)}.*?{re.escape(GUIDANCE_END)}", re.S)
    updated = pattern.sub(block, existing) if pattern.search(existing) else f"{existing.rstrip()}\n\n{block}\n".lstrip("\n")
    changed = updated != existing
    if changed and not dry_run:
        workspace_root.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(updated, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    return {"path": str(path), "changed": changed, "status": "dry-run" if dry_run else "installed"}


def disable_bootstrap_copy(codex_home: Path, marketplace_root: Path, dry_run: bool) -> dict:
    bare = codex_home / "skills" / SETUP_SKILL_ID
    if not (bare / "SKILL.md").is_file():
        return {"status": "not-present", "source": str(bare)}
    try:
        bare.resolve().relative_to(marketplace_root.resolve())
    except ValueError:
        pass
    else:
        raise RuntimeError("Refusing to disable the marketplace source as if it were a temporary bootstrap copy")
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    destination = codex_home / "skills.disabled" / f"{stamp}-bootstrap" / SETUP_SKILL_ID
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(bare), str(destination))
    return {"status": "dry-run" if dry_run else "disabled", "source": str(bare), "destination": str(destination)}


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
        if unsafe_source_path(resolved_explicit):
            raise RuntimeError(f"Refusing quarantined or backup marketplace source: {resolved_explicit}")
        return resolved_explicit
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
        if unsafe_source_path(resolved):
            continue
        if is_marketplace(resolved) and all(normalized_path(resolved) != normalized_path(item) for item in valid):
            valid.append(resolved)
    if len(valid) > 1:
        raise RuntimeError(f"Multiple marketplace roots were found: {[str(item) for item in valid]}")
    return valid[0] if valid else None


def require_git() -> str:
    git = shutil.which("git")
    if git:
        return git
    well_known = [
        Path(r"E:\A001-软件安装\Git\cmd\git.exe"),
        Path(r"C:\Program Files\Git\cmd\git.exe"),
        Path(r"C:\Program Files (x86)\Git\cmd\git.exe"),
        Path.home() / "AppData" / "Local" / "Programs" / "Git" / "cmd" / "git.exe",
    ]
    for candidate in well_known:
        if candidate.is_file():
            cmd_dir = str(candidate.parent)
            if cmd_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = cmd_dir + os.pathsep + os.environ.get("PATH", "")
            return str(candidate)
    raise FileNotFoundError("Git was not found in PATH. Install Git separately or provide an existing downloaded ZIP checkout.")


def git_facts(root: Path, expected_repository: str) -> dict:
    if not (root / ".git").exists():
        return {"git": False, "remote": None, "branch": None, "commit": None, "dirty": None}
    git = require_git()
    remote = run([git, "remote", "get-url", "origin"], cwd=root, capture=True, show_output=False).stdout.strip()
    if normalized_repository(remote) != normalized_repository(expected_repository):
        raise RuntimeError(f"Repository remote mismatch. Expected {expected_repository}; found {remote}")
    branch_result = subprocess.run(
        [git, "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=subprocess_environment([git], root),
    )
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


def preflight_repository(root: Path, repository: str, stable_ref: str, dry_run: bool) -> dict:
    facts = git_facts(root, repository)
    if not facts["git"]:
        raise RuntimeError("Preflight requires the authoritative Git checkout, not a ZIP or installed cache")
    if facts["dirty"]:
        raise RuntimeError("Preflight stopped because the marketplace worktree has uncommitted changes")
    if facts["branch"] != stable_ref and not str(facts["branch"] or "").startswith("codex/"):
        raise RuntimeError(
            f"Preflight supports {stable_ref} or codex/* development branches; current branch is {facts['branch'] or '[detached]'}"
        )
    git = require_git()
    remote_ref = f"origin/{stable_ref}"
    if dry_run:
        return {
            "status": "dry-run",
            "before": facts["commit"],
            "after": facts["commit"],
            "changedPaths": [],
            "affectedPlugins": [],
            "restartRequired": False,
        }
    run([git, "fetch", "origin", stable_ref], cwd=root)
    if not git_ref_exists(git, root, remote_ref):
        raise RuntimeError(f"Remote stable ref was not found after fetch: {remote_ref}")
    local = git_output(git, root, "rev-parse", "HEAD")
    remote = git_output(git, root, "rev-parse", remote_ref)
    if facts["branch"] != stable_ref:
        if git_is_ancestor(git, root, remote, local):
            return {
                "status": "development-current",
                "branch": facts["branch"],
                "before": local,
                "after": local,
                "stable": remote,
                "changedPaths": [],
                "affectedPlugins": [],
                "restartRequired": False,
            }
        raise RuntimeError("Development branch does not include the latest origin/main; merge stable changes manually")
    if local == remote:
        return {
            "status": "up-to-date",
            "before": local,
            "after": local,
            "changedPaths": [],
            "affectedPlugins": [],
            "restartRequired": False,
        }
    if git_is_ancestor(git, root, local, remote):
        run([git, "pull", "--ff-only", "origin", stable_ref], cwd=root)
        after = git_output(git, root, "rev-parse", "HEAD")
        paths = changed_paths_between(git, root, local, after)
        affected = affected_plugins(root, paths)
        return {
            "status": "updated",
            "before": local,
            "after": after,
            "changedPaths": paths,
            "affectedPlugins": affected,
            "restartRequired": bool(affected),
        }
    if git_is_ancestor(git, root, remote, local):
        return {
            "status": "local-ahead",
            "before": local,
            "after": local,
            "remote": remote,
            "changedPaths": [],
            "affectedPlugins": [],
            "restartRequired": False,
        }
    raise RuntimeError("Preflight stopped because local and remote stable history diverged; merge manually")


def verify_ref(root: Path, ref: str, head: str) -> None:
    git = require_git()
    resolved = run([git, "rev-parse", f"{ref}^{{commit}}"], cwd=root, capture=True, show_output=False).stdout.strip()
    if resolved != head:
        raise RuntimeError(f"Requested ref {ref} resolves to {resolved}, but the source checkout is {head}")


def _windows_app_version_key(path: Path) -> tuple[int, ...]:
    pkg_name = path.parts[-4] if len(path.parts) >= 4 else path.name
    match = re.search(r"_(\d+(?:\.\d+)+)_", pkg_name)
    if not match:
        return (0,)
    return tuple(int(part) for part in match.group(1).split("."))


def _windows_apps_codex_from_config(codex_home: Path) -> Path | None:
    cfg_path = codex_home / "config.toml"
    if not cfg_path.is_file():
        return None
    try:
        cfg_text = cfg_path.read_text(encoding="utf-8")
        cfg = _load_toml(cfg_text)
    except Exception:
        return None
    candidates: list[Path] = []
    node_env = ((cfg.get("mcp_servers") or {}).get("node_repl") or {}).get("env") or {}
    cli_val = node_env.get("CODEX_CLI_PATH")
    if isinstance(cli_val, str) and cli_val.strip():
        candidates.append(Path(cli_val.strip()))
    notify = cfg.get("notify")
    if isinstance(notify, list) and notify and isinstance(notify[0], str):
        # e.g. ...\app\resources\cua_node\bin\...\codex-computer-use.exe -> ...\app\resources\codex.exe
        p0 = Path(notify[0].strip())
        for parent in p0.parents:
            if parent.name == "resources":
                candidates.append(parent / "codex.exe")
                break
    for cand in candidates:
        try:
            if cand.is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


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
        from_cfg = _windows_apps_codex_from_config(codex_home)
        if from_cfg is not None:
            return str(from_cfg)
        windows_apps = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WindowsApps"
        try:
            if windows_apps.is_dir():
                matches = sorted(
                    windows_apps.glob("OpenAI.Codex_*/app/resources/codex.exe"),
                    key=_windows_app_version_key,
                    reverse=True,
                )
                for candidate in matches:
                    if candidate.is_file():
                        return str(candidate.resolve())
        except OSError:
            pass
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
    config_path = codex_home / "config.toml"
    if config_path.is_file() and _has_toml_parser():
        try:
            cfg = _load_toml(config_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
        for key, entry in (cfg.get("plugins") or {}).items():
            if not isinstance(entry, dict) or entry.get("enabled") is not True or "@" not in key:
                continue
            pid, marketplace = key.split("@", 1)
            if pid in ids and marketplace != MARKETPLACE_NAME:
                warnings.append(f"Enabled plugin duplicate: {pid}@{marketplace}")
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
        "cacheVerified": False,
        "cacheVerification": None,
    }
    if not codex_cli:
        result["status"] = "codex-cli-unavailable"
        return result
    output = run([codex_cli, "plugin", "list", "-m", MARKETPLACE_NAME], capture=True, show_output=False).stdout
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
    try:
        result["cacheVerification"] = verify_plugin_cache(root, codex_home)
        result["cacheVerified"] = True
    except RuntimeError as exc:
        result["cacheVerification"] = {"status": "failed", "error": str(exc)}
    result["status"] = "ok" if not missing and config_matches and result["cacheVerified"] else "needs-repair"
    return result


def run_doctor(root: Path, dry_run: bool) -> None:
    run([sys.executable, str(root / "tools" / "test_personal_skill_marketplace.py"), "--marketplace-root", str(root)], cwd=root, dry_run=dry_run)


def semantic_version(value: str) -> tuple[int, int, int]:
    base = value.split("+", 1)[0]
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", base)
    if not match:
        raise RuntimeError(f"Plugin version is not semantic X.Y.Z: {value}")
    return tuple(int(item) for item in match.groups())


def semantic_version_text(value: tuple[int, int, int]) -> str:
    return ".".join(str(item) for item in value)


def next_patch_version(value: str) -> str:
    major, minor, patch = semantic_version(value)
    return semantic_version_text((major, minor, patch + 1))


def display_name_with_version(value: str, version: str) -> str:
    name = re.sub(r"\s+v\d+\.\d+\.\d+$", "", value.strip())
    return f"{name} v{version}"


def update_yaml_display_version(path: Path, version: str) -> None:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    changed = 0
    updated: list[str] = []
    for line in lines:
        match = re.match(r"^(\s*display_name:\s*)(.*?)(\r?\n)?$", line)
        if not match:
            updated.append(line)
            continue
        raw = match.group(2).strip()
        quote = raw[0] if len(raw) >= 2 and raw[0] in {'\"', "'"} and raw[-1] == raw[0] else ""
        value = raw[1:-1] if quote else raw
        replacement = display_name_with_version(value, version)
        updated.append(f"{match.group(1)}{quote}{replacement}{quote}{match.group(3) or ''}")
        changed += 1
    if changed != 1:
        raise RuntimeError(f"Expected exactly one display_name in {path}; found {changed}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(updated), encoding="utf-8", newline="")
    os.replace(temporary, path)


def committed_plugin_version(git: str, root: Path, plugin_id: str) -> str | None:
    relative = f"plugins/{plugin_id}/.codex-plugin/plugin.json"
    completed = subprocess.run(
        [git, "show", f"HEAD:{relative}"],
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=subprocess_environment([git], root),
    )
    if completed.returncode:
        return None
    return str(json.loads(completed.stdout).get("version") or "")


def plugin_version_at_ref(git: str, root: Path, ref: str, plugin_id: str) -> str:
    relative = f"plugins/{plugin_id}/.codex-plugin/plugin.json"
    raw = git_output(git, root, "show", f"{ref}:{relative}")
    version = str(json.loads(raw).get("version") or "")
    semantic_version(version)
    return version


def active_metadata_files(root: Path) -> list[Path]:
    files = [
        root / "skill-pack.json",
        root / ".agents" / "plugins" / "marketplace.json",
        root / ".codex-plugin" / "marketplace.json",
    ]
    for plugin_root in sorted(path for path in (root / "plugins").glob("*") if path.is_dir()):
        manifest = plugin_root / ".codex-plugin" / "plugin.json"
        if manifest.is_file():
            files.append(manifest)
        files.extend(
            sorted(
                path
                for path in plugin_root.glob("skills/*/agents/openai.yaml")
                if path.is_file()
            )
        )
    return files


def yaml_display_name(path: Path) -> str:
    """Read the simple scalar used by the marketplace's openai.yaml files."""
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*display_name:\s*(.*?)\s*$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] in {'\"', "'"} and value[-1] == value[0]:
            value = value[1:-1]
        return value
    return ""


def validate_active_metadata(root: Path, plugin_ids: list[str]) -> None:
    """Reject legacy versions and manifest/cache drift in active metadata."""
    pack = load_json(root / "skill-pack.json")
    pack_versions = {str(item["id"]): str(item.get("version") or "") for item in pack.get("plugins", [])}
    errors = []
    active_text = "\n".join(
        f"{path}:\n{path.read_text(encoding='utf-8')}"
        for path in active_metadata_files(root)
        if path.is_file()
    )
    if re.search(r"(?<!\d)0\.6\.3(?!\d)", active_text):
        errors.append("active metadata contains forbidden legacy v0.6.3")
    for plugin_id in plugin_ids:
        manifest_path = root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json"
        manifest = load_json(manifest_path)
        manifest_version = str(manifest.get("version") or "")
        semantic_version(manifest_version)
        if pack_versions.get(plugin_id) != manifest_version:
            errors.append(f"{plugin_id}: skill-pack version {pack_versions.get(plugin_id)} != plugin manifest {manifest_version}")
        skill_path = root / "plugins" / plugin_id / "skills" / plugin_id
        yaml_path = skill_path / "agents" / "openai.yaml"
        display = str((manifest.get("interface") or {}).get("displayName") or "")
        yaml_display = yaml_display_name(yaml_path) if yaml_path.is_file() else ""
        if display != yaml_display:
            errors.append(f"{plugin_id}: plugin.json and openai.yaml display names differ")
    if errors:
        raise RuntimeError("Active metadata gate failed: " + "; ".join(errors))


def validate_publish_versions(git: str, root: Path, stable_ref: str, plugin_ids: list[str]) -> dict[str, dict[str, str]]:
    """Require every affected candidate to move forward from stable main."""
    result = {}
    for plugin_id in plugin_ids:
        local_path = root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json"
        local_version = str(load_json(local_path).get("version") or "")
        stable_version = plugin_version_at_ref(git, root, f"origin/{stable_ref}", plugin_id)
        proposed = proposed_plugin_versions(root, [plugin_id], git)[plugin_id]
        if semantic_version(local_version) < semantic_version(stable_version):
            raise RuntimeError(f"{plugin_id} candidate version {local_version} is older than stable {stable_version}")
        if semantic_version(proposed) <= semantic_version(stable_version):
            raise RuntimeError(f"{plugin_id} proposed version {proposed} does not advance stable {stable_version}")
        result[plugin_id] = {"candidate": local_version, "stable": stable_version, "proposed": proposed}
    return result


def proposed_plugin_versions(root: Path, plugin_ids: list[str], git: str | None = None) -> dict[str, str]:
    result: dict[str, str] = {}
    for plugin_id in plugin_ids:
        manifest = load_json(root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json")
        current = str(manifest.get("version") or "0.1.0")
        current_base = semantic_version_text(semantic_version(current))
        previous = committed_plugin_version(git, root, plugin_id) if git else None
        previous_base = semantic_version_text(semantic_version(previous)) if previous else None
        result[plugin_id] = next_patch_version(current_base) if previous_base == current_base else current_base
    return result


def replace_plugin_cachebusters(root: Path, plugin_ids: list[str], git: str | None = None) -> dict[str, str]:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    versions: dict[str, str] = {}
    proposed = proposed_plugin_versions(root, plugin_ids, git)
    for plugin_id in plugin_ids:
        path = root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json"
        manifest = load_json(path)
        base = proposed[plugin_id]
        version = f"{base}+codex.{stamp}"
        manifest["version"] = version
        interface = manifest.setdefault("interface", {})
        interface["displayName"] = display_name_with_version(str(interface.get("displayName") or plugin_id), base)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
        update_yaml_display_version(root / "plugins" / plugin_id / "skills" / plugin_id / "agents" / "openai.yaml", base)
        versions[plugin_id] = version
    run([sys.executable, str(root / "tools" / "sync_skill_pack_versions.py")], cwd=root)
    return versions


def run_publish_tests(root: Path, affected: list[str], dry_run: bool) -> None:
    run_doctor(root, dry_run)
    run([sys.executable, str(root / "tools" / "test_marketplace_setup.py")], cwd=root, dry_run=dry_run)
    run([sys.executable, str(root / "tools" / "sync_skill_pack_versions.py"), "--check"], cwd=root, dry_run=dry_run)
    annotation_ids = {"sc-major-celltype-annotation-auto", "sc-marker-cluster-annotation-auto", "annotation-knowledge-release"}
    if annotation_ids.intersection(affected):
        test_root = root / "tmp"
        if dry_run:
            run([sys.executable, str(root / "shared" / "sc-annotation-case-registry" / "tests" / "test_case_registry.py")], cwd=root, dry_run=True)
            run(
                [
                    sys.executable,
                    str(root / "plugins" / "sc-marker-cluster-annotation-auto" / "skills" / "sc-marker-cluster-annotation-auto" / "tests" / "run_registered_regressions.py"),
                    "--work-dir",
                    str(test_root / "planned-registered-regressions"),
                ],
                cwd=root,
                dry_run=True,
            )
            return
        test_root.mkdir(parents=True, exist_ok=True)
        previous = {name: os.environ.get(name) for name in ("CODEX_TEST_TMPDIR", "TMPDIR", "TEMP", "TMP")}
        for name in previous:
            os.environ[name] = str(test_root)
        try:
            with tempfile.TemporaryDirectory(prefix="workspace-local-regression-", dir=test_root) as temporary:
                work = Path(temporary)
                run([sys.executable, str(root / "shared" / "sc-annotation-case-registry" / "tests" / "test_case_registry.py")], cwd=root, dry_run=dry_run)
                run(
                    [
                        sys.executable,
                        str(root / "plugins" / "sc-marker-cluster-annotation-auto" / "skills" / "sc-marker-cluster-annotation-auto" / "tests" / "run_registered_regressions.py"),
                        "--work-dir",
                        str(work / "registered"),
                    ],
                    cwd=root,
                    dry_run=dry_run,
                )
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


def repository_compare_url(repository: str, stable_ref: str, branch: str) -> str | None:
    normalized = normalized_repository(repository)
    if not normalized.startswith("github.com/"):
        return None
    slug = normalized.removeprefix("github.com/")
    return f"https://github.com/{slug}/compare/{stable_ref}...{branch}?expand=1"


def github_repository_slug(repository: str) -> str | None:
    normalized = normalized_repository(repository)
    if not normalized.startswith("github.com/"):
        return None
    slug = normalized.removeprefix("github.com/")
    return slug if re.fullmatch(r"[^/]+/[^/]+", slug) else None


def enable_github_api_proxy_from_git(git: str, root: Path) -> str | None:
    completed = subprocess.run(
        [git, "config", "--get", "http.proxy"],
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=subprocess_environment([git], root),
    )
    proxy = completed.stdout.strip() if completed.returncode == 0 else ""
    if proxy:
        os.environ.setdefault("HTTPS_PROXY", proxy)
        os.environ.setdefault("HTTP_PROXY", proxy)
        return proxy
    return None


def github_auth_token(git: str, root: Path, repository: str) -> str:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(name):
            return str(os.environ[name])
    gh = shutil.which("gh")
    if gh:
        completed = subprocess.run(
            [gh, "auth", "token"],
            cwd=root,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
    slug = github_repository_slug(repository)
    if not slug:
        raise RuntimeError("Automatic PR operations require a GitHub repository")
    for credential_input in (
        f"protocol=https\nhost=github.com\npath={slug}\n\n",
        "protocol=https\nhost=github.com\n\n",
    ):
        completed = subprocess.run(
            [git, "credential", "fill"],
            cwd=root,
            input=credential_input,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=subprocess_environment([git], root),
        )
        values = {}
        for line in completed.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
        if completed.returncode == 0 and values.get("password"):
            return values["password"]
    raise RuntimeError("GitHub authentication was not available from gh, environment, or the configured Git credential helper")


def github_api_request(
    token: str,
    slug: str,
    method: str,
    endpoint: str,
    payload: dict | None = None,
):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    suffix = endpoint.lstrip("/")
    url = f"https://api.github.com/repos/{slug}" + (f"/{suffix}" if suffix else "")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "workspace-local-skill-release",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("message", body)
        except json.JSONDecodeError:
            detail = body
        raise RuntimeError(f"GitHub API {method} {endpoint} failed with HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API {method} {endpoint} failed: {exc.reason}") from None


def find_or_create_pull_request(
    token: str,
    slug: str,
    stable_ref: str,
    branch: str,
    title: str,
    release_commit: str,
) -> dict:
    owner = slug.split("/", 1)[0]
    query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{branch}", "base": stable_ref})
    existing = github_api_request(token, slug, "GET", f"pulls?{query}")
    if existing:
        return existing[0]
    return github_api_request(
        token,
        slug,
        "POST",
        "pulls",
        {
            "title": title,
            "head": branch,
            "base": stable_ref,
            "body": f"Automated Skill release from `{release_commit}`. Tests passed locally before push.",
        },
    )


def github_ci_summary(checks: dict, combined_status: dict) -> dict:
    check_runs = list(checks.get("check_runs") or [])
    statuses = list(combined_status.get("statuses") or [])
    pending = [str(item.get("name") or "unnamed-check") for item in check_runs if item.get("status") != "completed"]
    failed = [
        str(item.get("name") or "unnamed-check")
        for item in check_runs
        if item.get("status") == "completed" and item.get("conclusion") not in {"success", "neutral", "skipped"}
    ]
    pending.extend(str(item.get("context") or "unnamed-status") for item in statuses if item.get("state") == "pending")
    failed.extend(str(item.get("context") or "unnamed-status") for item in statuses if item.get("state") in {"error", "failure"})
    observed = len(check_runs) + len(statuses)
    return {
        "observed": observed,
        "pending": sorted(set(pending)),
        "failed": sorted(set(failed)),
        "successful": observed > 0 and not pending and not failed,
    }


def wait_for_github_ci(token: str, slug: str, head_sha: str, timeout_seconds: int, poll_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_state = None
    while True:
        checks = github_api_request(token, slug, "GET", f"commits/{head_sha}/check-runs?per_page=100")
        statuses = github_api_request(token, slug, "GET", f"commits/{head_sha}/status")
        summary = github_ci_summary(checks, statuses)
        state = json.dumps(summary, ensure_ascii=False, sort_keys=True)
        if state != last_state:
            print(json.dumps({"githubCI": summary}, ensure_ascii=False), flush=True)
            last_state = state
        if summary["failed"]:
            raise RuntimeError("GitHub CI failed: " + ", ".join(summary["failed"]))
        if summary["successful"]:
            return summary
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for GitHub CI after {timeout_seconds} seconds")
        time.sleep(max(1, min(poll_seconds, int(max(1, deadline - time.monotonic())))))


def wait_for_clean_pull_request(token: str, slug: str, number: int, timeout_seconds: int, poll_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while True:
        pull = github_api_request(token, slug, "GET", f"pulls/{number}")
        if pull.get("draft"):
            raise RuntimeError(f"Pull request #{number} is a draft")
        if pull.get("state") != "open":
            raise RuntimeError(f"Pull request #{number} is not open")
        if pull.get("mergeable") is True and pull.get("mergeable_state") == "clean":
            return pull
        if pull.get("mergeable") is False:
            raise RuntimeError(f"Pull request #{number} is not mergeable: {pull.get('mergeable_state')}")
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Pull request #{number} did not reach clean mergeable state")
        time.sleep(max(1, min(poll_seconds, int(max(1, deadline - time.monotonic())))))


def merge_pull_request(token: str, slug: str, number: int, head_sha: str, title: str) -> dict:
    result = github_api_request(
        token,
        slug,
        "PUT",
        f"pulls/{number}/merge",
        {"sha": head_sha, "merge_method": "merge", "commit_title": title},
    )
    if result.get("merged") is not True or not result.get("sha"):
        raise RuntimeError(f"GitHub did not merge pull request #{number}: {result.get('message', 'unknown response')}")
    return result


def verify_remote_release(
    git: str,
    root: Path,
    stable_ref: str,
    release_commit: str,
    merge_commit: str,
) -> dict:
    run([git, "fetch", "origin", stable_ref], cwd=root)
    remote_ref = f"origin/{stable_ref}"
    stable_commit = git_output(git, root, "rev-parse", remote_ref)
    if not git_is_ancestor(git, root, release_commit, stable_commit):
        raise RuntimeError(f"Release commit {release_commit} is not contained in {remote_ref}")
    if not git_is_ancestor(git, root, merge_commit, stable_commit):
        raise RuntimeError(f"Merge commit {merge_commit} is not contained in {remote_ref}")
    return {
        "stableRef": remote_ref,
        "stableCommit": stable_commit,
        "releaseCommit": release_commit,
        "mergeCommit": merge_commit,
        "verified": True,
    }


def codex_marketplace_roots(codex_cli: str, root: Path, log_stream=None) -> list[str]:
    completed = run(
        [codex_cli, "plugin", "marketplace", "list"],
        cwd=root,
        capture=True,
        show_output=False,
        log_stream=log_stream,
    )
    roots = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(MARKETPLACE_NAME)}\s+(.+?)\s*$")
    for match in pattern.finditer(completed.stdout or ""):
        roots.append(match.group(1).strip())
    return roots


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rmtree_safe(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink():
        path.unlink()
        return

    def _clear_readonly(func, target_path, _exc) -> None:
        os.chmod(target_path, stat.S_IWRITE | stat.S_IREAD)
        func(target_path)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_readonly)
    else:
        shutil.rmtree(path, onerror=_clear_readonly)


def directory_content_sha256(root: Path) -> str:
    if not root.is_dir():
        return ""
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".git" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
        and path.name != ".DS_Store"
    )
    for file_path in files:
        relative = file_path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(file_path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _has_toml_parser() -> bool:
    try:
        import tomllib  # noqa: F401
        return True
    except ImportError:
        try:
            import tomli  # noqa: F401
            return True
        except ImportError:
            return False


def _load_toml(text: str) -> dict:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Python 3.11+ (tomllib) or 'tomli' package is required on Python 3.10 to parse Codex config.toml"
            ) from exc
    return tomllib.loads(text)


def _read_text_preserve_eol(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _atomic_write_text_preserving_mode(path: Path, text: str) -> None:
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(text)
        if path.exists():
            shutil.copymode(path, tmp_path)
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _safe_cache_plugin_dir(cache_root: Path, plugin_id: str) -> Path:
    if (
        not plugin_id
        or plugin_id in {".", ".."}
        or "/" in plugin_id
        or "\\" in plugin_id
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", plugin_id)
    ):
        raise RuntimeError(f"Unsafe or invalid plugin ID for Codex cache operation: {plugin_id!r}")
    root_resolved = cache_root.resolve()
    target = (cache_root / plugin_id).resolve()
    if target.parent != root_resolved:
        raise RuntimeError(f"Refusing Codex cache operation outside cache root: {target}")
    return cache_root / plugin_id


@contextlib.contextmanager
def _codex_home_sync_lock(codex_home: Path, timeout_seconds: float = 30.0):
    lock_path = codex_home / ".workspace-local-sync.lock"
    codex_home.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        locked = False
        try:
            if os.name == "nt":
                import msvcrt

                while True:
                    handle.seek(0)
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        locked = True
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(f"Timed out waiting for Codex sync lock: {lock_path}")
                        time.sleep(0.05)
            else:
                import fcntl

                while True:
                    try:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = True
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(f"Timed out waiting for Codex sync lock: {lock_path}")
                        time.sleep(0.05)
            yield
        finally:
            if locked:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _remove_config_plugin_block(config_text: str, plugin_key: str) -> str:
    newline = "\r\n" if "\r\n" in config_text else "\n"
    lines = config_text.splitlines()
    escaped = re.escape(plugin_key)
    header_re = re.compile(
        rf'^\[\s*plugins\s*\.\s*(?:"{escaped}"|\'{escaped}\')\s*\]\s*(?:#.*)?$'
    )
    nested_header_re = re.compile(
        rf'^\[\s*plugins\s*\.\s*(?:"{escaped}"|\'{escaped}\')\s*\.'
    )
    dotted_re = re.compile(
        rf'^\s*plugins\s*\.\s*(?:"{escaped}"|\'{escaped}\')\s*(?:\.|=)'
    )
    out: list[str] = []
    skipping = False
    drop_one_trailing_blank = False
    for line in lines:
        stripped = line.strip()
        if header_re.match(stripped):
            skipping = True
            drop_one_trailing_blank = True
            continue
        if skipping:
            if stripped.startswith("["):
                if nested_header_re.match(stripped):
                    drop_one_trailing_blank = True
                    continue
                skipping = False
                drop_one_trailing_blank = False
            elif not stripped:
                if drop_one_trailing_blank:
                    drop_one_trailing_blank = False
                    continue
                out.append(line)
                continue
            else:
                continue
        if dotted_re.match(line):
            continue
        out.append(line)
    result = newline.join(out)
    if config_text.endswith(("\n", "\r\n")) and result and not result.endswith(newline):
        result += newline
    return result


def _synchronize_codex_plugins_locked(
    marketplace_root: Path,
    codex_home: Path,
    codex_cli: str,
    config_path: Path,
    dry_run: bool,
) -> dict:
    roots = codex_marketplace_roots(codex_cli, marketplace_root, log_stream=sys.stderr)
    if not roots:
        return {"status": "skipped", "reason": "workspace-local-marketplace-not-registered", "codexRestartRequired": False}
    if len(roots) != 1 or normalized_path(roots[0]) != normalized_path(marketplace_root):
        if dry_run:
            return {
                "status": "skipped-root-mismatch",
                "registeredRoots": roots,
                "expectedRoot": str(marketplace_root),
                "codexRestartRequired": False,
            }
        raise RuntimeError(
            f"Registered {MARKETPLACE_NAME} root {roots} does not match {marketplace_root}"
        )

    pack = load_json(marketplace_root / "skill-pack.json")
    expected = {str(item["id"]): str(item["version"]) for item in pack.get("plugins", [])}
    before_cfg_text = _read_text_preserve_eol(config_path)
    before_cfg = _load_toml(before_cfg_text)

    suffix = f"@{MARKETPLACE_NAME}"
    plugins_cfg = before_cfg.get("plugins") or {}
    cfg_ws_ids = {
        key[: -len(suffix)]
        for key in plugins_cfg
        if key.endswith(suffix)
    }
    cache_root = codex_home / "plugins" / "cache" / MARKETPLACE_NAME
    cache_ids = {d.name for d in cache_root.iterdir() if d.is_dir()} if cache_root.is_dir() else set()
    retired = sorted((cfg_ws_ids | cache_ids) - set(expected.keys()))

    # Validate every ID and cache target boundary before invoking remove/rmtree/add
    for plugin_id in sorted(set(expected.keys()) | set(retired)):
        _safe_cache_plugin_dir(cache_root, plugin_id)

    # Snapshot which plugins differed on disk before `plugin list` (which can auto-materialize version bumps)
    source_hashes = {
        plugin_id: directory_content_sha256(marketplace_root / "plugins" / plugin_id)
        for plugin_id in expected
    }
    pre_stale: list[str] = []
    for plugin_id, expected_version in expected.items():
        plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
        version_cache_dir = plugin_cache_dir / expected_version
        if not version_cache_dir.is_dir():
            pre_stale.append(plugin_id)
            continue
        version_subdirs = [d.name for d in plugin_cache_dir.iterdir() if d.is_dir()]
        if version_subdirs != [expected_version] or directory_content_sha256(version_cache_dir) != source_hashes[plugin_id]:
            pre_stale.append(plugin_id)

    if dry_run:
        missing_dry: list[str] = []
        drifted_dry: list[str] = []
        for plugin_id in expected:
            cfg_entry = plugins_cfg.get(f"{plugin_id}{suffix}")
            plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
            if not isinstance(cfg_entry, dict) and not plugin_cache_dir.exists():
                missing_dry.append(plugin_id)
            elif not isinstance(cfg_entry, dict) or cfg_entry.get("enabled") is not True or plugin_id in pre_stale:
                drifted_dry.append(plugin_id)
        if not retired and not drifted_dry and not missing_dry:
            return {
                "status": "up-to-date",
                "removed": [],
                "refreshed": [],
                "installed": [],
                "verifiedPluginCount": len(expected),
                "codexRestartRequired": False,
            }
        return {
            "status": "dry-run",
            "removed": retired,
            "refreshed": drifted_dry,
            "installed": missing_dry,
            "autoRefreshedByCli": [],
            "verifiedPluginCount": len(expected),
            "codexRestartRequired": True,
        }

    list_output = run(
        [codex_cli, "plugin", "list", "-m", MARKETPLACE_NAME],
        cwd=marketplace_root,
        capture=True,
        show_output=False,
        log_stream=sys.stderr,
    ).stdout or ""

    missing: list[str] = []
    drifted: list[str] = []
    auto_refreshed: list[str] = []
    for plugin_id, expected_version in expected.items():
        installed_any_re = re.compile(rf"(?m)^\s*{re.escape(plugin_id)}@{re.escape(MARKETPLACE_NAME)}\s+installed,")
        enabled_exact_re = re.compile(
            rf"(?m)^\s*{re.escape(plugin_id)}@{re.escape(MARKETPLACE_NAME)}\s+"
            rf"installed,\s*enabled\s+{re.escape(expected_version)}(?:\s|$)"
        )
        plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
        version_cache_dir = plugin_cache_dir / expected_version
        is_installed_anywhere = bool(installed_any_re.search(list_output)) or plugin_id in cfg_ws_ids or plugin_cache_dir.exists()
        if not is_installed_anywhere:
            missing.append(plugin_id)
            continue
        if not enabled_exact_re.search(list_output) or not version_cache_dir.is_dir():
            drifted.append(plugin_id)
            continue
        version_subdirs = [d.name for d in plugin_cache_dir.iterdir() if d.is_dir()]
        if version_subdirs != [expected_version]:
            drifted.append(plugin_id)
            continue
        cached_hash = directory_content_sha256(version_cache_dir)
        if source_hashes[plugin_id] != cached_hash:
            drifted.append(plugin_id)
        elif plugin_id in pre_stale:
            auto_refreshed.append(plugin_id)

    if not retired and not drifted and not missing:
        if auto_refreshed:
            verify_plugin_cache(marketplace_root, codex_home)
            return {
                "status": "synchronized",
                "removed": [],
                "refreshed": auto_refreshed,
                "installed": [],
                "autoRefreshedByCli": auto_refreshed,
                "verifiedPluginCount": len(expected),
                "codexRestartRequired": True,
            }
        return {
            "status": "up-to-date",
            "removed": [],
            "refreshed": [],
            "installed": [],
            "verifiedPluginCount": len(expected),
            "codexRestartRequired": False,
        }

    with tempfile.TemporaryDirectory(prefix="codex-sync-run-") as run_backup_tmp:
        run_backup_dir = Path(run_backup_tmp)
        backup_cfg_file = run_backup_dir / "config.toml.bak"
        backup_cfg_file.write_text(before_cfg_text, encoding="utf-8", newline="")
        shutil.copymode(config_path, backup_cfg_file)
        _atomic_write_text_preserving_mode(codex_home / "config.toml.bak.auto-sync", before_cfg_text)

        cache_backup_root = run_backup_dir / "cache"
        touched_ids = sorted(set(retired) | set(drifted) | set(missing))
        had_cache_before: dict[str, bool] = {}
        for plugin_id in touched_ids:
            plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
            if plugin_cache_dir.exists():
                had_cache_before[plugin_id] = True
                shutil.copytree(plugin_cache_dir, cache_backup_root / plugin_id)
            else:
                had_cache_before[plugin_id] = False

        try:
            for plugin_id in retired:
                selector = f"{plugin_id}@{MARKETPLACE_NAME}"
                plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
                cmd = [codex_cli, "plugin", "remove", selector]
                print("+", " ".join(cmd), file=sys.stderr, flush=True)
                subprocess.run(
                    cmd,
                    cwd=marketplace_root,
                    text=True,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    env=subprocess_environment(cmd, marketplace_root),
                )
                rmtree_safe(plugin_cache_dir)
                cur_text = _read_text_preserve_eol(config_path)
                if selector in (_load_toml(cur_text).get("plugins") or {}):
                    updated_text = _remove_config_plugin_block(cur_text, selector)
                    _atomic_write_text_preserving_mode(config_path, updated_text)

            for plugin_id in drifted:
                selector = f"{plugin_id}@{MARKETPLACE_NAME}"
                plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
                cmd = [codex_cli, "plugin", "remove", selector]
                print("+", " ".join(cmd), file=sys.stderr, flush=True)
                subprocess.run(
                    cmd,
                    cwd=marketplace_root,
                    text=True,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    env=subprocess_environment(cmd, marketplace_root),
                )
                rmtree_safe(plugin_cache_dir)
                cur_text = _read_text_preserve_eol(config_path)
                if selector in (_load_toml(cur_text).get("plugins") or {}):
                    updated_text = _remove_config_plugin_block(cur_text, selector)
                    _atomic_write_text_preserving_mode(config_path, updated_text)
                run([codex_cli, "plugin", "add", selector], cwd=marketplace_root, capture=True, show_output=False, log_stream=sys.stderr)

            for plugin_id in missing:
                plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
                rmtree_safe(plugin_cache_dir)
                run([codex_cli, "plugin", "add", f"{plugin_id}@{MARKETPLACE_NAME}"], cwd=marketplace_root, capture=True, show_output=False, log_stream=sys.stderr)

            verify_plugin_cache(marketplace_root, codex_home)
            after_cfg = _load_toml(_read_text_preserve_eol(config_path))
            for key, value in before_cfg.items():
                if key != "plugins" and after_cfg.get(key) != value:
                    raise RuntimeError(f"config.toml section '{key}' mutated unexpectedly during sync")
            before_plugins = before_cfg.get("plugins") or {}
            after_plugins = after_cfg.get("plugins") or {}
            for key, value in before_plugins.items():
                if not key.endswith(suffix) and after_plugins.get(key) != value:
                    raise RuntimeError(f"Non-workspace-local plugin '{key}' mutated unexpectedly during sync")
            for plugin_id in expected:
                entry = after_plugins.get(f"{plugin_id}{suffix}")
                if not isinstance(entry, dict) or entry.get("enabled") is not True:
                    raise RuntimeError(f"Expected enabled plugin missing from config.toml after sync: {plugin_id}{suffix}")
            remaining_retired = [
                key[: -len(suffix)]
                for key in after_plugins
                if key.endswith(suffix) and key[: -len(suffix)] not in expected
            ]
            if remaining_retired:
                raise RuntimeError(f"Retired plugins remained in config.toml after sync: {remaining_retired}")
        except Exception:
            _atomic_write_text_preserving_mode(config_path, before_cfg_text)
            shutil.copymode(backup_cfg_file, config_path)
            for plugin_id in touched_ids:
                plugin_cache_dir = _safe_cache_plugin_dir(cache_root, plugin_id)
                rmtree_safe(plugin_cache_dir)
                if had_cache_before.get(plugin_id):
                    shutil.copytree(cache_backup_root / plugin_id, plugin_cache_dir)
            raise

    return {
        "status": "synchronized",
        "removed": retired,
        "refreshed": sorted(set(drifted) | set(auto_refreshed)),
        "installed": missing,
        "autoRefreshedByCli": auto_refreshed,
        "verifiedPluginCount": len(expected),
        "codexRestartRequired": True,
    }


def synchronize_codex_plugins(
    marketplace_root: Path,
    codex_home: Path,
    codex_cli: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Incrementally sync @workspace-local plugins & cache without touching other config."""
    if not codex_cli:
        return {"status": "skipped", "reason": "codex-cli-unavailable", "codexRestartRequired": False}
    config_path = codex_home / "config.toml"
    if not config_path.is_file():
        return {"status": "skipped", "reason": "config-toml-missing", "codexRestartRequired": False}
    if dry_run:
        return _synchronize_codex_plugins_locked(marketplace_root, codex_home, codex_cli, config_path, dry_run=True)
    with _codex_home_sync_lock(codex_home):
        return _synchronize_codex_plugins_locked(marketplace_root, codex_home, codex_cli, config_path, dry_run=False)


def plugin_source_files(plugin_root: Path) -> list[Path]:
    return sorted(
        path
        for path in plugin_root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
        and path.name != ".DS_Store"
    )


def verify_plugin_cache(root: Path, codex_home: Path) -> dict:
    pack = load_json(root / "skill-pack.json")
    cache_root = codex_home / "plugins" / "cache" / MARKETPLACE_NAME
    verified = []
    failures = []
    for item in pack.get("plugins", []):
        plugin_id = str(item["id"])
        expected_version = str(item["version"])
        source_root = root / "plugins" / plugin_id
        installed_root = cache_root / plugin_id / expected_version
        manifest_path = installed_root / ".codex-plugin" / "plugin.json"
        if not installed_root.is_dir():
            failures.append(f"{plugin_id}: cache directory missing for {expected_version}")
            continue
        if not manifest_path.is_file():
            failures.append(f"{plugin_id}: cached plugin manifest is missing")
            continue
        cached_version = str(load_json(manifest_path).get("version") or "")
        if cached_version != expected_version:
            failures.append(
                f"{plugin_id}: cached manifest version is {cached_version or '[missing]'}, expected {expected_version}"
            )
            continue
        source_files = plugin_source_files(source_root)
        if not source_files:
            failures.append(f"{plugin_id}: source plugin contains no verifiable files")
            continue
        digest = hashlib.sha256()
        mismatch = None
        for source in source_files:
            relative = source.relative_to(source_root)
            cached = installed_root / relative
            source_hash = sha256_file(source)
            if not cached.is_file():
                mismatch = f"missing cached file {relative.as_posix()}"
                break
            cached_hash = sha256_file(cached)
            if cached_hash != source_hash:
                mismatch = f"hash mismatch for {relative.as_posix()}"
                break
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(source_hash.encode("ascii"))
            digest.update(b"\n")
        if mismatch:
            failures.append(f"{plugin_id}: {mismatch}")
            continue
        verified.append(
            {
                "id": plugin_id,
                "version": expected_version,
                "cachePath": str(installed_root),
                "fileCount": len(source_files),
                "contentSha256": digest.hexdigest(),
            }
        )
    if failures:
        raise RuntimeError("Stable cache verification failed: " + "; ".join(failures))
    return {
        "status": "verified",
        "cacheRoot": str(cache_root),
        "verifiedPluginCount": len(verified),
        "plugins": verified,
    }


def verify_enabled_plugin_versions(codex_cli: str, root: Path, codex_home: Path) -> dict:
    pack = load_json(root / "skill-pack.json")
    completed = run([codex_cli, "plugin", "list", "-m", MARKETPLACE_NAME], cwd=root, capture=True, show_output=False)
    missing = []
    for item in pack.get("plugins", []):
        pattern = re.compile(
            rf"(?m)^\s*{re.escape(item['id'])}@{re.escape(MARKETPLACE_NAME)}\s+"
            rf"installed,\s*enabled\s+{re.escape(item['version'])}(?:\s|$)"
        )
        if not pattern.search(completed.stdout or ""):
            missing.append(str(item["id"]))
    if missing:
        raise RuntimeError("Stable cache refresh did not install expected plugin versions: " + ", ".join(missing))
    cache = verify_plugin_cache(root, codex_home)
    return {
        "status": "installed-and-verified",
        "enabledPluginCount": len(pack.get("plugins", [])),
        "cache": cache,
    }


def expected_skill_path(root: Path, codex_home: Path, plugin_id: str) -> Path:
    versions = {str(item["id"]): str(item["version"]) for item in load_json(root / "skill-pack.json").get("plugins", [])}
    if plugin_id not in versions:
        raise RuntimeError(f"Unknown plugin id for binding verification: {plugin_id}")
    return (
        codex_home
        / "plugins"
        / "cache"
        / MARKETPLACE_NAME
        / plugin_id
        / versions[plugin_id]
        / "skills"
        / plugin_id
        / "SKILL.md"
    ).resolve()


def verify_loaded_skill_binding(root: Path, codex_home: Path, loaded_skill_path: Path | None) -> dict:
    if loaded_skill_path is None:
        return {
            "status": "restart-required",
            "newTaskRequired": True,
            "loadedSkillPath": None,
        }
    loaded = loaded_skill_path.expanduser().resolve()
    for item in load_json(root / "skill-pack.json").get("plugins", []):
        plugin_id = str(item["id"])
        expected = expected_skill_path(root, codex_home, plugin_id)
        if normalized_path(loaded) == normalized_path(expected):
            return {
                "status": "loaded-path-verified",
                "newTaskRequired": False,
                "pluginId": plugin_id,
                "version": str(item["version"]),
                "loadedSkillPath": str(loaded),
                "expectedSkillPath": str(expected),
            }
    return {
        "status": "loaded-path-mismatch",
        "newTaskRequired": True,
        "loadedSkillPath": str(loaded),
    }


def configured_workspace_any(codex_home: Path) -> Path | None:
    marker = codex_home / "workspace-local.json"
    if not marker.is_file():
        return None
    value = load_json(marker).get("workspaceRoot")
    return Path(value).expanduser().resolve() if value else None


def synchronize_registered_stable_root(
    git: str,
    release_root: Path,
    registered_root: Path,
    repository: str,
    stable_ref: str,
) -> dict:
    facts = git_facts(registered_root, repository)
    if not facts.get("git"):
        return {"status": "non-git-source-retained", "path": str(registered_root)}
    if facts.get("dirty"):
        return {"status": "dirty-source-retained", "path": str(registered_root), "before": facts.get("commit")}
    remote_ref = f"origin/{stable_ref}"
    run([git, "fetch", "origin", stable_ref], cwd=registered_root)
    remote = git_output(git, registered_root, "rev-parse", remote_ref)
    local = git_output(git, registered_root, "rev-parse", "HEAD")
    if facts.get("branch") is None:
        return {
            "status": "detached-source-retained",
            "path": str(registered_root),
            "before": local,
            "stable": remote,
        }
    if facts.get("branch") != stable_ref:
        return {
            "status": "development-source-retained",
            "path": str(registered_root),
            "branch": facts.get("branch"),
            "before": local,
            "stable": remote,
        }
    if local == remote:
        return {"status": "up-to-date", "path": str(registered_root), "before": local, "after": remote}
    if not git_is_ancestor(git, registered_root, local, remote):
        return {"status": "divergent-source-retained", "path": str(registered_root), "before": local, "stable": remote}
    run([git, "pull", "--ff-only", "origin", stable_ref], cwd=registered_root)
    after = git_output(git, registered_root, "rev-parse", "HEAD")
    if after != remote:
        raise RuntimeError(f"Registered stable source did not synchronize to {remote}: {after}")
    return {"status": "updated", "path": str(registered_root), "before": local, "after": after}


def unique_managed_stable_path(workspace: Path) -> Path:
    preferred = workspace / "local-marketplace-stable"
    if not preferred.exists():
        return preferred
    return workspace / f"local-marketplace-stable-{dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def prepare_persistent_stable_root(
    git: str,
    release_root: Path,
    workspace: Path,
    repository: str,
    stable_ref: str,
) -> dict:
    preferred = workspace / "local-marketplace-stable"
    if preferred.exists() and is_marketplace(preferred):
        existing = synchronize_registered_stable_root(git, release_root, preferred, repository, stable_ref)
        if existing["status"] not in UNSAFE_REGISTRATION_STATUSES:
            return {"status": "reused", "path": str(preferred), "synchronization": existing}
    destination = unique_managed_stable_path(workspace)
    run(
        [git, "clone", "--no-hardlinks", "--branch", stable_ref, str(release_root), str(destination)],
        cwd=release_root,
    )
    run([git, "remote", "set-url", "origin", repository], cwd=destination)
    run([git, "fetch", "origin", stable_ref], cwd=destination)
    run([git, "pull", "--ff-only", "origin", stable_ref], cwd=destination)
    local = git_output(git, destination, "rev-parse", "HEAD")
    remote = git_output(git, destination, "rev-parse", f"origin/{stable_ref}")
    if local != remote or not is_marketplace(destination):
        raise RuntimeError(f"Persistent stable marketplace did not resolve to {remote}: {destination} at {local}")
    return {"status": "created", "path": str(destination), "stableCommit": local}


ANTIGRAVITY_SKILLS_MAP: dict[str, tuple[int, str]] = {
    "single-cell-qc-extract": (1, "A01-质控过滤提取"),
    "sc-major-celltype-annotation-auto": (2, "A02-大类谱系注释"),
    "sc-marker-cluster-annotation-auto": (3, "A03-亚群精细注释"),
    "annotation-knowledge-release": (4, "A04-知识库发布"),
    "bioinformatics-results-report": (5, "A05-交互解读报告"),
    "bioinformatics-results-report-classic": (6, "A06-文档解读报告"),
    "workflow-script-structure": (7, "A07-流程脚本工程"),
    "single-cell-qc-image-display": (8, "B01-质控分布图"),
    "feature-gene-heatmap-violin": (9, "B02-Marker表达图"),
    "celltype-function-heatmap": (10, "B03-功能模块热图"),
    "sc-group-gene-bubble-stats": (11, "B04-分组表达气泡图"),
    "sc-cell-proportion-stats": (12, "B05-细胞比例统计图"),
    "kegg-flow-bubble-plot": (13, "B06-KEGG流泡图"),
    "scientific-diagram-016": (14, "B07-机制流程概念图"),
    "c06-ai-design-pipeline": (15, "C06-AI设计流水线"),
    "hpc-computing-guide": (16, "D01-HPC超算指南"),
    "server-task-delivery": (17, "D02-服务器任务投递"),
    "task-handoff": (18, "E01-任务交接"),
    "tripartite-expert-review": (19, "E02-生信三方评审"),
    "skill-writing": (20, "E03-Skill规范写作"),
    "personal-skill-marketplace-setup": (21, "E04-Skill市场安装"),
    "skill-sync-publish": (22, "E05-Skill同步发布"),
    "local-agent-delegate": (23, "E06-红蓝对抗闭环"),
    "e07-dispatch": (24, "E07-派发"),
}

RETIRED_ANTIGRAVITY_SKILL_DIRS: tuple[str, ...] = (
    "E02-三方专家评审",
    "E06-本机智能体委托",
    "C01-工作台",
    "C02-UI视觉设计",
    "C03-需求对齐追问",
    "C04-独立体验走查",
    "C05-桌面应用打包",
    "18-Lucky_Note工作台迭代与体验护栏",
    "E05-多智能体委托",
)


def _is_valid_zip(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            return zf.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def zip_directory(folder_path: Path, output_zip: Path, exclude_patterns: tuple[str, ...] = ("__pycache__", ".git")) -> None:
    tmp_zip = output_zip.with_name(f".{output_zip.name}.{uuid.uuid4().hex[:6]}.tmp")
    try:
        with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            for root_dir, _, files in os.walk(folder_path):
                if any(pat in root_dir for pat in exclude_patterns):
                    continue
                for file in files:
                    if file.endswith(".pyc"):
                        continue
                    file_path = Path(root_dir) / file
                    arcname = file_path.relative_to(folder_path)
                    zipf.write(file_path, arcname)
        os.replace(tmp_zip, output_zip)
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink(missing_ok=True)


def _stage_antigravity_skill_dir(
    src_plugin_dir: Path,
    src_skill_dir: Path,
    stage_dir: Path,
    order: int,
    chinese_cmd_name: str,
    shared_target_dir: Path,
) -> None:
    shutil.copytree(src_skill_dir, stage_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))

    pj_file = src_plugin_dir / ".codex-plugin" / "plugin.json"
    display_name = f"{order:02d} · {chinese_cmd_name[3:]}"
    short_desc = ""
    if pj_file.is_file():
        try:
            pj_data = load_json(pj_file)
            display_name = pj_data.get("interface", {}).get("displayName", display_name)
            short_desc = pj_data.get("interface", {}).get("shortDescription", "")
        except Exception:
            pass

    skill_md_file = stage_dir / "SKILL.md"
    if skill_md_file.is_file():
        content = skill_md_file.read_text(encoding="utf-8")
        desc_start = content.find("description:")
        if desc_start != -1:
            end_frontmatter = content.find("---", desc_start)
            existing_desc = content[desc_start + len("description:"):end_frontmatter].strip()
            if existing_desc.startswith(">-") or existing_desc.startswith("|"):
                existing_desc = existing_desc[2:].strip()
            if existing_desc.startswith('"') and existing_desc.endswith('"'):
                existing_desc = existing_desc[1:-1]
        else:
            existing_desc = ""

        if existing_desc.startswith(f"{display_name}：") or existing_desc.startswith(f"{display_name}:") or existing_desc.startswith(display_name):
            combined_desc = existing_desc
        elif short_desc:
            combined_desc = f"{display_name}：{short_desc} {existing_desc}".strip()
        else:
            combined_desc = f"{display_name}。{existing_desc}".strip()
        body_start = content.find("---", 3)
        body = content[body_start + 3:].strip() if body_start != -1 else content
        if body.startswith("# "):
            first_line_end = body.find("\n")
            body = f"# {display_name}\n" + (body[first_line_end + 1:] if first_line_end != -1 else "")
        else:
            body = f"# {display_name}\n\n" + body

        if "annotation-universal-contract.md" in body:
            ref_dir = stage_dir / "references"
            ref_dir.mkdir(parents=True, exist_ok=True)
            contract_file = shared_target_dir / "annotation-universal-contract.md"
            if contract_file.exists():
                shutil.copy2(contract_file, ref_dir / "annotation-universal-contract.md")
            body = body.replace("../../../../shared/annotation-universal-contract.md", "references/annotation-universal-contract.md")

        new_content = f"---\nname: {chinese_cmd_name}\ndisplayName: {display_name}\ndescription: {combined_desc}\n---\n\n{body}\n"
        skill_md_file.write_text(new_content, encoding="utf-8")


def synchronize_antigravity_environment(
    marketplace_root: Path,
    workspace_root: Path | None = None,
    dry_run: bool = False,
    state_file: Path | None = None,
    desktop_dir: Path | None = None,
) -> dict:
    antigravity_home = Path(
        os.environ.get("ANTIGRAVITY_HOME")
        or os.environ.get("GEMINI_HOME")
        or (Path.home() / ".gemini")
    )
    target_skills_dir = antigravity_home / "config" / "skills"
    shared_target_dir = antigravity_home / "config" / "shared"

    if state_file is not None:
        state_path = Path(state_file).expanduser().resolve()
    else:
        env_codex_home = os.environ.get("CODEX_HOME")
        if env_codex_home:
            state_path = Path(env_codex_home).expanduser().resolve() / "skill-sync-state.json"
        elif os.environ.get("ANTIGRAVITY_HOME") or os.environ.get("GEMINI_HOME"):
            state_path = antigravity_home / "skill-sync-state.json"
        else:
            default_codex = Path.home() / ".codex"
            state_path = (default_codex if default_codex.is_dir() else antigravity_home) / "skill-sync-state.json"

    sync_state: dict = {}
    if state_path.is_file():
        try:
            loaded_state = load_json(state_path)
            if isinstance(loaded_state, dict):
                sync_state = loaded_state
        except Exception:
            sync_state = {}
    ag_hashes: dict[str, str] = sync_state.setdefault("antigravityHashes", {})
    desktop_hashes: dict[str, str] = sync_state.setdefault("desktopPluginHashes", {})
    downstream_drift_backups: list[dict[str, str]] = []
    desktop_updated_plugins: list[str] = []

    synced_skills: list[str] = []
    if target_skills_dir.is_dir() or antigravity_home.is_dir():
        if not dry_run:
            target_skills_dir.mkdir(parents=True, exist_ok=True)
            for retired_name in RETIRED_ANTIGRAVITY_SKILL_DIRS:
                retired_dir = target_skills_dir / retired_name
                if retired_dir.exists():
                    rmtree_safe(retired_dir)
            for item in target_skills_dir.iterdir():
                if item.is_dir() and item.name.startswith("_archive"):
                    rmtree_safe(item)
            shared_source = marketplace_root / "shared"
            if shared_source.is_dir():
                if shared_target_dir.exists():
                    rmtree_safe(shared_target_dir)
                shutil.copytree(shared_source, shared_target_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
                pitfalls_src = shared_source / "global_pitfalls.json"
                if pitfalls_src.is_file():
                    shutil.copy2(pitfalls_src, target_skills_dir / "shared_global_pitfalls.json")

        with tempfile.TemporaryDirectory(prefix="ag-sync-stage-") as stage_tmp:
            stage_root = Path(stage_tmp)
            for plugin_id, (order, chinese_cmd_name) in ANTIGRAVITY_SKILLS_MAP.items():
                src_plugin_dir = marketplace_root / "plugins" / plugin_id
                src_skill_dir = src_plugin_dir / "skills" / plugin_id
                if not src_skill_dir.is_dir():
                    continue
                dest_skill_dir = target_skills_dir / chinese_cmd_name
                if not dry_run:
                    stage_dir = stage_root / chinese_cmd_name
                    _stage_antigravity_skill_dir(
                        src_plugin_dir,
                        src_skill_dir,
                        stage_dir,
                        order,
                        chinese_cmd_name,
                        shared_target_dir,
                    )
                    rendered_hash = directory_content_sha256(stage_dir)
                    prev_ag_hash = ag_hashes.get(chinese_cmd_name)
                    if dest_skill_dir.is_dir():
                        current_dest_hash = directory_content_sha256(dest_skill_dir)
                        should_backup = (
                            (prev_ag_hash is not None and current_dest_hash != prev_ag_hash)
                            or (prev_ag_hash is None and current_dest_hash != rendered_hash)
                        )
                        if should_backup:
                            stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
                            backup_base = antigravity_home / "archive_e_series_backup" / "downstream_drift_backups"
                            backup_dir = backup_base / f"{stamp}-{chinese_cmd_name}"
                            if backup_dir.exists():
                                backup_dir = backup_base / f"{stamp}-{uuid.uuid4().hex[:6]}-{chinese_cmd_name}"
                            backup_dir.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copytree(dest_skill_dir, backup_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
                            downstream_drift_backups.append({"skill": chinese_cmd_name, "backupPath": str(backup_dir)})

                    if dest_skill_dir.exists():
                        rmtree_safe(dest_skill_dir)
                    shutil.copytree(stage_dir, dest_skill_dir)
                    ag_hashes[chinese_cmd_name] = rendered_hash

                synced_skills.append(chinese_cmd_name)

        if not dry_run and target_skills_dir.is_dir():
            plugin_root = antigravity_home / "config" / "plugins" / "personal-bio-skills"
            if plugin_root.exists():
                rmtree_safe(plugin_root)

            skills_json_file = antigravity_home / "config" / "skills.json"
            skills_json_data = {"entries": [{"path": target_skills_dir.as_posix()}]}
            skills_json_file.write_text(json.dumps(skills_json_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    desktop_sync = None
    resolved_desktop_dir = Path("E:/Desktop/检索调用文件/skill") if desktop_dir is None else Path(desktop_dir)
    if resolved_desktop_dir.is_dir():
        desktop_sync = {"status": "synchronized", "path": str(resolved_desktop_dir)}
        if not dry_run:
            mp_dir = resolved_desktop_dir / "personal-codex-skills-marketplace-16"
            mp_zip = resolved_desktop_dir / f"{mp_dir.name}.zip"
            any_desktop_changed = False
            for plugin_id, (order, chinese_cmd_name) in ANTIGRAVITY_SKILLS_MAP.items():
                src_plugin = marketplace_root / "plugins" / plugin_id
                if not src_plugin.is_dir():
                    continue
                src_hash = directory_content_sha256(src_plugin)
                prev_hash = desktop_hashes.get(plugin_id)
                hash_changed = prev_hash != src_hash

                standalone_dir = resolved_desktop_dir / f"{order:02d}-{plugin_id}"
                standalone_zip = resolved_desktop_dir / f"{order:02d}-{plugin_id}.zip"
                standalone_exists = standalone_dir.is_dir()
                standalone_needs_update = standalone_exists and (
                    hash_changed
                    or directory_content_sha256(standalone_dir) != src_hash
                    or not _is_valid_zip(standalone_zip)
                )
                dst_plugin = mp_dir / "plugins" / plugin_id if mp_dir.is_dir() else None
                mp_exists = dst_plugin is not None and dst_plugin.is_dir()
                mp_plugin_needs_update = mp_exists and (
                    hash_changed or directory_content_sha256(dst_plugin) != src_hash
                )

                if standalone_needs_update:
                    rmtree_safe(standalone_dir)
                    shutil.copytree(src_plugin, standalone_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
                    zip_directory(standalone_dir, standalone_zip)
                if mp_plugin_needs_update and dst_plugin is not None:
                    rmtree_safe(dst_plugin)
                    shutil.copytree(src_plugin, dst_plugin, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))

                if standalone_needs_update or mp_plugin_needs_update:
                    desktop_updated_plugins.append(plugin_id)
                    any_desktop_changed = True

                targets_present = standalone_exists or mp_exists
                targets_ok = (
                    (not standalone_exists or (directory_content_sha256(standalone_dir) == src_hash and _is_valid_zip(standalone_zip)))
                    and (not mp_exists or directory_content_sha256(dst_plugin) == src_hash)  # type: ignore[arg-type]
                )
                if targets_present and targets_ok:
                    desktop_hashes[plugin_id] = src_hash
                else:
                    desktop_hashes.pop(plugin_id, None)

            if mp_dir.is_dir():
                src_sp = marketplace_root / "skill-pack.json"
                dst_sp = mp_dir / "skill-pack.json"
                if src_sp.is_file() and (not dst_sp.is_file() or sha256_file(src_sp) != sha256_file(dst_sp)):
                    shutil.copy2(src_sp, dst_sp)
                    any_desktop_changed = True
                if any_desktop_changed or not _is_valid_zip(mp_zip):
                    zip_directory(mp_dir, mp_zip)

            manifest_file = resolved_desktop_dir / "EXPORT-MANIFEST.json"
            if manifest_file.is_file():
                try:
                    m_data = load_json(manifest_file)
                    manifest_before = json.dumps(m_data, ensure_ascii=False, sort_keys=True)
                    for sk in m_data.get("skills", []):
                        sk_id = sk.get("id")
                        pj_f = marketplace_root / "plugins" / sk_id / ".codex-plugin" / "plugin.json"
                        if pj_f.is_file():
                            pj_d = load_json(pj_f)
                            v = pj_d.get("version", sk.get("version"))
                            sk["version"] = v
                            sk["sourcePackage"] = v
                            sk["displayName"] = pj_d.get("interface", {}).get("displayName", sk.get("displayName"))
                            z_path = resolved_desktop_dir / f"{sk.get('order', 0):02d}-{sk_id}.zip"
                            if _is_valid_zip(z_path):
                                sk["contentSha256"] = sha256_file(z_path)
                    if json.dumps(m_data, ensure_ascii=False, sort_keys=True) != manifest_before:
                        manifest_file.write_text(json.dumps(m_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                except Exception:
                    pass

    if not dry_run and (target_skills_dir.is_dir() or antigravity_home.is_dir() or resolved_desktop_dir.is_dir()):
        sync_state["updatedAt"] = dt.datetime.now().astimezone().isoformat()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_state: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=state_path.parent,
                prefix=f".{state_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                tmp_state = Path(handle.name)
                handle.write(json.dumps(sync_state, ensure_ascii=False, indent=2) + "\n")
            os.replace(tmp_state, state_path)
            tmp_state = None
        finally:
            if tmp_state is not None and tmp_state.exists():
                tmp_state.unlink(missing_ok=True)

    return {
        "status": "dry-run" if dry_run else ("synchronized" if synced_skills else "antigravity-not-found"),
        "antigravityHome": str(antigravity_home),
        "stateFile": str(state_path),
        "syncedSkillsCount": len(synced_skills),
        "syncedSkills": synced_skills,
        "downstreamDriftBackups": downstream_drift_backups,
        "desktopUpdatedPlugins": desktop_updated_plugins,
        "desktopSync": desktop_sync,
    }


def refresh_from_verified_stable(
    args,
    root: Path,
    codex_home: Path,
    stable_ref: str,
) -> dict:
    git = require_git()
    workspace = validate_workspace(args.workspace_root or configured_workspace_any(codex_home) or root.parent, codex_home, False)
    workspace.mkdir(parents=True, exist_ok=True)
    codex_cli = resolve_codex_cli(args.codex_cli, root, codex_home)
    if not codex_cli:
        raise FileNotFoundError("Codex CLI was not found; stable release was merged but the callable cache was not refreshed")
    original_root = configured_marketplace(codex_home)
    if not original_root or not is_marketplace(original_root):
        original_root = root
    registered_source_sync = synchronize_registered_stable_root(
        git,
        root,
        original_root,
        args.repo_url,
        stable_ref,
    )
    retain_stable_root = registered_source_sync["status"] in UNSAFE_REGISTRATION_STATUSES
    persistent = None
    if retain_stable_root:
        persistent = prepare_persistent_stable_root(git, root, workspace, args.repo_url, stable_ref)
        stable_root = Path(persistent["path"])
        final_registration_root = stable_root
    else:
        temporary_parent = workspace / "tmp"
        temporary_parent.mkdir(parents=True, exist_ok=True)
        stable_root = temporary_parent / f"workspace-local-stable-{uuid.uuid4().hex}"
        run([git, "worktree", "add", "--detach", str(stable_root), f"origin/{stable_ref}"], cwd=root)
        final_registration_root = original_root
    finalized = False
    try:
        stable_commit = git_output(git, stable_root, "rev-parse", "HEAD")
        run_doctor(stable_root, False)
        command = [
            sys.executable,
            str(stable_root / "tools" / "install_personal_skill_marketplace.py"),
            "--marketplace-root",
            str(stable_root),
            "--workspace-root",
            str(workspace),
            "--codex-home",
            str(codex_home),
            "--codex-cli",
            codex_cli,
            "--skip-doctor",
            "--replace-marketplace-registration",
        ]
        if not retain_stable_root:
            command.append("--allow-detached-stable")
        if retain_stable_root:
            command.append("--replace-location-config")
        else:
            command.append("--skip-user-config")
        run(command, cwd=stable_root)
    finally:
        try:
            current_roots = codex_marketplace_roots(codex_cli, stable_root)
            if len(current_roots) != 1 or normalized_path(current_roots[0]) != normalized_path(final_registration_root):
                run([codex_cli, "plugin", "marketplace", "remove", MARKETPLACE_NAME], cwd=stable_root)
                run([codex_cli, "plugin", "marketplace", "add", str(final_registration_root)], cwd=stable_root)
            final_roots = codex_marketplace_roots(codex_cli, stable_root)
            if len(final_roots) != 1 or normalized_path(final_roots[0]) != normalized_path(final_registration_root):
                raise RuntimeError(f"Failed to finalize marketplace registration at {final_registration_root}: {final_roots}")
            installation = verify_enabled_plugin_versions(codex_cli, final_registration_root, codex_home)
            configured_root = configured_marketplace(codex_home)
            if not configured_root or normalized_path(configured_root) != normalized_path(final_registration_root):
                raise RuntimeError(
                    f"Location config did not settle on the final marketplace root {final_registration_root}: {configured_root}"
                )
            finalized = True
        finally:
            if finalized and not retain_stable_root:
                run([git, "worktree", "remove", str(stable_root)], cwd=root)
    antigravity_sync = synchronize_antigravity_environment(
        marketplace_root=final_registration_root,
        workspace_root=workspace,
        dry_run=False,
    )
    return {
        "status": "installed-and-verified",
        "stableCommit": stable_commit,
        "registeredMarketplaceRoot": str(final_registration_root),
        "retainedPersistentStableRoot": retain_stable_root,
        "persistentStableRoot": persistent,
        "registeredSourceSync": registered_source_sync,
        "antigravitySync": antigravity_sync,
        "cacheVerified": True,
        "installationVerification": installation,
        "workspaceRoot": str(workspace),
        "restartRequired": True,
        "activationStatus": "restart-required",
        "newTaskBinding": verify_loaded_skill_binding(stable_root, codex_home, None),
    }


def release_authorization_policy(merge_authorized: bool) -> dict:
    return {
        "singleReviewDefault": True,
        "oneStepRelease": True,
        "oneStepCommand": "publish --one-step",
        "noAdditionalApprovalAfterAuthorization": True,
        "defaultAuthorizationScope": [
            "version-update",
            "commit",
            "push",
            "pull-request",
            "ci-wait",
            "sha-pinned-merge",
            "stable-main-verification",
            "local-cache-refresh",
            "cache-hash-verification",
            "restart-and-new-task-pickup",
        ],
        "publicationOnlyRequiresExplicitLimitation": True,
        "mergeRequiresExplicitAuthorization": True,
        "mergeAuthorized": bool(merge_authorized),
    }


def apply_one_step_authorization(args):
    """Expand the single user-approved closeout control into execution flags."""
    if not args.one_step:
        return args
    if args.mode != "publish":
        raise ValueError("--one-step is only valid with publish mode")
    args.confirm_publish = True
    args.confirm_merge = True
    args.create_pr = True
    return args


def publish_changes(args, root: Path, codex_home: Path) -> dict:
    if unsafe_source_path(root):
        raise RuntimeError(f"Publish cannot use a quarantined or backup source: {root}")
    facts = git_facts(root, args.repo_url)
    if not facts["git"] or not facts["branch"]:
        raise RuntimeError("Publish requires a normal Git branch in the authoritative source checkout")
    git = require_git()
    stable_ref = args.ref or STABLE_REF
    remote_ref = f"origin/{stable_ref}"
    if facts["branch"] != stable_ref and not facts["branch"].startswith("codex/"):
        raise RuntimeError("Publish is allowed only from the stable branch or an existing codex/* development branch")

    paths = changed_worktree_paths(git, root)
    if not paths:
        raise RuntimeError("No uncommitted marketplace changes were found")
    mixed = mixed_staging_paths(git, root)
    if mixed:
        raise RuntimeError("Publish stopped because paths are modified in both index and worktree: " + ", ".join(mixed))
    unregistered = unregistered_changed_plugins(root, paths)
    affected = publication_plugins(root, paths)
    if not args.dry_run:
        run([git, "fetch", "origin", stable_ref], cwd=root)
        if not git_ref_exists(git, root, remote_ref):
            raise RuntimeError(f"Remote stable ref does not exist: {remote_ref}")
        head = git_output(git, root, "rev-parse", "HEAD")
        remote = git_output(git, root, "rev-parse", remote_ref)
        if facts["branch"] == stable_ref and head != remote:
            raise RuntimeError("Stable branch is not identical to origin; run preflight or resolve Git history before publishing")
        if facts["branch"].startswith("codex/") and not git_is_ancestor(git, root, remote, head):
            raise RuntimeError("Development branch does not contain the latest origin/main; merge stable changes manually before publishing")
        validate_active_metadata(root, affected)
        version_gate = validate_publish_versions(git, root, stable_ref, affected) if affected else {}
    else:
        version_gate = {}
    proposed_versions = {plugin_id: item["proposed"] for plugin_id, item in version_gate.items()} if version_gate else (proposed_plugin_versions(root, affected, git) if affected else {})
    plan = {
        "status": "registration-required" if unregistered else "confirmation-required" if not args.confirm_publish else "publishing",
        "stableRef": stable_ref,
        "currentBranch": facts["branch"],
        "changedPaths": paths,
        "affectedPlugins": affected,
        "proposedSemanticVersions": proposed_versions,
        "unregisteredPlugins": unregistered,
        "requiredRegistrationFiles": [
            "skill-pack.json",
            ".agents/plugins/marketplace.json",
            ".codex-plugin/marketplace.json",
        ],
        "tests": ["marketplace doctor", "setup unit tests", "version manifest check", "annotation regressions when affected"],
        **release_authorization_policy(args.confirm_merge),
    }
    if not args.confirm_publish:
        return plan
    if unregistered:
        raise RuntimeError(
            "New plugin directories are not fully registered for publication: " + ", ".join(unregistered)
        )
    if not affected:
        raise RuntimeError("No plugin-affecting changes were found; publish manually if this is an intentional documentation-only change")

    branch = facts["branch"]
    if branch == stable_ref:
        branch = args.branch or f"codex/skills-{dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"
        run([git, "switch", "-c", branch], cwd=root, dry_run=args.dry_run)
    versions = {} if args.dry_run else replace_plugin_cachebusters(root, affected, git)
    run_publish_tests(root, affected, args.dry_run)
    publish_paths = changed_worktree_paths(git, root) if not args.dry_run else paths
    run([git, "add", "--", *publish_paths], cwd=root, dry_run=args.dry_run)
    message = args.message or f"Update personal skills: {', '.join(affected)}"
    if args.dry_run:
        commit_command = [git, "commit", "-m", message]
    else:
        author_name, author_email = git_commit_identity(git, root)
        commit_command = [
            git,
            "-c",
            f"user.name={author_name}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "-m",
            message,
        ]
    run(commit_command, cwd=root, dry_run=args.dry_run)
    run([git, "push", "-u", "origin", branch], cwd=root, dry_run=args.dry_run)
    release_commit = None if args.dry_run else git_output(git, root, "rev-parse", "HEAD")
    pr = None
    pr_status = "not-requested"
    compare_url = repository_compare_url(args.repo_url, stable_ref, branch)
    if args.dry_run:
        return {
            **plan,
            "status": "dry-run",
            "branch": branch,
            "versions": versions,
            "pullRequestStatus": "planned" if args.create_pr or args.confirm_merge else "not-requested",
            "mergeStatus": "planned" if args.confirm_merge else "not-authorized",
            "compareUrl": compare_url,
        }

    pull = None
    token = None
    slug = github_repository_slug(args.repo_url)
    if args.create_pr or args.confirm_merge:
        try:
            if not slug:
                raise RuntimeError("Automatic PR creation requires a GitHub repository")
            enable_github_api_proxy_from_git(git, root)
            token = github_auth_token(git, root, args.repo_url)
            pull = find_or_create_pull_request(token, slug, stable_ref, branch, message, str(release_commit))
            pr = str(pull.get("html_url") or "") or None
            pr_status = "created-or-reused"
        except Exception:
            if args.confirm_merge:
                raise
            pr_status = "compare-url-required"

    ci = None
    merge = None
    stable = None
    refresh = None
    if args.confirm_merge:
        if not pull or not token or not slug:
            raise RuntimeError("Automatic merge requires an authenticated GitHub pull request")
        number = int(pull["number"])
        head_sha = str(pull.get("head", {}).get("sha") or release_commit)
        if head_sha != release_commit:
            raise RuntimeError(f"Pull request #{number} head {head_sha} does not match release commit {release_commit}")
        ci = wait_for_github_ci(token, slug, head_sha, args.ci_timeout_seconds, args.ci_poll_seconds)
        pull = wait_for_clean_pull_request(token, slug, number, min(180, args.ci_timeout_seconds), args.ci_poll_seconds)
        merge_response = merge_pull_request(token, slug, number, head_sha, message)
        merge_commit = str(merge_response["sha"])
        merge = {
            "status": "merged",
            "pullRequestNumber": number,
            "pullRequest": pr,
            "mergeCommit": merge_commit,
        }
        stable = verify_remote_release(git, root, stable_ref, str(release_commit), merge_commit)
        refresh = refresh_from_verified_stable(args, root, codex_home, stable_ref)
    return {
        **plan,
        "status": "merged-cache-verified-restart-required" if refresh else "published" if pr_status != "compare-url-required" else "published-pr-required",
        "branch": branch,
        "versions": versions,
        "releaseCommit": release_commit,
        "pullRequest": pr,
        "pullRequestStatus": pr_status,
        "githubCI": ci,
        "merge": merge,
        "stableVerification": stable,
        "cacheRefresh": refresh,
        "compareUrl": compare_url,
    }


def run_installer(
    args,
    root: Path,
    codex_home: Path,
    workspace_root: Path,
    codex_cli: str | None,
    plugin_ids: list[str] | None = None,
) -> None:
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
    for plugin_id in plugin_ids or []:
        command.extend(["--plugin-id", plugin_id])
    command.append("--skip-doctor")
    run(command, cwd=root)


def main() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        raise RuntimeError("Python 3.10 or newer is required")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("audit", "bootstrap", "install", "preflight", "publish", "update", "repair", "sync-antigravity"))
    parser.add_argument("--marketplace-root", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--codex-cli")
    parser.add_argument("--repo-url", default=DEFAULT_REPOSITORY)
    parser.add_argument("--ref")
    parser.add_argument("--replace-location-config", action="store_true")
    parser.add_argument("--relocate", action="store_true")
    parser.add_argument("--skip-managed-guidance", action="store_true")
    parser.add_argument("--skip-codex", action="store_true")
    parser.add_argument("--disable-bootstrap-copy", action="store_true")
    parser.add_argument("--confirm-publish", action="store_true")
    parser.add_argument("--one-step", action="store_true", help="Run the fully authorized publish, merge, verify, and cache closeout")
    parser.add_argument("--branch")
    parser.add_argument("--message")
    parser.add_argument("--create-pr", action="store_true")
    parser.add_argument("--confirm-merge", action="store_true")
    parser.add_argument("--ci-timeout-seconds", type=int, default=1800)
    parser.add_argument("--ci-poll-seconds", type=int, default=10)
    parser.add_argument("--loaded-skill-path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    args = apply_one_step_authorization(args)
    if args.confirm_merge and not args.confirm_publish:
        raise ValueError("--confirm-merge requires --confirm-publish and an explicit user request to publish and merge")
    if args.confirm_merge:
        args.create_pr = True
    if args.ci_timeout_seconds < 1 or args.ci_poll_seconds < 1:
        raise ValueError("CI timeout and poll interval must be positive")

    codex_home = resolve_codex_home(args.codex_home)
    os.environ["CODEX_HOME"] = str(codex_home)
    root = locate_marketplace(args.marketplace_root, codex_home, allow_explicit_conflict=args.relocate)
    cloned = False
    if root is None:
        if args.mode not in {"bootstrap", "install"}:
            raise FileNotFoundError("No source marketplace was found. Use bootstrap with an explicit --destination for the first clone.")
        if not args.destination:
            raise ValueError("First installation requires an explicit, user-approved --destination")
        if args.mode == "bootstrap" and not args.workspace_root:
            raise ValueError("Bootstrap requires an explicit, user-approved --workspace-root")
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

    if args.mode == "sync-antigravity":
        codex_cli = None
        if not args.skip_codex:
            codex_cli = resolve_codex_cli(args.codex_cli, root, codex_home)
            if codex_cli and (codex_home / "config.toml").is_file() and not _has_toml_parser():
                raise RuntimeError(
                    "Python 3.11+ (tomllib) or 'tomli' package is required on Python 3.10 to parse Codex config.toml before syncing"
                )
        sync_result = synchronize_antigravity_environment(
            marketplace_root=root,
            workspace_root=args.workspace_root,
            dry_run=args.dry_run,
        )
        if args.skip_codex:
            codex_sync_result = {"status": "skipped", "reason": "skip-codex-flag", "codexRestartRequired": False}
        else:
            codex_sync_result = synchronize_codex_plugins(
                marketplace_root=root,
                codex_home=codex_home,
                codex_cli=codex_cli,
                dry_run=args.dry_run,
            )
        print(json.dumps({"syncAntigravity": sync_result, "syncCodex": codex_sync_result}, ensure_ascii=False, indent=2))
        return

    facts_before = git_facts(root, args.repo_url) if not (cloned and args.dry_run) else {"git": True, "remote": args.repo_url, "branch": args.ref or "main", "commit": None, "dirty": False}
    if args.mode == "bootstrap" and facts_before.get("dirty"):
        raise RuntimeError("Bootstrap requires a clean authoritative marketplace checkout")
    if args.mode not in {"preflight", "publish", "update"} and args.ref and facts_before.get("commit"):
        verify_ref(root, args.ref, facts_before["commit"])

    if args.mode == "publish":
        print(json.dumps(publish_changes(args, root, codex_home), ensure_ascii=False, indent=2))
        return

    if args.mode == "bootstrap" and not args.workspace_root:
        raise ValueError("Bootstrap requires an explicit, user-approved --workspace-root")

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
        "networkRequired": args.mode in {"preflight", "update"} or cloned,
        "gitAuthentication": "may-be-required-by-remote" if args.mode in {"preflight", "update"} or cloned else "not-used",
        "dryRun": args.dry_run,
    }
    print(json.dumps({"preflight": preflight}, ensure_ascii=False, indent=2))

    if cloned and args.dry_run:
        print(json.dumps({"status": "dry-run", "mode": args.mode, "plannedClone": str(root)}, ensure_ascii=False, indent=2))
        return

    if args.mode == "preflight":
        sync = preflight_repository(root, args.repo_url, args.ref or STABLE_REF, args.dry_run)
        print(json.dumps({"repositoryPreflight": sync}, ensure_ascii=False, indent=2))
        if sync["status"] == "updated":
            run_doctor(root, args.dry_run)
            if sync["affectedPlugins"]:
                if not codex_cli:
                    raise FileNotFoundError("Codex CLI was not found. The repository updated, but plugins were not reinstalled")
                run_installer(args, root, codex_home, workspace_root, codex_cli, sync["affectedPlugins"])
        installation = None if args.dry_run else installation_findings(root, codex_home, codex_cli)
        binding = verify_loaded_skill_binding(root, codex_home, args.loaded_skill_path)
        result = {
            "status": sync["status"],
            "mode": args.mode,
            "marketplaceRoot": str(root),
            "workspaceRoot": str(workspace_root),
            "git": sync,
            "installation": installation,
            "restartRequired": sync["restartRequired"],
            "activationStatus": binding["status"],
            "newTaskBinding": binding,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.mode == "update":
        facts_after = update_repository(root, args.repo_url, args.ref, args.dry_run)
        print(json.dumps({"postUpdateGit": facts_after}, ensure_ascii=False, indent=2))
    else:
        facts_after = facts_before

    managed_guidance = None
    bootstrap_copy = None
    antigravity_sync = None
    if args.mode == "audit":
        run_doctor(root, args.dry_run)
    else:
        if not codex_cli:
            raise FileNotFoundError("Codex CLI was not found. Add codex to PATH or pass --codex-cli with its full path.")
        run_doctor(root, args.dry_run)
        run_installer(args, root, codex_home, workspace_root, codex_cli)
        if args.mode in {"install", "repair"} and not args.dry_run:
            antigravity_sync = synchronize_antigravity_environment(
                marketplace_root=root,
                workspace_root=workspace_root,
                dry_run=args.dry_run,
            )
        if args.mode == "bootstrap" and not args.skip_managed_guidance:
            managed_guidance = install_managed_guidance(workspace_root, args.dry_run)
        if args.mode == "bootstrap" and args.disable_bootstrap_copy:
            bootstrap_copy = disable_bootstrap_copy(codex_home, root, args.dry_run)

    warnings = [] if args.dry_run else duplicate_findings(root, codex_home, codex_cli)
    if facts_after.get("dirty") and args.mode in {"install", "repair"}:
        warnings.append("Source worktree has uncommitted changes; the installed state is not reproducible from the recorded commit")
    installation = None if args.dry_run else installation_findings(root, codex_home, codex_cli)
    if installation and installation.get("status") == "codex-cli-unavailable":
        warnings.append("Codex CLI is unavailable; installed plugin state was not verified")
    elif installation and installation.get("status") != "ok":
        warnings.append("Installed plugin versions or workspace-local location config need repair")
    binding = verify_loaded_skill_binding(root, codex_home, args.loaded_skill_path)
    result = {
        "status": "audited" if args.mode == "audit" else "dry-run" if args.dry_run else "completed",
        "mode": args.mode,
        "marketplaceRoot": str(root),
        "workspaceRoot": str(workspace_root),
        "codexHome": str(codex_home),
        "pluginCount": len(pack.get("plugins", [])),
        "git": facts_after,
        "installation": installation,
        "antigravitySync": antigravity_sync,
        "managedGuidance": managed_guidance,
        "bootstrapCopy": bootstrap_copy,
        "restartRequired": args.mode != "audit" and not args.dry_run,
        "activationStatus": binding["status"],
        "newTaskBinding": binding,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
