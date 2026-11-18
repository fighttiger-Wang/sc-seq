#!/usr/bin/env python3
"""
Adversarial Review Engine for E06 & Swarm Integration.
Orchestrates deep critique from local external Agents (DeepSeek, Claude, Codex, etc.)
with session tracking, structured anti-compromise protocols, and zero-truncation file I/O.
Supports real-time pause and zero-crash dynamic model validation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def get_valid_codex_slugs() -> set[str]:
    codex_cache = Path.home() / ".codex" / "models_cache.json"
    valid_slugs = set()
    if codex_cache.is_file():
        try:
            data = json.loads(codex_cache.read_text(encoding="utf-8"))
            for m in data.get("models", []):
                if m.get("slug"):
                    valid_slugs.add(m["slug"].lower())
        except Exception:
            pass
    return valid_slugs


def main():
    parser = argparse.ArgumentParser(description="E06 Adversarial Reviewer Bridge")
    parser.add_argument("--draft", required=True, help="Path to draft file to be audited")
    parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace path")
    parser.add_argument("--runner", default="dsh", help="Default critic runner agent if not configured dynamically")
    parser.add_argument("--model", default=None, help="Specific model parameter")
    parser.add_argument("--session", default=None, help="Previous session_id for continuity")
    parser.add_argument("--round", type=int, default=1, help="Current adversarial round")
    parser.add_argument("--max-rounds", type=int, default=4, help="Maximum allowed rounds")
    parser.add_argument("--output", default=None, help="Path to write the full critic report")
    args = parser.parse_args()

    draft_path = Path(args.draft).resolve()
    if not draft_path.is_file():
        sys.stderr.write(f"[ERROR] Draft file not found: {draft_path}\n")
        sys.exit(1)

    workspace_path = Path(args.workspace).resolve()
    script_dir = Path(__file__).resolve().parent
    run_local_py = script_dir / "run_local.py"

    # Check real-time dynamic configuration from critic_config.json
    active_runner = args.runner
    active_model = args.model
    active_code = "1A"
    cfg_file = workspace_path / ".swarm" / "critic_config.json"
    if cfg_file.is_file():
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            if cfg.get("paused"):
                result_payload = {
                    "status": "PAUSED",
                    "round": args.round,
                    "max_rounds": args.max_rounds,
                    "board_message": "@coordinator [PAUSED] 对抗审查已被用户手动暂停。等待用户输入 '继续' 或执行切换指令恢复。",
                }
                print(json.dumps(result_payload, ensure_ascii=False, indent=2))
                sys.exit(0)
            if cfg.get("active_runner"):
                active_runner = cfg["active_runner"]
            if cfg.get("active_model_slug"):
                active_model = cfg["active_model_slug"]
            elif cfg.get("active_model_param"):
                active_model = cfg["active_model_param"]
            if cfg.get("active_code"):
                active_code = cfg["active_code"]
        except Exception:
            pass

    # Dynamic Validation for Codex Models to avoid CLI crashing on unknown slugs
    safe_model_to_pass = None
    if active_runner == "codex" and active_model:
        valid_codex = get_valid_codex_slugs()
        if valid_codex:
            if active_model.lower() in valid_codex:
                safe_model_to_pass = active_model
            else:
                # Fallback: do not pass an invalid model slug; let Codex use its validated default
                safe_model_to_pass = None
        else:
            safe_model_to_pass = active_model

    # Construct adversarial system prompt with strict zero-compromise rules
    critique_prompt = (
        f"你现在担任最高标准的红队逻辑与代码对抗审查官（Adversarial Critic）。\n"
        f"当前是对抗优化的第 {args.round}/{args.max_rounds} 轮。\n"
        f"待审文件路径: {draft_path.name}\n\n"
        f"【严格审查与裁决准则】\n"
        f"1. 绝对默认拒绝原则 (Reject-by-Default)：严禁任何无原则的客套或表面赞扬。你必须假设提交的内容存在逻辑死角、边界异常、性能隐患或未被测试覆盖的假设漏洞。\n"
        f"2. 必须附带反例 (Counter-example Requirement)：每次拒绝必须明确指出具体缺陷，并给出可执行的失败用例输入 (Corner Case) 或明确的逻辑反例断言。\n"
        f"3. 裁决格式红线（首行必须为明确状态）：\n"
        f"   - 若发现任何瑕疵，第一行必须是：[STATUS: REJECT]\n"
        f"   - 仅当经过极尽挑刺后依然毫无瑕疵、边界完全闭环时，第一行才允许输出：[STATUS: APPROVED]\n"
        f"请仔细阅读已传入的待审文件内容，展开深度思考，输出严格的审计报告与反例。"
    )

    cmd = [
        sys.executable,
        str(run_local_py),
        "run",
        "--runner", active_runner,
        "--workspace", str(workspace_path),
        "--mode", "read",
        "--file", str(draft_path),
        "--prompt", critique_prompt,
        "--json",
    ]
    if safe_model_to_pass:
        cmd.extend(["--model", safe_model_to_pass])
    if args.session:
        cmd.extend(["--session", args.session])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"[ERROR] Critic ({active_runner}) review timed out after 300 seconds.\n")
        sys.exit(2)

    raw_output = proc.stdout.strip()
    if proc.returncode != 0:
        sys.stderr.write(f"[ERROR] Runner failed with code {proc.returncode}:\n{proc.stderr}\n")
        sys.exit(proc.returncode)

    # Parse JSON output from delegate.py
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        data = None
        for line in reversed(raw_output.splitlines()):
            try:
                data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
        if not data:
            sys.stderr.write(f"[ERROR] Failed to parse JSON from runner output: {raw_output[:500]}\n")
            sys.exit(3)

    session_id = data.get("session_id")
    response_text = data.get("response", "").strip()

    # Determine verdict from first lines
    first_line = response_text.splitlines()[0].strip() if response_text else ""
    if "[STATUS: APPROVED]" in first_line or response_text.startswith("[STATUS: APPROVED]"):
        verdict = "APPROVED"
    else:
        verdict = "REJECT"

    # Save full report if requested
    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(response_text, encoding="utf-8")

    # Generate ready-to-post message for the swarm board
    first_paragraph = "\n".join(response_text.splitlines()[:5])
    if verdict == "APPROVED":
        board_msg = f"@author [ROUND {args.round}/{args.max_rounds}] [VERDICT: APPROVED] 方案已通过 {active_runner} [{active_code}] 红队极端边界审计。"
    else:
        board_msg = (
            f"@author [ROUND {args.round}/{args.max_rounds}] REJECT: "
            f"{active_runner} [{active_code}] 审查发现漏洞，报告已写入 {args.output or '审查报告'}。\n"
            f"核心问题摘要:\n{first_paragraph}"
        )

    result_payload = {
        "status": "SUCCESS",
        "runner": active_runner,
        "code": active_code,
        "round": args.round,
        "max_rounds": args.max_rounds,
        "verdict": verdict,
        "session_id": session_id,
        "report_file": str(args.output) if args.output else None,
        "board_message": board_msg,
        "response_excerpt": first_paragraph,
    }

    print(json.dumps(result_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
