#!/usr/bin/env python3
"""Cross-platform bootstrap and lifecycle manager for workspace-local skills."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


DEFAULT_REPOSITORY = "https://github.com/fighttiger-Wang/sc-seq.git"
MARKETPLACE_NAME = "workspace-local"
MINIMUM_PYTHON = (3, 10)
STABLE_REF = "main"
SETUP_SKILL_ID = "personal-skill-marketplace-setup"
GUIDANCE_BEGIN = "<!-- BEGIN WORKSPACE-LOCAL SKILL SYNC -->"
GUIDANCE_END = "<!-- END WORKSPACE-LOCAL SKILL SYNC -->"


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


def git_output(git: str, root: Path, *arguments: str) -> str:
    return run([git, *arguments], cwd=root, capture=True, show_output=False).stdout.strip()


def git_ref_exists(git: str, root: Path, ref: str) -> bool:
    result = subprocess.run(
        [git, "rev-parse", "--verify", "--quiet", ref],
        cwd=root,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0


def git_is_ancestor(git: str, root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        [git, "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        capture_output=True,
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
            "- Before the final response after changing files inside the configured marketplace source, inspect the changed Skills and ask whether to publish. Never commit or push without the user's explicit confirmation.",
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


def replace_plugin_cachebusters(root: Path, plugin_ids: list[str]) -> dict[str, str]:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    versions: dict[str, str] = {}
    for plugin_id in plugin_ids:
        path = root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json"
        manifest = load_json(path)
        current = str(manifest.get("version") or "0.1.0")
        base = current.split("+", 1)[0]
        version = f"{base}+codex.{stamp}"
        manifest["version"] = version
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, path)
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


def publish_changes(args, root: Path) -> dict:
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
    affected = affected_plugins(root, paths)
    plan = {
        "status": "confirmation-required" if not args.confirm_publish else "publishing",
        "stableRef": stable_ref,
        "currentBranch": facts["branch"],
        "changedPaths": paths,
        "affectedPlugins": affected,
        "tests": ["marketplace doctor", "setup unit tests", "version manifest check", "annotation regressions when affected"],
    }
    if not args.confirm_publish:
        return plan
    if not affected:
        raise RuntimeError("No plugin-affecting changes were found; publish manually if this is an intentional documentation-only change")

    run([git, "fetch", "origin", stable_ref], cwd=root, dry_run=args.dry_run)
    if not args.dry_run and not git_ref_exists(git, root, remote_ref):
        raise RuntimeError(f"Remote stable ref does not exist: {remote_ref}")
    if not args.dry_run:
        head = git_output(git, root, "rev-parse", "HEAD")
        remote = git_output(git, root, "rev-parse", remote_ref)
        if facts["branch"] == stable_ref and head != remote:
            raise RuntimeError("Stable branch is not identical to origin; run preflight or resolve Git history before publishing")
        if facts["branch"].startswith("codex/") and not git_is_ancestor(git, root, remote, head):
            raise RuntimeError("Development branch does not contain the latest origin/main; merge stable changes manually before publishing")

    branch = facts["branch"]
    if branch == stable_ref:
        branch = args.branch or f"codex/skills-{dt.datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')}"
        run([git, "switch", "-c", branch], cwd=root, dry_run=args.dry_run)
    versions = {} if args.dry_run else replace_plugin_cachebusters(root, affected)
    run_publish_tests(root, affected, args.dry_run)
    publish_paths = changed_worktree_paths(git, root) if not args.dry_run else paths
    run([git, "add", "--", *publish_paths], cwd=root, dry_run=args.dry_run)
    message = args.message or f"Update personal skills: {', '.join(affected)}"
    run([git, "commit", "-m", message], cwd=root, dry_run=args.dry_run)
    run([git, "push", "-u", "origin", branch], cwd=root, dry_run=args.dry_run)
    pr = None
    if args.create_pr:
        gh = shutil.which("gh")
        if not gh:
            raise FileNotFoundError("GitHub CLI was not found; the branch was pushed but the pull request was not created")
        completed = run(
            [gh, "pr", "create", "--base", stable_ref, "--head", branch, "--fill"],
            cwd=root,
            capture=True,
            dry_run=args.dry_run,
        )
        pr = completed.stdout.strip() if completed.stdout else None
    return {
        **plan,
        "status": "published",
        "branch": branch,
        "versions": versions,
        "pullRequest": pr,
        "compareUrl": repository_compare_url(args.repo_url, stable_ref, branch),
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
    parser.add_argument("mode", choices=("audit", "bootstrap", "install", "preflight", "publish", "update", "repair"))
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
    parser.add_argument("--disable-bootstrap-copy", action="store_true")
    parser.add_argument("--confirm-publish", action="store_true")
    parser.add_argument("--branch")
    parser.add_argument("--message")
    parser.add_argument("--create-pr", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

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

    facts_before = git_facts(root, args.repo_url) if not (cloned and args.dry_run) else {"git": True, "remote": args.repo_url, "branch": args.ref or "main", "commit": None, "dirty": False}
    if args.mode == "bootstrap" and facts_before.get("dirty"):
        raise RuntimeError("Bootstrap requires a clean authoritative marketplace checkout")
    if args.mode not in {"preflight", "publish", "update"} and args.ref and facts_before.get("commit"):
        verify_ref(root, args.ref, facts_before["commit"])

    if args.mode == "publish":
        print(json.dumps(publish_changes(args, root), ensure_ascii=False, indent=2))
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
        result = {
            "status": sync["status"],
            "mode": args.mode,
            "marketplaceRoot": str(root),
            "workspaceRoot": str(workspace_root),
            "git": sync,
            "restartRequired": sync["restartRequired"],
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
    if args.mode == "audit":
        run_doctor(root, args.dry_run)
    else:
        if not codex_cli:
            raise FileNotFoundError("Codex CLI was not found. Add codex to PATH or pass --codex-cli with its full path.")
        run_doctor(root, args.dry_run)
        run_installer(args, root, codex_home, workspace_root, codex_cli)
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
    result = {
        "status": "audited" if args.mode == "audit" else "dry-run" if args.dry_run else "completed",
        "mode": args.mode,
        "marketplaceRoot": str(root),
        "workspaceRoot": str(workspace_root),
        "codexHome": str(codex_home),
        "pluginCount": len(pack.get("plugins", [])),
        "git": facts_after,
        "installation": installation,
        "managedGuidance": managed_guidance,
        "bootstrapCopy": bootstrap_copy,
        "restartRequired": args.mode != "audit" and not args.dry_run,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
