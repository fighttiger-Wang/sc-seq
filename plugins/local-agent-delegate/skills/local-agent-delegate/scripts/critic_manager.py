#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Critic & Lineup Manager for E06 Adversarial Swarm v1.0.0.
特性：
1. 与 E07 100% 共用全局统一模型代号矩阵（1A~4A 为内置免费模型池，8A/8B 为 DeepSeek 付费外援，9A/9B 为 Codex 付费外援）
2. 默认 1 号王牌对攻阵容为客户端内置 0 额外付费异构组合：[2A] Claude Sonnet 5.5 ⚔ [4A] Gemini 4 Neon High
3. 读取 <2KB 的 models_fast_cache.json，秒级弹出阵容与审查官 HUD 看板
4. 支持同工种内置模型额度耗尽自动降级接力链（Quota Fallback Chain）
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
    "1A": {
        "code": "1A",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 3.8 Flash (High/Medium)",
        "slug": "gemini-3.8-flash-high",
        "quota": "94%",
        "fallback_chain": ["gemini-3.8-flash-high", "gemini-4-hydrogen-low", "gpt-oss-120b-medium"],
        "desc": "极速挑刺与轻量复核",
    },
    "1B": {
        "code": "1B",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Hydrogen (Low)",
        "slug": "gemini-4-hydrogen-low",
        "quota": "94%",
        "fallback_chain": ["gemini-4-hydrogen-low", "gemini-3.8-flash-medium", "gpt-oss-120b-medium"],
        "desc": "极速第一替补",
    },
    "1C": {
        "code": "1C",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "GPT-OSS 120B (Medium)",
        "slug": "gpt-oss-120b-medium",
        "quota": "34%",
        "fallback_chain": ["gpt-oss-120b-medium", "gemini-3.8-flash-medium"],
        "desc": "开源异构保底",
    },
    "2A": {
        "code": "2A",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Claude Sonnet 5.5 (High)",
        "slug": "claude-sonnet-5-5-high",
        "quota": "34%",
        "fallback_chain": [
            "claude-sonnet-5-5-high",
            "claude-sonnet-5-5-medium",
            "gemini-4-hydrogen-high",
            "gemini-4-argon-medium",
            "gpt-oss-120b-medium",
        ],
        "desc": "蓝方编码首选主力",
    },
    "2B": {
        "code": "2B",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Hydrogen (High/Medium)",
        "slug": "gemini-4-hydrogen-high",
        "quota": "94%",
        "fallback_chain": ["gemini-4-hydrogen-high", "gemini-4-hydrogen-medium", "gemini-4-argon-medium"],
        "desc": "蓝方全栈敏捷编码主力",
    },
    "3A": {
        "code": "3A",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Argon (High/Medium)",
        "slug": "gemini-4-argon-high",
        "quota": "66% (周池)",
        "fallback_chain": ["gemini-4-argon-high", "gemini-4-argon-medium", "claude-opus-5-5-high"],
        "desc": "超长上下文宏观架构主力",
    },
    "3B": {
        "code": "3B",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Claude Opus 5.5 (High)",
        "slug": "claude-opus-5-5-high",
        "quota": "34%",
        "fallback_chain": ["claude-opus-5-5-high", "claude-opus-5-5-medium", "gemini-4-argon-high"],
        "desc": "顶层架构与严苛规范审阅",
    },
    "4A": {
        "code": "4A",
        "pool": "4",
        "pool_name": "🔍 深度挑刺推理池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Neon (High/XHigh)",
        "slug": "gemini-4-neon-high",
        "quota": "94%",
        "fallback_chain": ["gemini-4-neon-high", "gemini-4-neon-xhigh", "claude-opus-5-5-high", "gemini-4-argon-high"],
        "desc": "红方逻辑挑刺与死锁排错首选",
    },
    "8A": {
        "code": "8A",
        "pool": "8",
        "pool_name": "💰 付费外援 · DeepSeek (非默认)",
        "tier": "paid_external",
        "runner": "dsh",
        "name": "DeepSeek-R1 / Reasoner",
        "slug": "deepseek-reasoner",
        "quota": "按量付费API",
        "fallback_chain": ["deepseek-reasoner", "deepseek-chat"],
        "desc": "外部付费深度推理红方外援",
    },
    "8B": {
        "code": "8B",
        "pool": "8",
        "pool_name": "💰 付费外援 · DeepSeek (非默认)",
        "tier": "paid_external",
        "runner": "dsh",
        "name": "DeepSeek-V3 / Chat",
        "slug": "deepseek-chat",
        "quota": "按量付费API",
        "fallback_chain": ["deepseek-chat"],
        "desc": "外部付费通用审查外援",
    },
    "9A": {
        "code": "9A",
        "pool": "9",
        "pool_name": "💰 付费外援 · OpenAI Codex (非默认)",
        "tier": "paid_external",
        "runner": "codex",
        "name": "Codex 6.2 Sol (旗舰)",
        "slug": "gpt-6.2-sol",
        "quota": "外部订阅/API",
        "fallback_chain": ["gpt-6.2-sol", "gpt-6.1-sol"],
        "desc": "外部付费旗舰编码蓝方外援",
    },
    "9B": {
        "code": "9B",
        "pool": "9",
        "pool_name": "💰 付费外援 · OpenAI Codex (非默认)",
        "tier": "paid_external",
        "runner": "codex",
        "name": "Codex 6.1 Sol (稳健)",
        "slug": "gpt-6.1-sol",
        "quota": "外部订阅/API",
        "fallback_chain": ["gpt-6.1-sol"],
        "desc": "外部付费稳健编码蓝方外援",
    },
}

ROSTERS: dict[str, dict[str, Any]] = {
    "1": {
        "name": "默认内置王牌异构对攻 (Claude Sonnet 5.5 [2A] ⚔ Gemini 4 Neon High [4A])",
        "tier": "native_free",
        "author_code": "2A",
        "critic_code": "4A",
    },
    "2": {
        "name": "内置架构统筹对攻 (Gemini 4 Argon [3A] ⚔ Claude Opus 5.5 [3B])",
        "tier": "native_free",
        "author_code": "3A",
        "critic_code": "3B",
    },
    "3": {
        "name": "内置极速敏捷对攻 (Gemini 4 Hydrogen [2B] ⚔ Gemini 3.8 Flash High [1A])",
        "tier": "native_free",
        "author_code": "2B",
        "critic_code": "1A",
    },
    "8": {
        "name": "半托管外援对攻 (内置 Claude Sonnet 5.5 [2A] ⚔ 付费外援 DeepSeek [8A])",
        "tier": "semi_paid_external",
        "author_code": "2A",
        "critic_code": "8A",
    },
    "9": {
        "name": "经典全外援付费对攻 (付费 Codex 6.2 Sol [9A] ⚔ 付费 DeepSeek [8A])",
        "tier": "full_paid_external",
        "author_code": "9A",
        "critic_code": "8A",
    },
}

POOL_DEFAULT_CODE = {
    "1": "1A",
    "2": "2A",
    "3": "3A",
    "4": "4A",
    "8": "8A",
    "9": "9A",
}


def get_config_path(workspace: str | None = None) -> Path:
    ws = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    swarm_dir = ws / ".swarm"
    swarm_dir.mkdir(parents=True, exist_ok=True)
    return swarm_dir / "critic_config.json"


def build_config_from_codes(lineup_id: str, author_code: str, critic_code: str, paused: bool = False) -> dict[str, Any]:
    a = UNIFIED_MODELS.get(author_code, UNIFIED_MODELS["2A"])
    c = UNIFIED_MODELS.get(critic_code, UNIFIED_MODELS["4A"])
    return {
        "schema_version": "2.0",
        "mode": "native_first" if (a["tier"] == "native_free" and c["tier"] == "native_free") else "paid_external_enabled",
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
        "external_paid_locked": (a["tier"] == "native_free" and c["tier"] == "native_free"),
        "paused": paused,
    }


def load_config(workspace: str | None = None) -> dict[str, Any]:
    cfg_file = get_config_path(workspace)
    if cfg_file.is_file():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            if data.get("schema_version") == "2.0":
                return data
        except Exception:
            pass
    default_cfg = build_config_from_codes("1", "2A", "4A", paused=False)
    save_config(default_cfg, workspace)
    return default_cfg


def save_config(cfg: dict[str, Any], workspace: str | None = None) -> None:
    cfg_file = get_config_path(workspace)
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def render_lineup_box(cfg: dict[str, Any]) -> str:
    cur_l = cfg.get("active_lineup", "1")
    a_desc = f"[{cfg.get('author_code', '2A')}] {cfg.get('author_model_name')}"
    c_desc = f"[{cfg.get('active_code', '4A')}] {cfg.get('active_model_name')}"
    return f"""┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E06 · 红蓝对抗闭环 v1.1.0 · 阶段 1/4: 对攻阵容速选]    │
│    [▶ 1.选对攻阵容] ➔ [2.定制/确认任务] ➔ [3.多轮红蓝死磕] ➔ [4.两相提交]  │
├────────────────────────────────────────────────────────────────────────────┤
│ 💡 当前锁定阵容: [{cur_l}] {a_desc} ⚔ {c_desc}
│    • 【客户端内置 0 额外付费异构对攻席（支持额度耗尽自动顺延接力）】:      │
│      👉★[1] 默认内置王牌异构对攻 : [2A] Claude Sonnet 5.5 ⚔ [4A] Gemini 4 Neon High │
│             (额度耗尽自动接力链  : [2B] Gemini 4 Hydrogen ⚔ [3B] Opus 5.5 / [3A] Argon)│
│         [2] 内置架构统筹对攻     : [3A] Gemini 4 Argon    ⚔ [3B] Claude Opus 5.5    │
│         [3] 内置极速敏捷对攻     : [2B] Gemini 4 Hydrogen ⚔ [1A] Gemini 3.8 Flash   │
│    • 【外部付费外援对攻席（🔒非默认！需消耗外部 API，仅手动选 8 或 9 启用）】│
│         [8] 半托管外援对攻       : [2A] 内置 Sonnet 5.5   ⚔ [8A] 付费 DeepSeek-R1   │
│         [9] 经典全外援付费对攻   : [9A] 付费 Codex 6.2    ⚔ [8A] 付费 DeepSeek-R1   │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 全局 .前缀零撞车快捷口令（释放裸字母 A/B/C/D 给选择题）:                │
│    • [1] / [2] / [3]  : 一键锁定内置 0 额外付费对攻阵容 [1]/[2]/[3]        │
│    • [8] / [9]        : 显式解锁半托管外援 [8] 或全外援付费对攻 [9]        │
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
    parser = argparse.ArgumentParser(description="E06 双脑红蓝对抗阵容与审查官管理器 v1.0.0")
    parser.add_argument("--workspace", default=os.getcwd(), help="工作区路径")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("table", help="打印当前对攻阵容与审查官 HUD 看板")
    sub.add_parser("probe", help="输出全局统一模型矩阵 JSON")
    sub.add_parser("pause", help="暂停对抗循环")
    sub.add_parser("resume", help="恢复对抗循环")

    lineup_cmd = sub.add_parser("lineup", help="查看或配置对攻阵容 (1/2/3 内置免费, 8/9 付费外援, 或自定义 蓝方代号 红方代号)")
    lineup_cmd.add_argument("args", nargs="*", help="阵容号 (1/2/3/8/9) 或 蓝方代号 红方代号 (如 2A 4A)")

    switch_cmd = sub.add_parser("switch", help="热切红方审查官模型代号 (1A~4A, 8A/8B, 9A/9B)")
    switch_cmd.add_argument("code", help="模型代号，如 4A, 3B, 8A")

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
            "schema_version": "2.0",
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
                "paid_external_used": r["tier"] != "native_free",
            }, ensure_ascii=False, indent=2))
            sys.exit(0)

        if len(l_args) >= 2:
            a_code = resolve_code(l_args[0], "2A")
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
                "paid_external_used": not new_cfg["external_paid_locked"],
            }, ensure_ascii=False, indent=2))
            sys.exit(0)

        sys.stderr.write("[ERROR] 可选阵容编号: 1, 2, 3 (内置免费) 或 8, 9 (付费外援)，或传入两个代号如: lineup 2A 4A\n")
        sys.exit(1)

    if args.command == "switch":
        c_code = resolve_code(args.code, "4A")
        a_code = cfg.get("author_code", "2A")
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
        }, ensure_ascii=False, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
