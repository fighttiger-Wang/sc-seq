#!/usr/bin/env python3
"""Cross-platform annotation knowledge release orchestrator."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ANNOTATION_PLUGINS = ("sc-major-celltype-annotation-auto", "sc-marker-cluster-annotation-auto")


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
    return runtime if runtime.is_file() else root / "shared" / "sc-annotation-evidence-core" / "knowledge-base" / "cell-annotation-knowledge-base.v2.json"


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
        return {"status": "verified", "marketplace": str(root)}

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
        command = [sys.executable, str(root / "tools" / "install_personal_skill_marketplace.py"), "--marketplace-root", str(root)]
        if args.codex_cli:
            command.extend(["--codex-cli", args.codex_cli])
        run(command, cwd=root, env=env)
    result = {"status": "published", "source": str(source), "marketplace": str(root), "versions": version_changes}
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
