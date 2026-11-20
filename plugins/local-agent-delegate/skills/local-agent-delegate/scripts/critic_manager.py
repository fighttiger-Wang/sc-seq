#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Critic & Lineup Manager for E06 · 红蓝对抗闭环 v1.2.0
特性：
1. 与 E07 100% 共用三级阶梯统一模型代号矩阵（9A~9D Codex周期订阅 ➔ 1A~4A 客户端内置三独立池 ➔ 8A/8B DeepSeek按量咨询）
2. 默认 1 号阵容为双周期异构王牌：[9B] Codex GPT-6.2 Sol ⚔ [4A] Gemini 4 Neon High
   （Codex 处于 Free 或耗尽时，蓝方自动退回客户端内置 [2A] Claude Sonnet 5.5 ➔ [2B] Gemini 4 Hydrogen）
3. 支持三大独立内置配额池跨池接力（Neon 5h / Claude 5h / Argon 周池），绝不误触发按量付费 DeepSeek
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FAST_CACHE_FILE = SCRIPT_DIR / "models_fast_cache.json"

UNIFIED_MODELS: dict[str, dict[str, Any]] = {
    # Tier 1: Codex 周期订阅优先池
    "9A": {
        "code": "9A",
        "pool": "9",
        "pool_name": "🥇 Codex 周期订阅池 (Tier 1)",
        "tier": "codex_subscription",
        "runner": "codex",
        "name": "Codex GPT-6.2 Astra (旗舰)",
        "slug": "gpt-6.2-astra",
        "quota": "周期订阅",
        "fallback_chain": ["gpt-6.2-astra", "gpt-6.2-sol", "gemini-4-argon-medium", "claude-opus-5-5-medium"],
        "desc": "复杂工程/架构重构蓝方旗舰",
    },
    "9B": {
        "code": "9B",
        "pool": "9",
        "pool_name": "🥇 Codex 周期订阅池 (Tier 1)",
        "tier": "codex_subscription",
        "runner": "codex",
        "name": "Codex GPT-6.2 Sol (主力编码)",
        "slug": "gpt-6.2-sol",
        "quota": "周期订阅",
        "fallback_chain": ["gpt-6.2-sol", "gpt-6.1-sol", "claude-sonnet-5-5-medium", "gemini-4-hydrogen-medium", "gemini-4-argon-medium"],
        "desc": "双周期异构蓝方首选 · 吃满 Codex 订阅额度",
    },
    "9C": {
        "code": "9C",
        "pool": "9",
        "pool_name": "🥇 Codex 周期订阅池 (Tier 1)",
        "tier": "codex_subscription",
        "runner": "codex",
        "name": "Codex GPT-6.1 Terra (视觉UI)",
        "slug": "gpt-6.1-terra",
        "quota": "周期订阅",
        "fallback_chain": ["gpt-6.1-terra", "gpt-6.2-sol", "gemini-4-hydrogen-medium", "claude-sonnet-5-5-medium"],
        "desc": "前端视觉理解与 UI 截图审查",
    },
    "9D": {
        "code": "9D",
        "pool": "9",
        "pool_name": "🥇 Codex 周期订阅池 (Tier 1)",
        "tier": "codex_subscription",
        "runner": "codex",
        "name": "Codex GPT-6 Luna (轻量)",
        "slug": "gpt-6-luna",
        "quota": "周期订阅",
        "fallback_chain": ["gpt-6-luna", "gemini-3.8-flash-medium", "gemini-4-hydrogen-low"],
        "desc": "轻量高速批量任务",
    },
    # Tier 2: 客户端内置三大独立池
    "1A": {
        "code": "1A",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (Neon池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 3.8 Flash (Neon池)",
        "slug": "gemini-3.8-flash-medium",
        "quota": "Neon 5h池",
        "fallback_chain": ["gemini-3.8-flash-medium", "gemini-4-hydrogen-low", "claude-sonnet-5-5-low"],
        "desc": "极速复核与轻量挑刺",
    },
    "1B": {
        "code": "1B",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (Neon池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Hydrogen Low (Neon池)",
        "slug": "gemini-4-hydrogen-low",
        "quota": "Neon 5h池",
        "fallback_chain": ["gemini-4-hydrogen-low", "gemini-3.8-flash-medium", "claude-sonnet-5-5-low"],
        "desc": "Neon 池极速替补",
    },
    "1C": {
        "code": "1C",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (Claude池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Claude Sonnet 5.5 Low (Claude池)",
        "slug": "claude-sonnet-5-5-low",
        "quota": "Claude 5h池",
        "fallback_chain": ["claude-sonnet-5-5-low", "gemini-3.8-flash-medium", "gemini-4-hydrogen-low"],
        "desc": "Claude 池跨池轻量接力",
    },
    "2A": {
        "code": "2A",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (Claude池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Claude Sonnet 5.5 (Claude池)",
        "slug": "claude-sonnet-5-5-medium",
        "quota": "Claude 5h池",
        "fallback_chain": ["claude-sonnet-5-5-medium", "claude-sonnet-5-5-high", "gemini-4-hydrogen-medium", "gemini-4-argon-medium"],
        "desc": "内置编码首选（跨 Neon ➔ Argon 周池）",
    },
    "2B": {
        "code": "2B",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (Neon池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Hydrogen (Neon池)",
        "slug": "gemini-4-hydrogen-medium",
        "quota": "Neon 5h池",
        "fallback_chain": ["gemini-4-hydrogen-medium", "gemini-4-hydrogen-high", "claude-sonnet-5-5-medium", "gemini-4-argon-medium"],
        "desc": "Neon 池敏捷编码主力",
    },
    "3A": {
        "code": "3A",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (Argon周池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Argon (Argon周池)",
        "slug": "gemini-4-argon-medium",
        "quota": "Argon 周池",
        "fallback_chain": ["gemini-4-argon-medium", "gemini-4-argon-high", "claude-opus-5-5-medium", "gemini-pro-orchestrator-neon"],
        "desc": "超长上下文宏观架构主力",
    },
    "3B": {
        "code": "3B",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (Claude池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Claude Opus 5.5 (Claude池)",
        "slug": "claude-opus-5-5-medium",
        "quota": "Claude 5h池",
        "fallback_chain": ["claude-opus-5-5-medium", "claude-opus-5-5-high", "gemini-4-neon-high", "gemini-4-argon-medium"],
        "desc": "顶层架构与严苛规范审阅",
    },
    "3C": {
        "code": "3C",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (Neon池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Orchestrator (Neon池)",
        "slug": "gemini-pro-orchestrator-neon",
        "quota": "Neon 5h池",
        "fallback_chain": ["gemini-pro-orchestrator-neon", "gemini-4-argon-medium", "claude-opus-5-5-medium"],
        "desc": "Neon 池双阶段统筹",
    },
    "4A": {
        "code": "4A",
        "pool": "4",
        "pool_name": "🔍 深度挑刺推理池 (Neon池)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Neon High (Neon池)",
        "slug": "gemini-4-neon-high",
        "quota": "Neon 5h池",
        "fallback_chain": ["gemini-4-neon-high", "gemini-4-neon-xhigh", "claude-opus-5-5-high", "gemini-4-argon-high"],
        "desc": "红方逻辑挑刺与死锁排错首选",
    },
    # Tier 3: DeepSeek 按量付费咨询席（永不自动调用）
    "8A": {
        "code": "8A",
        "pool": "8",
        "pool_name": "💰 DeepSeek 按量咨询席 (Tier 3)",
        "tier": "payg_ask_first",
        "runner": "dsh",
        "name": "DeepSeek-R1 / Reasoner",
        "slug": "deepseek-reasoner",
        "quota": "按量付费API",
        "fallback_chain": ["deepseek-reasoner", "deepseek-chat"],
        "desc": "按量付费红方外援（需先向用户确认）",
    },
    "8B": {
        "code": "8B",
        "pool": "8",
        "pool_name": "💰 DeepSeek 按量咨询席 (Tier 3)",
        "tier": "payg_ask_first",
        "runner": "dsh",
        "name": "DeepSeek-V3 / Chat",
        "slug": "deepseek-chat",
        "quota": "按量付费API",
        "fallback_chain": ["deepseek-chat"],
        "desc": "按量付费通用审查外援（需先向用户确认）",
    },
}

ROSTERS: dict[str, dict[str, Any]] = {
    "1": {
        "name": "双周期异构王牌 (Codex GPT-6.2 Sol [9B] ⚔ Gemini 4 Neon High [4A])",
        "tier": "codex_plus_native",
        "author_code": "9B",
        "critic_code": "4A",
    },
    "2": {
        "name": "客户端纯内置异构 (Claude Sonnet 5.5 [2A] ⚔ Gemini 4 Neon High [4A])",
        "tier": "native_free",
        "author_code": "2A",
        "critic_code": "4A",
    },
    "3": {
        "name": "顶级架构统筹对攻 (Codex GPT-6.2 Astra [9A] ⚔ Claude Opus 5.5 [3B] / Neon [4A])",
        "tier": "codex_plus_native",
        "author_code": "9A",
        "critic_code": "3B",
    },
    "8": {
        "name": "DeepSeek 按量外援对攻 (Codex/内置 [9B/2A] ⚔ 按量 DeepSeek-R1 [8A] · 需先确认)",
        "tier": "payg_ask_first",
        "author_code": "9B",
        "critic_code": "8A",
    },
}

POOL_DEFAULT_CODE = {
    "1": "1A",
    "2": "2A",
    "3": "3A",
    "4": "4A",
    "8": "8A",
    "9": "9B",
}


def get_config_path(workspace: str | None = None) -> Path:
    ws = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    swarm_dir = ws / ".swarm"
    swarm_dir.mkdir(parents=True, exist_ok=True)
    return swarm_dir / "critic_config.json"


def build_config_from_codes(lineup_id: str, author_code: str, critic_code: str, paused: bool = False) -> dict[str, Any]:
    a = UNIFIED_MODELS.get(author_code, UNIFIED_MODELS["9B"])
    c = UNIFIED_MODELS.get(critic_code, UNIFIED_MODELS["4A"])
    payg_used = (a["tier"] == "payg_ask_first" or c["tier"] == "payg_ask_first")
    if a["tier"] == "native_free" and c["tier"] == "native_free":
        mode = "native_first"
    elif payg_used:
        mode = "payg_ask_first"
    else:
        mode = "codex_plus_native"
    return {
        "schema_version": "2.1",
        "mode": mode,
        "active_lineup": lineup_id,
        "author_code": a["code"],
        "author_runner": a["runner"],
        "author_agent_name": a["pool_name"],
        "author_model_name": a["name"],
        "author_model_slug": a["slug"],
        "author_fallback_chain": a["fallback_chain"],
        "active_code": c["code"],
        "active_runner": c["runner"],
        "active_agent_name": c["pool_name"],
        "active_model_name": c["name"],
        "active_model_slug": c["slug"],
        "critic_fallback_chain": c["fallback_chain"],
        "payg_ask_first": payg_used,
        "external_paid_locked": (not payg_used),
        "paused": paused,
    }


def load_config(workspace: str | None = None) -> dict[str, Any]:
    cfg_file = get_config_path(workspace)
    if cfg_file.is_file():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            if data.get("schema_version") == "2.1":
                return data
        except Exception:
            pass
    default_cfg = build_config_from_codes("1", "9B", "4A", paused=False)
    save_config(default_cfg, workspace)
    return default_cfg


def save_config(cfg: dict[str, Any], workspace: str | None = None) -> None:
    cfg_file = get_config_path(workspace)
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def render_lineup_box(cfg: dict[str, Any]) -> str:
    cur_l = cfg.get("active_lineup", "1")
    a_desc = f"[{cfg.get('author_code', '9B')}] {cfg.get('author_model_name')}"
    c_desc = f"[{cfg.get('active_code', '4A')}] {cfg.get('active_model_name')}"
    return f"""┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E06 · 红蓝对抗闭环 v1.2.0 · 阶段 1/4: 对攻阵容速选]    │
│    [▶ 1.选对攻阵容] ➔ [2.定制/确认任务] ➔ [3.多轮红蓝死磕] ➔ [4.两相提交]  │
├────────────────────────────────────────────────────────────────────────────┤
│ 💡 当前锁定阵容: [{cur_l}] {a_desc} ⚔ {c_desc}
│    • 【三级阶梯 · 周期免费异构对攻席（自动跨池接力，0 按量扣费）】:        │
│      👉★[1] 双周期异构王牌   : [9B] Codex GPT-6.2 Sol ⚔ [4A] Gemini 4 Neon High │
│             (Codex Free/耗尽 : 蓝方自动退回 [2A] Sonnet 5.5 / [2B] Hydrogen)    │
│         [2] 客户端纯内置异构 : [2A] Claude Sonnet 5.5 ⚔ [4A] Gemini 4 Neon High │
│         [3] 顶级架构统筹对攻 : [9A] Codex GPT-6.2 Astra ⚔ [3B] Opus / [4A] Neon │
│    • 【按量付费咨询席（🔒永不自动调！仅前两级异常且询问确认后才启用）】:   │
│         [8] 按量外援对攻     : [9B/2A] 蓝方施工       ⚔ [8A] DeepSeek-R1 按量   │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 全局 .前缀零撞车快捷口令（释放裸字母 A/B/C/D 给选择题）:                │
│    • [1] / [2] / [3]  : 一键锁定周期/内置免费对攻阵容 [1]/[2]/[3]          │
│    • [8]              : 需用户确认的按量外援 (非工作日09-12/14-18及周末均半价) │
│    • [.?] / [面板]    : 呼出当前焦点对攻看板（唯一焦点锁，不与 E07 抢答）  │
│    • [.s] / [状态]    : 查看后台运行进度 + 刷新/查看内置模型剩余额度       │
└────────────────────────────────────────────────────────────────────────────┘"""


def resolve_code(raw: str, default_code: str = "4A") -> str:
    val = raw.strip().upper()
    if val in POOL_DEFAULT_CODE:
        return POOL_DEFAULT_CODE[val]
    if val in UNIFIED_MODELS:
        return val
    return default_code


def main() -> None:
    parser = argparse.ArgumentParser(description="E06 双脑红蓝对抗阵容与审查官管理器 v1.2.0")
    parser.add_argument("--workspace", default=os.getcwd(), help="工作区路径")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("table", help="打印当前对攻阵容与审查官 HUD 看板")
    sub.add_parser("probe", help="输出全局统一模型矩阵 JSON")
    sub.add_parser("pause", help="暂停对抗循环")
    sub.add_parser("resume", help="恢复对抗循环")

    lineup_cmd = sub.add_parser("lineup", help="查看或配置对攻阵容 (1/2/3 周期或内置免费, 8 询问确认按量, 或自定义 蓝方代号 红方代号)")
    lineup_cmd.add_argument("args", nargs="*", help="阵容号 (1/2/3/8) 或 蓝方代号 红方代号 (如 9B 4A)")

    switch_cmd = sub.add_parser("switch", help="热切红方审查官模型代号 (1A~4A, 9A~9D, 8A/8B)")
    switch_cmd.add_argument("code", help="模型代号，如 4A, 3B, 9A, 8A")

    args = parser.parse_args()
    cfg = load_config(args.workspace)

    if args.command == "table":
        print(render_lineup_box(cfg))
        sys.exit(0)

    if args.command == "probe":
        fast_cache = {}
        if FAST_CACHE_FILE.exists():
            try:
                fast_cache = json.loads(FAST_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        print(json.dumps({
            "schema_version": "2.1",
            "unified_models": UNIFIED_MODELS,
            "rosters": ROSTERS,
            "codex_fast_cache": fast_cache,
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.command == "pause":
        cfg["paused"] = True
        save_config(cfg, args.workspace)
        print(json.dumps({"status": "PAUSED", "message": "对抗审查已暂停"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.command == "resume":
        cfg["paused"] = False
        save_config(cfg, args.workspace)
        print(json.dumps({"status": "RESUMED", "active_code": cfg.get("active_code")}, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.command == "lineup":
        l_args = getattr(args, "args", [])
        if not l_args:
            print(render_lineup_box(cfg))
            sys.exit(0)

        if len(l_args) == 1 and l_args[0].strip() in ROSTERS:
            lid = l_args[0].strip()
            r = ROSTERS[lid]
            new_cfg = build_config_from_codes(lid, r["author_code"], r["critic_code"], paused=False)
            save_config(new_cfg, args.workspace)
            print(json.dumps({
                "status": "LAUNCH_READY",
                "lineup": lid,
                "name": r["name"],
                "tier": r["tier"],
                "author": f"[{new_cfg['author_code']}] {new_cfg['author_model_name']} ({new_cfg['author_model_slug']})",
                "critic": f"[{new_cfg['active_code']}] {new_cfg['active_model_name']} ({new_cfg['active_model_slug']})",
                "author_fallback_chain": new_cfg["author_fallback_chain"],
                "critic_fallback_chain": new_cfg["critic_fallback_chain"],
                "payg_ask_first": new_cfg["payg_ask_first"],
            }, ensure_ascii=False, indent=2))
            sys.exit(0)

        if len(l_args) >= 2:
            a_code = resolve_code(l_args[0], "9B")
            c_code = resolve_code(l_args[1], "4A")
            new_cfg = build_config_from_codes("custom", a_code, c_code, paused=False)
            save_config(new_cfg, args.workspace)
            print(json.dumps({
                "status": "LAUNCH_READY",
                "lineup": "custom",
                "author": f"[{new_cfg['author_code']}] {new_cfg['author_model_name']} ({new_cfg['author_model_slug']})",
                "critic": f"[{new_cfg['active_code']}] {new_cfg['active_model_name']} ({new_cfg['active_model_slug']})",
                "author_fallback_chain": new_cfg["author_fallback_chain"],
                "critic_fallback_chain": new_cfg["critic_fallback_chain"],
                "payg_ask_first": new_cfg["payg_ask_first"],
            }, ensure_ascii=False, indent=2))
            sys.exit(0)

        sys.stderr.write("[ERROR] 可选阵容编号: 1, 2, 3 (周期/内置免费) 或 8 (按量询问外援)，或传入两个代号如: lineup 9B 4A\n")
        sys.exit(1)

    if args.command == "switch":
        c_code = resolve_code(args.code, "4A")
        a_code = cfg.get("author_code", "9B")
        lid = cfg.get("active_lineup", "1")
        new_cfg = build_config_from_codes(lid, a_code, c_code, paused=False)
        save_config(new_cfg, args.workspace)
        print(json.dumps({
            "status": "SWITCHED",
            "active_code": new_cfg["active_code"],
            "active_runner": new_cfg["active_runner"],
            "active_model_name": new_cfg["active_model_name"],
            "active_model_slug": new_cfg["active_model_slug"],
            "critic_fallback_chain": new_cfg["critic_fallback_chain"],
            "payg_ask_first": new_cfg["payg_ask_first"],
        }, ensure_ascii=False, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
