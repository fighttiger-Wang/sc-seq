#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autonomous Adversarial Closed-Loop Controller for E06 · 红蓝对抗闭环 v1.2.0
特性：
1. 默认 1 号双周期异构王牌阵容：[9B] Codex GPT-6.2 Sol ⚔ [4A] Gemini 4 Neon High
2. 自动读取最新 ~/.codex/models_cache.json 感知 Codex Free/受限状态，并按三大独立内置池跨池接力
3. 按量付费 DeepSeek (8A/8B) 永不自动调用，仅前两级异常且传 --user-confirmed 时才允许执行（附半价时段提示）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FAST_CACHE_FILE = SCRIPT_DIR / "models_fast_cache.json"
BJ_TZ = timezone(timedelta(hours=8))

QUOTA_BUCKETS: dict[str, set[str]] = {
    "neon_5h": {
        "neon", "neon_5h",
        "gemini-pro-orchestrator-neon", "gemini-4-neon-xhigh", "gemini-4-neon-high",
        "gemini-4-neon-medium", "gemini-4-neon-low", "gemini-4-hydrogen-xhigh",
        "gemini-4-hydrogen-high", "gemini-4-hydrogen-medium", "gemini-4-hydrogen-low",
        "gemini-3.8-flash-high", "gemini-3.8-flash-medium", "gemini-3.8-flash-low",
    },
    "claude_5h": {
        "claude", "claude_5h",
        "claude-opus-5-5-high", "claude-opus-5-5-medium", "claude-opus-5-5-low",
        "claude-sonnet-5-5-high", "claude-sonnet-5-5-medium", "claude-sonnet-5-5-low",
        "gpt-oss-120b-medium",
    },
    "argon_weekly": {
        "argon", "argon_weekly",
        "gemini-4-argon-high", "gemini-4-argon-medium", "gemini-4-argon-low",
        "gemini-pro-orchestrator-g1-pro",
    },
}


def expand_exhausted(raw_set: set[str]) -> set[str]:
    expanded = {x.strip().lower() for x in raw_set if x.strip()}
    for members in QUOTA_BUCKETS.values():
        if expanded & members:
            expanded.update(members)
    return expanded


def is_deepseek_half_price_window() -> tuple[bool, str]:
    bj_now = datetime.now(BJ_TZ)
    in_win = (0, 30) <= (bj_now.hour, bj_now.minute) < (8, 30)
    return in_win, bj_now.strftime("%H:%M")


def get_valid_codex_slugs() -> set[str]:
    src = Path.home() / ".codex" / "models_cache.json"
    if src.is_file():
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            slugs = {
                m["slug"].lower()
                for m in data.get("models", [])
                if m.get("slug") and not m["slug"].endswith("-auto-review") and m["slug"] != "gpt-reserve"
            }
            if slugs:
                return slugs
        except Exception:
            pass
    for candidate in (FAST_CACHE_FILE, Path.home() / ".codex" / "models_fast_cache.json"):
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return {s.lower() for s in data.get("valid_codex_slugs", [])}
            except Exception:
                pass
    return {"gpt-6.2-sol", "gpt-6.1-sol", "gpt-6.2-astra", "gpt-6.1-terra"}


def load_critic_config(workspace_path: Path) -> dict[str, Any]:
    cfg_file = workspace_path / ".swarm" / "critic_config.json"
    if cfg_file.is_file():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            if data.get("schema_version") == "2.1":
                return data
        except Exception:
            pass
    return {
        "schema_version": "2.1",
        "mode": "codex_plus_native",
        "active_lineup": "1",
        "author_code": "9B",
        "author_runner": "codex",
        "author_model_name": "Codex GPT-6.2 Sol (主力编码)",
        "author_model_slug": "gpt-6.2-sol",
        "author_fallback_chain": [
            "gpt-6.2-sol",
            "gpt-6.1-sol",
            "claude-sonnet-5-5-medium",
            "gemini-4-hydrogen-medium",
            "gemini-4-argon-medium",
        ],
        "active_code": "4A",
        "active_runner": "native",
        "active_model_name": "Gemini 4 Neon High (Neon池)",
        "active_model_slug": "gemini-4-neon-high",
        "critic_fallback_chain": [
            "gemini-4-neon-high",
            "gemini-4-neon-xhigh",
            "claude-opus-5-5-high",
            "gemini-4-argon-high",
        ],
        "payg_ask_first": False,
        "external_paid_locked": True,
        "paused": False,
    }


def resolve_chain_model(
    primary_runner: str,
    primary: str,
    chain: list[str],
    exhausted: set[str],
    valid_codex: set[str],
) -> tuple[str, str, bool]:
    candidates = [primary] + [c for c in chain if c != primary]
    for idx, cand in enumerate(candidates):
        cand_l = cand.lower()
        is_codex_slug = cand_l.startswith("gpt-6") or cand_l.startswith("gpt-5")
        if is_codex_slug:
            if "codex" in exhausted or cand_l in exhausted:
                continue
            if valid_codex and cand_l not in valid_codex:
                continue
            return "codex", cand, (idx > 0 or primary_runner != "codex")
        else:
            if cand_l in exhausted:
                continue
            return "native", cand, (idx > 0 or primary_runner != "native")
    return primary_runner, primary, True


def run_cmd(cmd: list[str], timeout: int = 900) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_runner_json(raw_stdout: str) -> dict[str, Any] | None:
    for line in reversed(raw_stdout.strip().splitlines()):
        try:
            val = json.loads(line)
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            continue
    return None


def execute_cli_turn(
    run_local_py: Path,
    workspace: Path,
    runner: str,
    model_slug: str | None,
    mode: str,
    draft_file: Path,
    prompt: str,
    session_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(run_local_py),
        "run",
        "--runner",
        runner,
        "--workspace",
        str(workspace),
        "--mode",
        mode,
        "--file",
        str(draft_file),
        "--prompt",
        prompt,
        "--json",
    ]
    if model_slug:
        cmd.extend(["--model", model_slug])
    if session_id:
        cmd.extend(["--session", session_id])
    if dry_run:
        cmd.append("--dry-run")

    ret, stdout, stderr = run_cmd(cmd, timeout=900)
    if ret != 0:
        raise RuntimeError(f"Runner ({runner}) failed with exit {ret}:\n{stderr}")
    data = parse_runner_json(stdout)
    if not data:
        raise RuntimeError(f"Failed to parse JSON from {runner}: {stdout[:300]}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="E06 双脑红蓝对抗闭环控制器 v1.2.0")
    parser.add_argument("--task", required=True, help="任务描述或任务文件路径")
    parser.add_argument("--file", default=".swarm/draft.md", help="待审草稿文件路径")
    parser.add_argument("--workspace", default=os.getcwd(), help="工作区根目录")
    parser.add_argument("--author-runner", default=None, help="覆盖蓝方引擎 (codex/native/dsh)")
    parser.add_argument("--author-model", default=None, help="覆盖蓝方模型 slug")
    parser.add_argument("--critic-runner", default=None, help="覆盖红方引擎 (native/codex/dsh)")
    parser.add_argument("--critic-model", default=None, help="覆盖红方模型 slug")
    parser.add_argument("--exhausted", default="", help="已耗尽的模型 slug 或桶名（逗号分隔，自动跨池接力）")
    parser.add_argument("--max-rounds", type=int, default=3, help="最大对抗轮数")
    parser.add_argument("--output", default=None, help="两阶段提交正式落盘路径")
    parser.add_argument("--dry-run", action="store_true", help="干跑验证双脑路由、额度接力与命令参数")
    parser.add_argument("--user-confirmed", action="store_true", help="按量付费 DeepSeek 已获用户明确确认")
    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    cfg = load_critic_config(workspace_path)
    exhausted_set = expand_exhausted({s.strip() for s in args.exhausted.split(",") if s.strip()})
    valid_codex = get_valid_codex_slugs()

    author_runner_req = args.author_runner or cfg.get("author_runner", "codex")
    author_primary = args.author_model or cfg.get("author_model_slug", "gpt-6.2-sol")
    author_chain = cfg.get("author_fallback_chain", [author_primary])
    if author_runner_req == "dsh":
        author_runner, author_model, author_fb = "dsh", author_primary, False
    else:
        author_runner, author_model, author_fb = resolve_chain_model(
            author_runner_req, author_primary, author_chain, exhausted_set, valid_codex
        )

    critic_runner_req = args.critic_runner or cfg.get("active_runner", "native")
    critic_primary = args.critic_model or cfg.get("active_model_slug", "gemini-4-neon-high")
    critic_chain = cfg.get("critic_fallback_chain", [critic_primary])
    if critic_runner_req == "dsh":
        critic_runner, critic_model, critic_fb = "dsh", critic_primary, False
    else:
        critic_runner, critic_model, critic_fb = resolve_chain_model(
            critic_runner_req, critic_primary, critic_chain, exhausted_set, valid_codex
        )

    payg_used = (author_runner == "dsh" or critic_runner == "dsh")
    half_price, bj_time = is_deepseek_half_price_window()
    if payg_used and not args.dry_run and not args.user_confirmed:
        print(json.dumps({
            "status": "ASK_USER_CONFIRMATION_REQUIRED",
            "ask_user_required": True,
            "deepseek_half_price_window": half_price,
            "beijing_time": bj_time,
            "message": "所选阵容包含按量付费 DeepSeek，请先向用户确认（提示 00:30-08:30 半价时段）后加 --user-confirmed 启动。",
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    draft_path = Path(args.file)
    if not draft_path.is_absolute():
        draft_path = workspace_path / draft_path
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    if not draft_path.is_file():
        draft_path.write_text(f"# Task Draft\n\nTask: {args.task}\n", encoding="utf-8")

    if author_runner == "native" or critic_runner == "native":
        plan = {
            "status": "HYBRID_ADVERSARIAL_PLAN_READY" if (author_runner != critic_runner) else "NATIVE_ADVERSARIAL_PLAN_READY",
            "lineup": cfg.get("active_lineup", "1"),
            "payg_external_triggered": payg_used,
            "max_rounds": args.max_rounds,
            "draft_file": str(draft_path),
            "final_output": str(Path(args.output).resolve()) if args.output else None,
            "author": {
                "code": cfg.get("author_code", "9B"),
                "runner": author_runner,
                "primary_model": author_primary,
                "selected_model": author_model,
                "fallback_triggered": author_fb,
                "fallback_chain": author_chain,
            },
            "critic": {
                "code": cfg.get("active_code", "4A"),
                "runner": critic_runner,
                "primary_model": critic_primary,
                "selected_model": critic_model,
                "fallback_triggered": critic_fb,
                "fallback_chain": critic_chain,
            },
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        sys.exit(0)

    run_local_py = SCRIPT_DIR / "run_local.py"
    if args.dry_run:
        a_res = execute_cli_turn(run_local_py, workspace_path, author_runner, author_model, "write", draft_path, args.task, dry_run=True)
        c_res = execute_cli_turn(run_local_py, workspace_path, critic_runner, critic_model, "read", draft_path, args.task, dry_run=True)
        print(json.dumps({
            "status": "EXTERNAL_ADVERSARIAL_DRY_RUN",
            "payg_external_triggered": payg_used,
            "ask_user_required": (payg_used and not args.user_confirmed),
            "deepseek_half_price_window": half_price if payg_used else None,
            "author_dry_run": a_res,
            "critic_dry_run": c_res,
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    author_session = None
    critic_session = None
    feedback = None
    for round_num in range(1, args.max_rounds + 1):
        a_prompt = args.task if not feedback else f"原始任务：{args.task}\n请根据上一轮红队反例修复 {draft_path.name}：\n{feedback}"
        a_data = execute_cli_turn(run_local_py, workspace_path, author_runner, author_model, "write", draft_path, a_prompt, session_id=author_session)
        author_session = a_data.get("session_id")

        c_prompt = f"担任红队审查官审查 {draft_path.name}（第{round_num}/{args.max_rounds}轮）。首行必须输出 [STATUS: REJECT] 或 [STATUS: APPROVED] 并附具体反例。"
        c_data = execute_cli_turn(run_local_py, workspace_path, critic_runner, critic_model, "read", draft_path, c_prompt, session_id=critic_session)
        critic_session = c_data.get("session_id")
        resp = (c_data.get("response") or "").strip()
        if resp.startswith("[STATUS: APPROVED]") or "[STATUS: APPROVED]" in (resp.splitlines()[0] if resp else ""):
            if args.output:
                out_p = Path(args.output).resolve()
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(json.dumps({"status": "APPROVED", "round": round_num, "output": args.output}, ensure_ascii=False, indent=2))
            sys.exit(0)
        feedback = resp

    print(json.dumps({"status": "MAX_ROUNDS_REACHED", "rounds": args.max_rounds}, ensure_ascii=False, indent=2))
    sys.exit(1)


if __name__ == "__main__":
    main()
