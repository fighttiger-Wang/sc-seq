#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autonomous Adversarial Closed-Loop Controller for E06 v1.0.0.
特性：
1. 默认采用内置 0 额外付费王牌异构阵容：[2A] Claude Sonnet 5.5 ⚔ [4A] Gemini 4 Neon High
2. 内置同工种额度耗尽自动顺延接力链（Quota Fallback Chain）
3. 读取 <2KB 的 models_fast_cache.json 代替 603KB 的 models_cache.json
4. 当蓝红双方为内置模型 (runner='native') 时，秒级生成原生 Swarm 双脑对抗编排方案或支持 --exhausted 额度接力验证；当显式指定 8/9 付费外援时，正确向 dsh/codex 传入 --model 参数驱动多轮闭环对攻。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FAST_CACHE_FILE = SCRIPT_DIR / "models_fast_cache.json"


def get_valid_codex_slugs() -> set[str]:
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
            if data.get("schema_version") == "2.0":
                return data
        except Exception:
            pass
    return {
        "schema_version": "2.0",
        "mode": "native_first",
        "active_lineup": "1",
        "author_code": "2A",
        "author_runner": "native",
        "author_model_name": "Claude Sonnet 5.5 (High)",
        "author_model_slug": "claude-sonnet-5-5-high",
        "author_fallback_chain": [
            "claude-sonnet-5-5-high",
            "claude-sonnet-5-5-medium",
            "gemini-4-hydrogen-high",
            "gemini-4-argon-medium",
            "gpt-oss-120b-medium",
        ],
        "active_code": "4A",
        "active_runner": "native",
        "active_model_name": "Gemini 4 Neon (High)",
        "active_model_slug": "gemini-4-neon-high",
        "critic_fallback_chain": [
            "gemini-4-neon-high",
            "gemini-4-neon-xhigh",
            "claude-opus-5-5-high",
            "gemini-4-argon-high",
        ],
        "external_paid_locked": True,
        "paused": False,
    }


def resolve_chain_model(primary: str, chain: list[str], exhausted: set[str]) -> tuple[str, bool]:
    if primary not in exhausted:
        return primary, False
    for cand in chain:
        if cand not in exhausted:
            return cand, True
    return primary, True


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
        if runner == "codex":
            valid = get_valid_codex_slugs()
            if not valid or model_slug.lower() in valid:
                cmd.extend(["--model", model_slug])
        else:
            # dsh or other runners receive --model properly
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
    parser = argparse.ArgumentParser(description="E06 双脑红蓝对抗闭环控制器 v1.0.0")
    parser.add_argument("--task", required=True, help="任务描述或任务文件路径")
    parser.add_argument("--file", default=".swarm/draft.md", help="待审草稿文件路径")
    parser.add_argument("--workspace", default=os.getcwd(), help="工作区根目录")
    parser.add_argument("--author-runner", default=None, help="覆盖蓝方引擎 (native/codex/dsh)")
    parser.add_argument("--author-model", default=None, help="覆盖蓝方模型 slug")
    parser.add_argument("--critic-runner", default=None, help="覆盖红方引擎 (native/dsh/codex)")
    parser.add_argument("--critic-model", default=None, help="覆盖红方模型 slug")
    parser.add_argument("--exhausted", default="", help="已耗尽额度的模型 slug 列表（逗号分隔，自动触发替补接力）")
    parser.add_argument("--max-rounds", type=int, default=3, help="最大对抗轮数")
    parser.add_argument("--output", default=None, help="两阶段提交正式落盘路径")
    parser.add_argument("--dry-run", action="store_true", help="干跑验证双脑路由、额度接力与命令参数")
    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    cfg = load_critic_config(workspace_path)
    exhausted_set = {s.strip() for s in args.exhausted.split(",") if s.strip()}

    author_runner = args.author_runner or cfg.get("author_runner", "native")
    author_primary = args.author_model or cfg.get("author_model_slug", "claude-sonnet-5-5-high")
    author_chain = cfg.get("author_fallback_chain", [author_primary])
    author_model, author_fb = resolve_chain_model(author_primary, author_chain, exhausted_set)

    critic_runner = args.critic_runner or cfg.get("active_runner", "native")
    critic_primary = args.critic_model or cfg.get("active_model_slug", "gemini-4-neon-high")
    critic_chain = cfg.get("critic_fallback_chain", [critic_primary])
    critic_model, critic_fb = resolve_chain_model(critic_primary, critic_chain, exhausted_set)

    draft_path = Path(args.file)
    if not draft_path.is_absolute():
        draft_path = workspace_path / draft_path
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    if not draft_path.is_file():
        draft_path.write_text(f"# Task Draft\n\nTask: {args.task}\n", encoding="utf-8")

    # 若蓝红任一方为客户端内置模型 (native) 或开启 --dry-run，返回完整的双脑编排与接力凭证
    if (author_runner == "native" and critic_runner == "native") or (args.dry_run and (author_runner == "native" or critic_runner == "native")):
        plan = {
            "status": "NATIVE_ADVERSARIAL_PLAN_READY",
            "lineup": cfg.get("active_lineup", "1"),
            "paid_external_triggered": (author_runner != "native" or critic_runner != "native"),
            "max_rounds": args.max_rounds,
            "draft_file": str(draft_path),
            "final_output": str(Path(args.output).resolve()) if args.output else None,
            "author": {
                "code": cfg.get("author_code", "2A"),
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
            "swarm_orchestration": [
                {
                    "action": "add",
                    "name": "author",
                    "model": author_model,
                    "workspace": "inherit",
                    "brief": f"【蓝方主力施工】完成任务：{args.task}，写入草稿 {draft_path}，完成后 @critic 发起红队审查。",
                },
                {
                    "action": "add",
                    "name": "critic",
                    "model": critic_model,
                    "workspace": "inherit",
                    "brief": f"【红方反例挑刺】按 Reject-by-Default 严格审查 {draft_path}，给出边界反例；通过则首行输出 [STATUS: APPROVED]，否则输出 [STATUS: REJECT] 并 @author 修复。",
                },
            ],
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        sys.exit(0)

    run_local_py = SCRIPT_DIR / "run_local.py"
    if args.dry_run:
        a_res = execute_cli_turn(run_local_py, workspace_path, author_runner, author_model, "write", draft_path, args.task, dry_run=True)
        c_res = execute_cli_turn(run_local_py, workspace_path, critic_runner, critic_model, "read", draft_path, args.task, dry_run=True)
        print(json.dumps({
            "status": "PAID_EXTERNAL_ADVERSARIAL_DRY_RUN",
            "paid_external_triggered": True,
            "author_dry_run": a_res,
            "critic_dry_run": c_res,
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    # Real external CLI loop when explicitly invoked with 8/9 lineups
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
