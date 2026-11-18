#!/usr/bin/env python3
"""
Autonomous Adversarial Closed-Loop Controller for E06 & Swarm.
Orchestrates autonomous ping-pong confrontation between heterogeneous agents:
  - Author Agent (e.g. Codex 5.6 Terra / GPT-6.2 Sol) writes & refactors code
  - Critic Agent (e.g. DeepSeek-V4-Pro) audits with Reject-by-Default & counterexamples
Features:
  - Autonomous multi-round convergence without manual polling or prompt hacking
  - Real-time pause/resume and live critic switching via .swarm/critic_config.json
  - Compact HUD banner output per round matching C06/E06 aesthetic
  - Two-phase commit: only overwrites target output upon formal [STATUS: APPROVED]
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


def char_width(c: str) -> int:
    if c in ('\ufe0f', '\u200d'):
        return 0
    if ord(c) in (0x25B6, 0x27A4, 0x2714, 0x2605, 0x2022, 0x2694):  # ▶, ➔, ✔, ★, •, ⚔
        return 1
    import unicodedata
    if ord(c) > 0x1F000 or unicodedata.east_asian_width(c) in ('F', 'W'):
        return 2
    return 1


def str_width(s: str) -> int:
    return sum(char_width(c) for c in s)


def pad_box_line(content: str, total_width: int = 74) -> str:
    w = str_width(content)
    pad = total_width - w
    if pad < 0:
        pad = 0
    return "│ " + content + " " * pad + " │"


def print_loop_hud(
    round_num: int,
    max_rounds: int,
    stage: str,
    author_name: str,
    critic_name: str,
    status: str = "🟢 正在对攻",
    last_verdict: str | None = None,
    box_w: int = 74,
):
    top = "┌" + "─" * (box_w + 2) + "┐"
    mid = "├" + "─" * (box_w + 2) + "┤"
    bot = "└" + "─" * (box_w + 2) + "┘"

    verdict_str = f" │ 上轮裁决: {last_verdict}" if last_verdict else ""
    if any(k in stage for k in ("施工", "代码", "作者", "初稿", "修复")):
        stage_idx = "3"
    elif any(k in stage for k in ("审查", "质检", "挑刺")):
        stage_idx = "4"
    else:
        stage_idx = "5"

    p3 = "▶ 3.主力施工" if stage_idx == "3" else ("✔ 3.主力施工" if int(stage_idx) > 3 or round_num > 1 else "3.主力施工")
    p4 = "▶ 4.红队质检" if stage_idx == "4" else ("✔ 4.红队质检" if int(stage_idx) > 4 or status == "✔ 已批准交付" else "4.红队质检")
    p5 = "▶ 5.两相提交" if stage_idx == "5" else "5.两相提交"

    lines = [
        "",
        top,
        pad_box_line(f"📍 流水线全景进度: [阶段 {stage_idx}/5: {stage} · 轮次 {round_num}/{max_rounds}]", box_w),
        pad_box_line(f"   [✔ 1.选阵容] ➔ [✔ 2.选模型] ➔ [{p3}] ➔ [{p4}] ➔ [{p5}]", box_w),
        mid,
        pad_box_line("💡 当前状态诊断与下一步建议:", box_w),
        pad_box_line("   • 诊断:", box_w),
        pad_box_line(f"     1. 主力施工: {author_name}", box_w),
        pad_box_line(f"     2. 红队质检: {critic_name} (Reject-by-Default 严格审计)", box_w),
        pad_box_line(f"     3. 实时状态: {status}{verdict_str}", box_w),
        pad_box_line("   • 建议: 保持自治对攻，获红队 [STATUS: APPROVED] 自动两相提交", box_w),
        mid,
        pad_box_line("⌨️ 全局单字符快捷键速查（按键即走）:", box_w),
        pad_box_line("   • [0] (Pause):  紧急挂起/暂停对攻循环 (再次输入 0 恢复)", box_w),
        pad_box_line("   • [1B] (Flash): 热切为 DeepSeek V4.1 Flash 审查官", box_w),
        pad_box_line("   • [1A] (Pro):   热切为 DeepSeek V4 Pro 旗舰审计官", box_w),
        pad_box_line("   • [2D] (Codex): 热切为 Codex GPT-6.1 Sol 审查官", box_w),
        pad_box_line("   • [6A] / [6B]:  热切为 Gemini Native Pro / Flash 审查官", box_w),
        pad_box_line("   • [?] (Status): 刷新此全景进度看板与快捷键菜单", box_w),
        bot,
        "",
    ]
    print("\n".join(lines), flush=True)


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


def load_critic_config(workspace_path: Path) -> dict[str, Any]:
    cfg_file = workspace_path / ".swarm" / "critic_config.json"
    if cfg_file.is_file():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "active_code": "1A",
        "active_runner": "dsh",
        "active_model_name": "DeepSeek-V4-Pro",
        "active_model_slug": "deepseek-v4-pro",
        "paused": False,
    }


def run_cmd(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
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
    try:
        return json.loads(raw_stdout.strip())
    except json.JSONDecodeError:
        for line in reversed(raw_stdout.strip().splitlines()):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def map_runner_name(runner: str) -> str:
    if runner == "gemini":
        return "antigravity"
    return runner


def execute_author_turn(
    run_local_py: Path,
    workspace: Path,
    author_runner: str,
    author_model: str | None,
    task_desc: str,
    draft_file: Path,
    round_num: int,
    critic_feedback: str | None = None,
    session_id: str | None = None,
) -> tuple[str, str | None]:
    """Invokes the Author agent to write or repair the draft."""
    if round_num == 1 or not critic_feedback:
        prompt = (
            f"【任务目标】\n{task_desc}\n\n"
            f"【要求】\n"
            f"请针对上述任务要求，编写出完整、健壮、具备完备异常处理的高质量代码/方案。\n"
            f"将成果完整输出并更新保存至待审文件: {draft_file.name}。\n"
            f"请确保逻辑闭环，首轮交付即追求工业级标准。"
        )
    else:
        prompt = (
            f"【任务目标】\n{task_desc}\n\n"
            f"【红队审查反馈 (第 {round_num - 1} 轮)】\n"
            f"上一轮异构审查官拒绝了当前版本，并提出了如下具体缺陷与反例用例：\n"
            f"{critic_feedback}\n\n"
            f"【修订准则】\n"
            f"1. 必须针对上述审查官给出的所有反例与边界漏洞进行深度修复，严禁敷衍或回避核心缺陷。\n"
            f"2. 请更新修复后的完整代码并保存至文件: {draft_file.name}。\n"
            f"3. 在回答开头简要列出针对反例的修复点（Fix Notes）。"
        )

    actual_runner = map_runner_name(author_runner)
    cmd = [
        sys.executable,
        str(run_local_py),
        "run",
        "--runner", actual_runner,
        "--workspace", str(workspace),
        "--mode", "write",
        "--file", str(draft_file),
        "--prompt", prompt,
        "--json",
    ]
    if actual_runner == "codex" and author_model:
        valid_codex = get_valid_codex_slugs()
        if not valid_codex or author_model.lower() in valid_codex:
            cmd.extend(["--model", author_model])
    if session_id:
        cmd.extend(["--session", session_id])

    ret, stdout, stderr = run_cmd(cmd, timeout=300)
    if ret != 0:
        raise RuntimeError(f"Author ({author_runner}) failed with exit {ret}:\n{stderr}")

    data = parse_runner_json(stdout)
    if not data:
        raise RuntimeError(f"Failed to parse author output JSON: {stdout[:400]}")

    return data.get("response", ""), data.get("session_id")


def execute_critic_turn(
    run_local_py: Path,
    workspace: Path,
    critic_runner: str,
    critic_model: str | None,
    task_desc: str,
    draft_file: Path,
    round_num: int,
    max_rounds: int,
    session_id: str | None = None,
) -> tuple[str, str, str | None]:
    """Invokes the Critic agent to audit the draft with Reject-by-Default."""
    critique_prompt = (
        f"你现在担任最高标准的红队逻辑与代码对抗审查官（Adversarial Critic）。\n"
        f"原始任务目标: {task_desc}\n"
        f"当前是对抗优化的第 {round_num}/{max_rounds} 轮。\n"
        f"待审文件路径: {draft_file.name}\n\n"
        f"【严格审查与裁决准则】\n"
        f"1. 绝对默认拒绝原则 (Reject-by-Default)：严禁无原则的客套或表面赞扬。你必须假设提交的代码存在边界漏洞、并发竞态、异常泄漏或逻辑反例。\n"
        f"2. 强制反例要求 (Counter-example Requirement)：每次拒绝必须明确指出具体缺陷，并给出可复现的失败用例输入 (Corner Case) 或断言反例。\n"
        f"3. 裁决格式红线（首行必须为明确状态标签）：\n"
        f"   - 若发现任何瑕疵，第一行必须是：[STATUS: REJECT]\n"
        f"   - 仅当极尽挑刺后依然毫无瑕疵、边界完全闭环时，第一行才允许输出：[STATUS: APPROVED]\n"
        f"请仔细阅读已传入的待审文件内容，展开深度思考，输出严格的审计报告与反例。"
    )

    actual_runner = map_runner_name(critic_runner)
    cmd = [
        sys.executable,
        str(run_local_py),
        "run",
        "--runner", actual_runner,
        "--workspace", str(workspace),
        "--mode", "read",
        "--file", str(draft_file),
        "--prompt", critique_prompt,
        "--json",
    ]
    if actual_runner == "codex" and critic_model:
        valid_codex = get_valid_codex_slugs()
        if not valid_codex or critic_model.lower() in valid_codex:
            cmd.extend(["--model", critic_model])
    if session_id:
        cmd.extend(["--session", session_id])

    ret, stdout, stderr = run_cmd(cmd, timeout=300)
    if ret != 0:
        raise RuntimeError(f"Critic ({critic_runner}) failed with exit {ret}:\n{stderr}")

    data = parse_runner_json(stdout)
    if not data:
        raise RuntimeError(f"Failed to parse critic output JSON: {stdout[:400]}")

    response = data.get("response", "").strip()
    first_line = response.splitlines()[0].strip() if response else ""
    verdict = "APPROVED" if ("[STATUS: APPROVED]" in first_line or response.startswith("[STATUS: APPROVED]")) else "REJECT"

    return verdict, response, data.get("session_id")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Adversarial Closed-Loop Controller")
    parser.add_argument("--task", required=True, help="Task description or goal")
    parser.add_argument("--file", default=".swarm/draft.md", help="Working draft file path")
    parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace path")
    parser.add_argument("--author-runner", default=None, help="Author runner (default: from config or codex)")
    parser.add_argument("--author-model", default=None, help="Author model (default: from config or gpt-6.1-sol)")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum allowed adversarial rounds (default: 3)")
    parser.add_argument("--output", default=None, help="Final approved destination file (Two-phase commit)")
    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    draft_path = Path(args.file)
    if not draft_path.is_absolute():
        draft_path = workspace_path / draft_path
    draft_path.parent.mkdir(parents=True, exist_ok=True)

    if not draft_path.is_file():
        draft_path.write_text(f"# Task Draft\n\nTask: {args.task}\n\n[Pending Initial Generation]\n", encoding="utf-8")

    script_dir = Path(__file__).resolve().parent
    run_local_py = script_dir / "run_local.py"

    log_dir = workspace_path / ".swarm" / "adversarial_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    author_session = None
    critic_session = None
    last_critic_feedback = None
    round_num = 1
    final_verdict = "REJECT"

    cfg = load_critic_config(workspace_path)
    cur_author_runner = args.author_runner or cfg.get("author_runner", "codex")
    cur_author_model = args.author_model or cfg.get("author_model_slug", "gpt-6.1-sol")

    print("\n🚀 [Adversarial Swarm Loop] 双脑自治闭环对攻控制器已启动...", flush=True)

    while round_num <= args.max_rounds:
        # Check pause status
        cfg = load_critic_config(workspace_path)
        while cfg.get("paused", False):
            print_loop_hud(
                round_num,
                args.max_rounds,
                "⏸️ 已暂停 (PAUSED)",
                f"{cur_author_runner} ({cur_author_model})",
                f"{cfg.get('active_runner')} [{cfg.get('active_code', '1B')}]",
                status="🔴 用户手动暂停中",
                last_verdict=final_verdict,
            )
            print("> 对抗循环当前处于挂起状态。在外部输入 '继续' 或运行 critic_manager.py resume 恢复...", flush=True)
            time.sleep(5)
            cfg = load_critic_config(workspace_path)

        # Dynamic critic synchronization
        critic_runner = cfg.get("active_runner", "dsh")
        critic_model = cfg.get("active_model_slug", "deepseek-v4.1-flash")
        critic_code = cfg.get("active_code", "1B")
        critic_display = f"{cfg.get('active_agent_name', critic_runner)} [{critic_code}] ({cfg.get('active_model_name', critic_model)})"
        author_display = f"{cur_author_runner} ({cur_author_model})"

        # Step 1: Author Turn
        stage_title = "初稿生成" if round_num == 1 else "针对反例修复"
        print_loop_hud(
            round_num,
            args.max_rounds,
            f"作者工作: {stage_title}",
            author_display,
            critic_display,
            status="⚡ 作者正在生成/修改代码...",
            last_verdict=final_verdict if round_num > 1 else None,
        )

        try:
            author_resp, author_session = execute_author_turn(
                run_local_py,
                workspace_path,
                cur_author_runner,
                cur_author_model,
                args.task,
                draft_path,
                round_num,
                critic_feedback=last_critic_feedback,
                session_id=author_session,
            )
        except Exception as e:
            print(f"[ERROR] Author execution failed: {e}", file=sys.stderr)
            sys.exit(2)

        (log_dir / f"round_{round_num}_author.md").write_text(author_resp, encoding="utf-8")

        # Step 2: Critic Turn (Dynamic)
        cfg = load_critic_config(workspace_path)
        critic_runner = cfg.get("active_runner", "dsh")
        critic_model = cfg.get("active_model_slug", "deepseek-v4.1-flash")
        critic_code = cfg.get("active_code", "1B")
        critic_display = f"{cfg.get('active_agent_name', critic_runner)} [{critic_code}] ({cfg.get('active_model_name', critic_model)})"

        print_loop_hud(
            round_num,
            args.max_rounds,
            "异构红队挑刺",
            author_display,
            critic_display,
            status="🛡️ 审查官正在反例挑刺...",
            last_verdict=None,
        )

        try:
            verdict, critic_resp, critic_session = execute_critic_turn(
                run_local_py,
                workspace_path,
                critic_runner,
                critic_model,
                args.task,
                draft_path,
                round_num,
                args.max_rounds,
                session_id=critic_session,
            )
        except Exception as e:
            print(f"[ERROR] Critic execution failed: {e}", file=sys.stderr)
            sys.exit(3)

        final_verdict = verdict
        last_critic_feedback = critic_resp
        (log_dir / f"round_{round_num}_critic_{verdict}.md").write_text(critic_resp, encoding="utf-8")

        if verdict == "APPROVED":
            print(f"\n[CONVERGENCE] Critic approved draft at round {round_num}! Proceeding to commit.")
            break

        if round_num >= args.max_rounds:
            print(f"\n[MAX ROUNDS] Reached limit of {args.max_rounds} rounds. Exiting loop.")
            break

        print_loop_hud(
            round_num + 1,
            args.max_rounds,
            "作者根据红队反例修复",
            author_name,
            critic_name,
            status="🔧 作者正在吸纳修复...",
            last_verdict=final_verdict,
        )

        try:
            author_resp, author_session = execute_author_turn(
                run_local_py,
                workspace_path,
                args.author_runner,
                args.author_model,
                args.task,
                draft_path,
                round_num,
                critic_feedback=last_critic_feedback,
                session_id=author_session,
            )
        except Exception as e:
            print(f"[ERROR] Author execution failed: {e}", file=sys.stderr)
            sys.exit(2)

        (log_dir / f"round_{round_num}_author.md").write_text(author_resp, encoding="utf-8")

        # Step 2: Critic Turn (Dynamic)
        cfg = load_critic_config(workspace_path)
        critic_runner = cfg.get("active_runner", "dsh")
        critic_model = cfg.get("active_model_slug")
        critic_code = cfg.get("active_code", "1A")
        critic_display = f"{cfg.get('active_agent_name', critic_runner)} [{critic_code}] ({cfg.get('active_model_name', critic_model)})"

        print_loop_hud(
            round_num,
            args.max_rounds,
            "异构红队挑刺",
            author_display,
            critic_display,
            status="🛡️ 审查官正在反例挑刺...",
            last_verdict=None,
        )

        try:
            verdict, critic_resp, critic_session = execute_critic_turn(
                run_local_py,
                workspace_path,
                critic_runner,
                critic_model,
                args.task,
                draft_path,
                round_num,
                args.max_rounds,
                session_id=critic_session,
            )
        except Exception as e:
            print(f"[ERROR] Critic execution failed: {e}", file=sys.stderr)
            sys.exit(3)

        final_verdict = verdict
        last_critic_feedback = critic_resp
        (log_dir / f"round_{round_num}_critic_{verdict}.md").write_text(critic_resp, encoding="utf-8")

        # Step 3: Decision check
        if verdict == "APPROVED":
            print_loop_hud(
                round_num,
                args.max_rounds,
                "🎉 审查通过 (APPROVED)",
                author_display,
                critic_display,
                status="✔ 已批准交付",
                last_verdict="APPROVED",
            )
            print(f"✅ [CONVERGED] 方案在第 {round_num} 轮经过红队严苛反例审计，获得 [STATUS: APPROVED]！\n")

            # Two-phase commit
            if args.output:
                out_path = Path(args.output).resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"📦 [DELIVERED] 已通过两阶段提交合并落盘至: {out_path}")

            sys.exit(0)

        # Rejected: Proceed to next round
        print(f"⚠️ [ROUND {round_num}/{args.max_rounds} REJECTED] 审查官发现漏洞反例，自动进入下一轮闭环修复...\n")
        round_num += 1

    # Loop exhausted
    print_loop_hud(
        args.max_rounds,
        args.max_rounds,
        "⚠️ 达到最大轮次未完全收敛",
        author_display,
        critic_display,
        status="🟡 需人工介入走查",
        last_verdict="REJECT",
    )
    print(f"❌ [MAX ROUNDS REACHED] 对抗已进行 {args.max_rounds} 轮，最新修改与审查反例已保存在: {log_dir}")
    sys.exit(1)


if __name__ == "__main__":
    main()
