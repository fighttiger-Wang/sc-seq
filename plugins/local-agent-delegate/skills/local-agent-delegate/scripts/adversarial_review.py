#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adversarial Review Engine for E06 & Swarm Integration v1.0.0.
特性：
1. 读取 <2KB 的 models_fast_cache.json 代替 603KB 的 models_cache.json
2. 支持内置免费模型 (1A~4A, runner='native') 与显式付费外援 (8A/8B dsh, 9A/9B codex)
3. 针对 dsh 与 codex 均正确透传 --model 参数
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(description="E06 Adversarial Reviewer Bridge v1.0.0")
    parser.add_argument("--draft", required=True, help="待审草稿文件路径")
    parser.add_argument("--workspace", default=os.getcwd(), help="工作区路径")
    parser.add_argument("--runner", default="native", help="默认审查引擎 (native/dsh/codex)")
    parser.add_argument("--model", default="gemini-4-neon-high", help="模型 slug")
    parser.add_argument("--session", default=None, help="续接会话 ID")
    parser.add_argument("--round", type=int, default=1, help="当前轮次")
    parser.add_argument("--max-rounds", type=int, default=3, help="最大轮次")
    parser.add_argument("--output", default=None, help="审查报告输出路径")
    parser.add_argument("--dry-run", action="store_true", help="仅验证配置与命令，不启动外部进程")
    args = parser.parse_args()

    draft_path = Path(args.draft).resolve()
    workspace_path = Path(args.workspace).resolve()
    run_local_py = SCRIPT_DIR / "run_local.py"

    active_runner = args.runner
    active_model = args.model
    active_code = "4A"
    fallback_chain = ["gemini-4-neon-high", "claude-opus-5-5-high", "gemini-4-argon-high"]

    cfg_file = workspace_path / ".swarm" / "critic_config.json"
    if cfg_file.is_file():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            if cfg.get("paused"):
                print(json.dumps({
                    "status": "PAUSED",
                    "round": args.round,
                    "max_rounds": args.max_rounds,
                    "board_message": "@coordinator [PAUSED] 对抗审查已暂停。",
                }, ensure_ascii=False, indent=2))
                sys.exit(0)
            active_runner = cfg.get("active_runner", active_runner)
            active_model = cfg.get("active_model_slug", active_model)
            active_code = cfg.get("active_code", active_code)
            fallback_chain = cfg.get("critic_fallback_chain", fallback_chain)
        except Exception:
            pass

    if active_runner == "native":
        payload = {
            "status": "NATIVE_CRITIC_READY",
            "dispatch_mode": "native",
            "code": active_code,
            "runner": "native",
            "model_slug": active_model,
            "fallback_chain": fallback_chain,
            "round": args.round,
            "max_rounds": args.max_rounds,
            "draft": str(draft_path),
            "swarm_critic_args": {
                "action": "add",
                "name": "critic",
                "model": active_model,
                "brief": f"作为红方审查官([{active_code}] {active_model})，以 Reject-by-Default 原则审查 {draft_path} 并给出具体反例；通过则首行输出 [STATUS: APPROVED]，否则输出 [STATUS: REJECT]。",
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    if not draft_path.is_file():
        sys.stderr.write(f"[ERROR] Draft file not found: {draft_path}\n")
        sys.exit(1)

    safe_model = active_model
    if active_runner == "codex" and active_model:
        valid_codex = get_valid_codex_slugs()
        if valid_codex and active_model.lower() not in valid_codex:
            safe_model = None

    critique_prompt = (
        f"你现在担任最高标准的红队逻辑与代码对抗审查官（Adversarial Critic）。\n"
        f"当前是对抗优化的第 {args.round}/{args.max_rounds} 轮。待审文件: {draft_path.name}\n"
        f"1. Reject-by-Default：必须排查边界异常、竞态与逻辑漏洞并给出反例。\n"
        f"2. 若发现任何瑕疵，首行必须是：[STATUS: REJECT]；仅当毫无瑕疵时首行输出：[STATUS: APPROVED]"
    )

    cmd = [
        sys.executable,
        str(run_local_py),
        "run",
        "--runner",
        active_runner,
        "--workspace",
        str(workspace_path),
        "--mode",
        "read",
        "--file",
        str(draft_path),
        "--prompt",
        critique_prompt,
        "--json",
    ]
    if safe_model:
        cmd.extend(["--model", safe_model])
    if args.session:
        cmd.extend(["--session", args.session])
    if args.dry_run:
        cmd.append("--dry-run")

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if proc.returncode != 0:
        sys.stderr.write(f"[ERROR] Runner failed ({proc.returncode}):\n{proc.stderr}\n")
        sys.exit(proc.returncode)

    data = json.loads(proc.stdout.strip().splitlines()[-1])
    if args.dry_run:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        sys.exit(0)

    response_text = data.get("response", "").strip()
    first_line = response_text.splitlines()[0].strip() if response_text else ""
    verdict = "APPROVED" if "[STATUS: APPROVED]" in first_line else "REJECT"
    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(response_text, encoding="utf-8")

    print(json.dumps({
        "status": "SUCCESS",
        "runner": active_runner,
        "code": active_code,
        "model": safe_model,
        "verdict": verdict,
        "session_id": data.get("session_id"),
        "report_file": args.output,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
