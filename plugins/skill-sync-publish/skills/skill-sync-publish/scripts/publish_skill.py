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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


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
    for candidate in (
        Path(r"E:\A002-Codex\工作区\local-marketplace-stable-20260916-193427-e53a557c"),
        Path(r"E:\A002-Codex\工作区\sc-seq"),
    ):
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


def run_step(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed (exit {proc.returncode}): {' '.join(cmd)}\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
    return proc


def main() -> None:
    parser = argparse.ArgumentParser(description="E05 · Skill同步发布 4 步原子级流水线 v0.1.0")
    parser.add_argument("skill", nargs="?", default="all", help="目标 Skill ID 或中文名（传 all 则体检并同步全部）")
    parser.add_argument("--version", default="none", help="版本递增策略: auto, patch, minor, major, X.Y.Z, 或 none (已升版)")
    parser.add_argument("--marketplace-root", type=Path, default=None, help="权威 Marketplace 根目录")
    parser.add_argument("--push", action="store_true", help="直接 Commit 并 Push 至 GitHub main 分支")
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

    # Step 2 (pre-sync bump if requested)
    if args.version.lower() != "none" and args.skill.lower() != "all":
        bump_cmd = [sys.executable, str(bump_py), plugin_id, args.version, "--skip-sync"]
        if args.dry_run:
            bump_cmd.append("--dry-run")
        proc = run_step(bump_cmd, mp_root)
        report["steps"]["step2_bump_version"] = json.loads(proc.stdout.strip())
    else:
        report["steps"]["step2_bump_version"] = {"status": "skipped (version already set or target=all)"}

    # Step 3: 三端原子同步 (sync-antigravity)
    sync_cmd = [sys.executable, str(setup_py), "sync-antigravity", "--marketplace-root", str(mp_root)]
    if args.dry_run:
        sync_cmd.append("--dry-run")
    proc_sync = run_step(sync_cmd, mp_root)
    report["steps"]["step3_tri_platform_sync"] = json.loads(proc_sync.stdout.strip())

    # Step 1: 分舱鲁棒性体检 (Verify post-sync 100% integrity across all 5 guardrails)
    val_cmd = [sys.executable, str(validator_py), "--marketplace-root", str(mp_root), "--json"]
    if args.skill.lower() != "all":
        val_cmd.extend(["--skill", plugin_id])
    proc_val = run_step(val_cmd, mp_root)
    val_res = json.loads(proc_val.stdout.strip())
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
        pr_cmd = [sys.executable, str(setup_py), "publish", "--one-step", "--marketplace-root", str(mp_root)]
        if args.message:
            pr_cmd.extend(["--message", args.message])
        proc_pr = run_step(pr_cmd, mp_root)
        report["steps"]["step4_github_release"] = {"mode": "pr", "output": proc_pr.stdout.strip()}
    elif args.push:
        git = find_git()
        status_out = run_step([git, "status", "--porcelain"], mp_root).stdout.strip()
        if not status_out:
            head_sha = run_step([git, "rev-parse", "HEAD"], mp_root).stdout.strip()
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
