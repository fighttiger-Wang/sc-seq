#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E05 · Skill同步发布 v0.1.0 — 4 步原子级发布流水线引擎
流程：
  Step 1: 分舱鲁棒性体检 (自动调用 E03/scripts/validate_skill_robustness.py)
  Step 2: 自动升版本号 (自动调用 tools/bump_skill_version.py <skill-id> <version>)
  Step 3: 三端原子同步 (自动调用 E04/scripts/setup.py sync-antigravity)
  Step 4: GitHub 远端推送 (默认 --push 直接 Commit & Push 至 main；可选 --pr 走 PR CI 流水线)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_REGISTRY_PATHS = {
    "skill-pack.json",
    ".agents/plugins/marketplace.json",
    ".codex-plugin/marketplace.json",
}


def resolve_marketplace_root(explicit: Path | None = None) -> Path:
    if explicit and (explicit / "skill-pack.json").is_file():
        return explicit.resolve()
    env_root = os.environ.get("CODEX_SHARED_MARKETPLACE_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if (p / "skill-pack.json").is_file():
            return p
    marker = Path.home() / ".codex" / "workspace-local.json"
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            mp = data.get("marketplaceRoot")
            if mp and (Path(mp) / "skill-pack.json").is_file():
                return Path(mp).resolve()
        except Exception:
            pass
    cursor = Path(__file__).resolve()
    for parent in cursor.parents:
        if (parent / "skill-pack.json").is_file():
            return parent
    candidate = Path(r"E:\A002-Codex\工作区\local-marketplace-stable-20260916-193427-e53a557c")
    if (candidate / "skill-pack.json").is_file():
        return candidate.resolve()
    raise FileNotFoundError("Could not locate marketplace root containing skill-pack.json")


def find_git() -> str:
    git = shutil.which("git")
    if git:
        return git
    for candidate in (
        r"E:\A001-软件安装\Git\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("git executable not found")


def _subprocess_env(cmd: list[str], cwd: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    exe = Path(cmd[0]).name.lower() if cmd else ""
    if exe in {"git", "git.exe"}:
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "safe.directory"
        env["GIT_CONFIG_VALUE_0"] = str(cwd.resolve())
    return env


def run_step(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_subprocess_env(cmd, cwd),
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed (exit {proc.returncode}): {' '.join(cmd)}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return proc


def _semver_tuple(value: str) -> tuple[int, int, int]:
    base = value.strip().lstrip("vV").split("+", 1)[0]
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", base)
    if not match:
        raise ValueError(f"Invalid semantic version X.Y.Z: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def check_no_version_downgrade(mp_root: Path, plugin_id: str, version_spec: str) -> None:
    if version_spec.lower() in {"none", "auto", "patch", "minor", "major"}:
        return
    pj_path = mp_root / "plugins" / plugin_id / ".codex-plugin" / "plugin.json"
    if not pj_path.is_file():
        return
    current_raw = str(json.loads(pj_path.read_text(encoding="utf-8")).get("version") or "0.0.0")
    if _semver_tuple(version_spec) < _semver_tuple(current_raw):
        raise RuntimeError(
            f"Refusing version downgrade for '{plugin_id}': target {version_spec} < current {current_raw}"
        )


def check_remote_version_no_downgrade(git: str, mp_root: Path, plugin_ids: list[str] | None = None) -> None:
    """Ensure local target plugin versions do not regress below origin/main after bump."""
    remote_pack_proc = run_step([git, "show", "origin/main:skill-pack.json"], mp_root, check=False)
    remote_versions: dict[str, str] = {}
    if remote_pack_proc.returncode == 0 and remote_pack_proc.stdout.strip():
        remote_pack = json.loads(remote_pack_proc.stdout)
        for item in remote_pack.get("plugins", []):
            if isinstance(item, dict) and item.get("id") and item.get("version"):
                remote_versions[str(item["id"])] = str(item["version"])

    check_ids = list(plugin_ids) if plugin_ids else sorted(
        {
            *(remote_versions.keys()),
            *(
                str(item["id"])
                for item in json.loads((mp_root / "skill-pack.json").read_text(encoding="utf-8")).get("plugins", [])
                if isinstance(item, dict) and item.get("id")
            ),
        }
    )
    for pid in check_ids:
        pj_path = mp_root / "plugins" / pid / ".codex-plugin" / "plugin.json"
        if not pj_path.is_file():
            continue
        local_raw = str(json.loads(pj_path.read_text(encoding="utf-8")).get("version") or "0.0.0")
        remote_raw = remote_versions.get(pid)
        pj_remote_proc = run_step(
            [git, "show", f"origin/main:plugins/{pid}/.codex-plugin/plugin.json"],
            mp_root,
            check=False,
        )
        if pj_remote_proc.returncode == 0 and pj_remote_proc.stdout.strip():
            pj_remote_ver = str(json.loads(pj_remote_proc.stdout).get("version") or "")
            if pj_remote_ver and (not remote_raw or _semver_tuple(pj_remote_ver) > _semver_tuple(remote_raw)):
                remote_raw = pj_remote_ver
        if remote_raw and _semver_tuple(local_raw) < _semver_tuple(remote_raw):
            raise RuntimeError(
                f"Refusing version downgrade against origin/main for '{pid}': local {local_raw} < stable {remote_raw}"
            )


def parse_porcelain_paths(status_stdout: str) -> list[str]:
    paths: list[str] = []
    for line in status_stdout.splitlines():
        if len(line) < 4:
            continue
        raw = line[3:].strip()
        if " -> " in raw:
            old_p, new_p = raw.split(" -> ", 1)
            for part in (old_p, new_p):
                paths.append(part.strip().strip('"').replace("\\", "/"))
        else:
            paths.append(raw.strip().strip('"').replace("\\", "/"))
    return sorted(set(paths))


def _check_registry_only_allows_plugin(git: str, mp_root: Path, relpath: str, plugin_id: str) -> None:
    head_proc = run_step([git, "show", f"HEAD:{relpath}"], mp_root, check=False)
    if head_proc.returncode != 0 or not head_proc.stdout.strip():
        return
    cur_file = mp_root / relpath
    if not cur_file.is_file():
        raise RuntimeError(f"Registry file '{relpath}' deleted during single-skill release of '{plugin_id}'")
    head_data = json.loads(head_proc.stdout)
    cur_data = json.loads(cur_file.read_text(encoding="utf-8"))
    key_field = "id" if relpath == "skill-pack.json" else "name"
    head_meta = {k: v for k, v in head_data.items() if k != "plugins"}
    cur_meta = {k: v for k, v in cur_data.items() if k != "plugins"}
    if head_meta != cur_meta:
        raise RuntimeError(
            f"Registry '{relpath}' has top-level metadata changes outside single-skill scope '{plugin_id}'"
        )
    head_entries = {str(item.get(key_field)): item for item in head_data.get("plugins", []) if isinstance(item, dict)}
    cur_entries = {str(item.get(key_field)): item for item in cur_data.get("plugins", []) if isinstance(item, dict)}
    unrelated_ids = sorted(
        (set(head_entries.keys()) | set(cur_entries.keys())) - {plugin_id}
    )
    changed_other = [
        pid for pid in unrelated_ids if head_entries.get(pid) != cur_entries.get(pid)
    ]
    if changed_other:
        raise RuntimeError(
            f"Registry '{relpath}' contains changes for unrelated plugins {changed_other} while releasing '{plugin_id}'. "
            "Commit them separately or pass --allow-mixed-dirty."
        )


def check_unrelated_dirty_paths(git: str, mp_root: Path, plugin_id: str, allow_mixed_dirty: bool) -> None:
    if allow_mixed_dirty:
        return
    status_out = run_step([git, "status", "--porcelain=v1", "-uall"], mp_root).stdout
    dirty_paths = parse_porcelain_paths(status_out)
    allowed_prefix = f"plugins/{plugin_id}/"
    unrelated = [
        path
        for path in dirty_paths
        if not path.startswith(allowed_prefix) and path not in ROOT_REGISTRY_PATHS
    ]
    if unrelated:
        raise RuntimeError(
            f"Refusing release for '{plugin_id}' while unrelated uncommitted files exist: {unrelated}. "
            "Commit/stash them first or pass --allow-mixed-dirty."
        )
    for reg_path in sorted(path for path in dirty_paths if path in ROOT_REGISTRY_PATHS):
        _check_registry_only_allows_plugin(git, mp_root, reg_path, plugin_id)


def check_git_ancestor_gate(git: str, mp_root: Path) -> None:
    run_step([git, "fetch", "origin", "main"], mp_root)
    anc = run_step([git, "merge-base", "--is-ancestor", "origin/main", "HEAD"], mp_root, check=False)
    if anc.returncode != 0:
        raise RuntimeError(
            "origin/main contains commits not present in local HEAD (history diverged/behind). "
            "Run 'git pull --rebase' or merge origin/main before pushing; force-push is forbidden."
        )


def _parse_json_stdout(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        idx = text.find("{")
        if idx == -1:
            raise
        data, _ = json.JSONDecoder().raw_decode(text, idx)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object on stdout, got {type(data).__name__}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="E05 · Skill同步发布 4 步原子级流水线 v0.1.0")
    parser.add_argument("skill", nargs="?", default="all", help="目标 Skill ID 或中文名（传 all 则体检并同步全部）")
    parser.add_argument("--version", default="none", help="版本递增策略: auto, patch, minor, major, X.Y.Z, 或 none (已升版)")
    parser.add_argument("--marketplace-root", type=Path, default=None, help="权威 Marketplace 根目录")
    parser.add_argument("--push", action="store_true", help="直接 Commit 并 Push 至 GitHub main 分支")
    parser.add_argument("--allow-mixed-dirty", action="store_true", help="允许工作区存在目标 Skill 之外的未提交改动并一起提交")
    parser.add_argument("--pr", action="store_true", help="走 setup.py publish --one-step PR 合入模式")
    parser.add_argument("-m", "--message", default="", help="Git 提交说明")
    parser.add_argument("--dry-run", action="store_true", help="仅做只读预演与体检")
    args = parser.parse_args()

    mp_root = resolve_marketplace_root(args.marketplace_root)
    validator_py = (
        mp_root
        / "plugins"
        / "skill-writing"
        / "skills"
        / "skill-writing"
        / "scripts"
        / "validate_skill_robustness.py"
    )
    bump_py = mp_root / "tools" / "bump_skill_version.py"
    setup_py = (
        mp_root
        / "plugins"
        / "personal-skill-marketplace-setup"
        / "skills"
        / "personal-skill-marketplace-setup"
        / "scripts"
        / "setup.py"
    )

    report: dict[str, Any] = {
        "pipeline": "E05 · Skill同步发布 v0.1.0",
        "marketplace_root": str(mp_root),
        "target_skill": args.skill,
        "dry_run": args.dry_run,
        "steps": {},
    }

    # Resolve plugin_id if a specific skill was requested
    plugin_id = args.skill
    if args.skill.lower() != "all":
        # Let validator resolve it
        sys.path.insert(0, str(validator_py.parent))
        import validate_skill_robustness as vsr  # type: ignore
        plugin_id, cn_name = vsr.resolve_skill_pair(args.skill)
        report["resolved_plugin_id"] = plugin_id
        report["resolved_cn_name"] = cn_name
        check_no_version_downgrade(mp_root, plugin_id, args.version)
        if (args.push or args.pr) and not args.dry_run:
            check_unrelated_dirty_paths(find_git(), mp_root, plugin_id, args.allow_mixed_dirty)

    # Step 2 (pre-sync bump if requested)
    if args.version.lower() != "none" and args.skill.lower() != "all":
        bump_cmd = [sys.executable, str(bump_py), plugin_id, args.version, "--skip-sync"]
        if args.dry_run:
            bump_cmd.append("--dry-run")
        proc = run_step(bump_cmd, mp_root)
        report["steps"]["step2_bump_version"] = _parse_json_stdout(proc.stdout)
    else:
        report["steps"]["step2_bump_version"] = {"status": "skipped (version already set or target=all)"}

    # Step 3: 三端原子同步 (sync-antigravity + incremental Codex cache sync)
    sync_cmd = [sys.executable, str(setup_py), "sync-antigravity", "--marketplace-root", str(mp_root)]
    if args.dry_run:
        sync_cmd.append("--dry-run")
    proc_sync = run_step(sync_cmd, mp_root)
    sync_res = _parse_json_stdout(proc_sync.stdout)
    report["steps"]["step3_tri_platform_sync"] = sync_res
    report["codex_restart_required"] = bool((sync_res.get("syncCodex") or {}).get("codexRestartRequired", False))

    # Step 1: 分舱鲁棒性体检 (Verify post-sync 100% integrity across all 7 guardrails)
    val_cmd = [sys.executable, str(validator_py), "--marketplace-root", str(mp_root), "--json"]
    if args.skill.lower() != "all":
        val_cmd.extend(["--skill", plugin_id])
    proc_val = run_step(val_cmd, mp_root)
    val_res = _parse_json_stdout(proc_val.stdout)
    report["steps"]["step1_robustness_check"] = {
        "status": val_res["status"],
        "checked_count": val_res["checked_count"],
        "error_count": val_res["error_count"],
        "warning_count": val_res["warning_count"],
    }

    # Step 4: GitHub 远端推送
    if args.dry_run:
        report["steps"]["step4_github_release"] = {"status": "dry-run (no git commit/push executed)"}
    elif args.pr:
        git = find_git()
        if args.skill.lower() != "all":
            check_unrelated_dirty_paths(git, mp_root, plugin_id, args.allow_mixed_dirty)
        pr_cmd = [sys.executable, str(setup_py), "publish", "--one-step", "--marketplace-root", str(mp_root)]
        if args.message:
            pr_cmd.extend(["--message", args.message])
        proc_pr = run_step(pr_cmd, mp_root)
        report["steps"]["step4_github_release"] = {"mode": "pr", "output": proc_pr.stdout.strip()}
    elif args.push:
        git = find_git()
        target_ids = [plugin_id] if args.skill.lower() != "all" else None
        if args.skill.lower() != "all":
            check_unrelated_dirty_paths(git, mp_root, plugin_id, args.allow_mixed_dirty)
        check_git_ancestor_gate(git, mp_root)
        check_remote_version_no_downgrade(git, mp_root, target_ids)
        status_out = run_step([git, "status", "--porcelain=v1", "-uall"], mp_root).stdout.strip()
        remote_sha = run_step([git, "rev-parse", "origin/main"], mp_root).stdout.strip()
        if not status_out:
            head_sha = run_step([git, "rev-parse", "HEAD"], mp_root).stdout.strip()
            if head_sha != remote_sha:
                run_step([git, "push", "origin", "HEAD:main"], mp_root)
                report["steps"]["step4_github_release"] = {
                    "mode": "direct-main-push",
                    "status": "pushed-to-origin-main",
                    "commit": head_sha,
                    "recovered_unpushed_commit": True,
                }
            else:
                report["steps"]["step4_github_release"] = {
                    "mode": "direct-main-push",
                    "status": "clean-worktree-already-committed",
                    "commit": head_sha,
                }
        else:
            run_step([git, "add", "-A"], mp_root)
            msg = args.message or f"feat(skills): publish {args.skill} via E05 atomic pipeline"
            run_step([git, "commit", "-m", msg], mp_root)
            head_sha = run_step([git, "rev-parse", "HEAD"], mp_root).stdout.strip()
            run_step([git, "push", "origin", "HEAD:main"], mp_root)
            report["steps"]["step4_github_release"] = {
                "mode": "direct-main-push",
                "status": "pushed-to-origin-main",
                "commit": head_sha,
                "message": msg,
            }
    else:
        report["steps"]["step4_github_release"] = {
            "status": "local-sync-complete (pass --push to push to GitHub main, or --pr for PR flow)"
        }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
