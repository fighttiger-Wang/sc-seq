#!/usr/bin/env python3
"""Cross-platform annotation knowledge release orchestrator."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ANNOTATION_PLUGINS = ("sc-major-celltype-annotation-auto", "sc-marker-cluster-annotation-auto")
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def run(arguments: list[str], *, cwd: Path = ROOT, env: dict | None = None) -> None:
    print("+", " ".join(arguments), flush=True)
    result = subprocess.run(arguments, cwd=cwd, env=env)
    if result.returncode:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(arguments)}")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(["git", *arguments], cwd=root, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"Git command failed: git {' '.join(arguments)}: {result.stderr.strip()}")
    return result.stdout.strip()


def git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        capture_output=True,
    ).returncode == 0


def semantic_version(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value.split("+", 1)[0])
    if not match:
        raise RuntimeError(f"Invalid semantic version: {value}")
    return tuple(int(item) for item in match.groups())


def validate_release_source(root: Path) -> dict:
    """Reject dirty, stale, divergent, or historically mixed release sources."""
    if not (root / ".git").exists():
        raise RuntimeError("Release requires a Git checkout; non-Git sources are forbidden")
    dirty = git_output(root, "status", "--porcelain")
    if dirty:
        raise RuntimeError("Release source is dirty; use a clean clone and apply the approved change there")
    git_output(root, "fetch", "origin", "main")
    remote = git_output(root, "rev-parse", "origin/main")
    head = git_output(root, "rev-parse", "HEAD")
    if not git_is_ancestor(root, remote, head):
        raise RuntimeError("Release source does not contain the latest origin/main")
    versions = {}
    for plugin_id in ANNOTATION_PLUGINS:
        relative = f"plugins/{plugin_id}/.codex-plugin/plugin.json"
        local = load_json(root / relative)
        remote_json = json.loads(git_output(root, "show", f"origin/main:{relative}"))
        local_version = str(local.get("version") or "")
        remote_version = str(remote_json.get("version") or "")
        if semantic_version(local_version) < semantic_version(remote_version):
            raise RuntimeError(f"{plugin_id} version {local_version} is older than origin/main {remote_version}")
        versions[plugin_id] = {"local": local_version, "remote": remote_version}
    metadata_paths = [
        root / "skill-pack.json",
        *[root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json" for plugin_id in ANNOTATION_PLUGINS],
    ]
    stale = []
    for path in metadata_paths:
        text = path.read_text(encoding="utf-8")
        if re.search(r"(?<!\d)0\.6\.3(?:\+codex\.[0-9]+)?(?!\d)", text):
            stale.append(str(path))
    if stale:
        raise RuntimeError("Legacy v0.6.3 metadata is not publishable: " + ", ".join(stale))
    return {"head": head, "originMain": remote, "versions": versions}


def workspace_root(root: Path, explicit: Path | None) -> Path:
    if explicit:
        return explicit.expanduser().resolve()
    configured = os.environ.get("CODEX_SHARED_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    markers = [Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser() / "workspace-local.json", Path.home() / ".codex" / "workspace-local.json"]
    for marker in dict.fromkeys(markers):
        if marker.is_file():
            value = load_json(marker).get("workspaceRoot")
            if value:
                return Path(value).expanduser().resolve()
    return root.parent


def default_source(root: Path, workspace: Path) -> Path:
    runtime = workspace / ".sc-annotation-knowledge" / "published" / "current" / "cell-annotation-knowledge-base.v2.json"
    canonical = root / "shared" / "sc-annotation-evidence-core" / "knowledge-base" / "cell-annotation-knowledge-base.v2.json"
    return canonical if canonical.is_file() else runtime


def update_annotation_versions(root: Path, cachebuster: str) -> dict:
    changes = []
    for plugin_id in ANNOTATION_PLUGINS:
        path = root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json"
        manifest = load_json(path)
        old = str(manifest.get("version") or "0.1.0")
        base = old.split("+", 1)[0]
        new = f"{base}+codex.{cachebuster}"
        manifest["version"] = new
        atomic_json(path, manifest)
        changes.append({"id": plugin_id, "old": old, "new": new})
    return {"cachebuster": cachebuster, "changes": changes}


def find_system_skill(name: str, root: Path) -> Path | None:
    candidates: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(Path(codex_home).expanduser() / "skills" / ".system" / name)
    candidates.append(Path.home() / ".codex" / "skills" / ".system" / name)
    cursor = root
    for _ in range(7):
        candidates.append(cursor / "codex-home" / "skills" / ".system" / name)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    cache = Path.home() / ".codex" / "plugins" / "cache"
    if cache.is_dir():
        candidates.extend(cache.glob(f"**/{name}/SKILL.md"))
    for candidate in candidates:
        directory = candidate.parent if candidate.name == "SKILL.md" else candidate
        if (directory / "SKILL.md").is_file():
            return directory.resolve()
    return None


def ensure_yaml(root: Path, env: dict) -> dict:
    if importlib.util.find_spec("yaml") is not None:
        return env
    target = root / "tmp" / "python-validation-packages"
    target.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--target", str(target), "PyYAML==6.0.2"], cwd=root, env=env)
    updated = dict(env)
    updated["PYTHONPATH"] = str(target) + os.pathsep + updated.get("PYTHONPATH", "")
    return updated


def official_validate(root: Path, strict: bool, env: dict) -> None:
    creator = find_system_skill("skill-creator", root)
    plugin_creator = find_system_skill("plugin-creator", root)
    if not creator or not plugin_creator:
        message = "Codex system validators were not found; repository doctor remains authoritative on this host."
        if strict:
            raise FileNotFoundError(message)
        print("WARNING:", message)
        return
    env = ensure_yaml(root, env)
    for plugin_id in ANNOTATION_PLUGINS:
        plugin = root / "plugins" / plugin_id
        skill = plugin / "skills" / plugin_id
        run([sys.executable, str(creator / "scripts" / "quick_validate.py"), str(skill)], cwd=root, env=env)
        run([sys.executable, str(plugin_creator / "scripts" / "validate_plugin.py"), str(plugin)], cwd=root, env=env)


def publish(args) -> dict:
    root = args.marketplace_root.expanduser().resolve()
    workspace = workspace_root(root, args.workspace_root)
    source = (args.source or default_source(root, workspace)).expanduser().resolve()
    source_facts = validate_release_source(root)
    if "dirty-backup" in str(source).lower() or "local-marketplace-dirty" in str(source).lower():
        raise RuntimeError("A dirty-worktree backup cannot be used as a release source")
    env = dict(os.environ)
    env.update({
        "CODEX_SHARED_MARKETPLACE_ROOT": str(root),
        "CODEX_SHARED_WORKSPACE_ROOT": str(workspace),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    release_tool = root / "tools" / "release_annotation_knowledge_base.py"
    pack_tool = root / "tools" / "sync_skill_pack_versions.py"
    doctor = root / "tools" / "test_personal_skill_marketplace.py"
    if args.check_only:
        run([sys.executable, str(release_tool), "--check"], cwd=root, env=env)
        run([sys.executable, str(pack_tool), "--check"], cwd=root, env=env)
        run([sys.executable, str(doctor), "--marketplace-root", str(root)], cwd=root, env=env)
        return {"status": "verified", "marketplace": str(root), "sourceFacts": source_facts}

    run([sys.executable, str(release_tool), "--source", str(source)], cwd=root, env=env)
    cachebuster = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    version_changes = update_annotation_versions(root, cachebuster)
    run([sys.executable, str(pack_tool)], cwd=root, env=env)
    official_validate(root, args.strict_system_validation, env)
    if not args.skip_tests:
        test_root = root / "tmp" / "annotation-knowledge-tests" / cachebuster
        run([sys.executable, str(root / "plugins" / "sc-marker-cluster-annotation-auto" / "skills" / "sc-marker-cluster-annotation-auto" / "tests" / "run_registered_regressions.py"), "--work-dir", str(test_root / "registered")], cwd=root, env=env)
        run([sys.executable, str(root / "plugins" / "sc-major-celltype-annotation-auto" / "skills" / "sc-major-celltype-annotation-auto" / "tests" / "test_major_builder.py"), "--work-dir", str(test_root / "major")], cwd=root, env=env)
        run([sys.executable, str(root / "shared" / "sc-annotation-case-registry" / "tests" / "test_case_registry.py")], cwd=root, env=env)
    run([sys.executable, str(release_tool), "--check"], cwd=root, env=env)
    run([sys.executable, str(pack_tool), "--check"], cwd=root, env=env)
    run([sys.executable, str(doctor), "--marketplace-root", str(root)], cwd=root, env=env)
    run([sys.executable, str(release_tool), "--publish-runtime"], cwd=root, env=env)
    if not args.skip_bundle:
        run([sys.executable, str(root / "tools" / "new_personal_skill_bundle.py"), "--marketplace-root", str(root), "--bundle-name", "personal-codex-skills-current"], cwd=root, env=env)
    if not args.skip_install:
        command = [
            sys.executable,
            str(root / "tools" / "install_personal_skill_marketplace.py"),
            "--marketplace-root",
            str(root),
            "--workspace-root",
            str(workspace),
        ]
        if args.codex_cli:
            command.extend(["--codex-cli", args.codex_cli])
        run(command, cwd=root, env=env)
    result = {"status": "published", "source": str(source), "marketplace": str(root), "sourceFacts": source_facts, "versions": version_changes}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace-root", type=Path, default=ROOT)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--codex-cli")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-bundle", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--strict-system-validation", action="store_true")
    publish(parser.parse_args())


if __name__ == "__main__":
    main()
