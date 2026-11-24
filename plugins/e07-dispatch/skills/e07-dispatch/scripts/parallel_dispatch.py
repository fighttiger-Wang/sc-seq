#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E07 · 三级阶梯智能派发与跨池额度接力中心 v1.2.0
核心特性：
1. 三级阶梯架构：
   - Tier 1 (Codex 周期订阅优先池 9A~9D)：独立重型后台任务优先吃满；自动同步 models_cache.json 感知 Free/受限状态并支持冷却熔断
   - Tier 2 (客户端内置两大共享池 1A~4A)：Gemini / Claude+GPT-OSS，同池共耗尽，跨池自动接力
   - Tier 3 (DeepSeek 按量付费咨询席 8A/8B)：永不自动调用，仅前两级不可用或降智时先询问并提示半价空闲时段（除工作日 09:00-12:00/14:00-18:00 外及周末/法定节假日全天半价）
2. 动态扫描 LOCALAPPDATA\\OpenAI\\Codex\\bin\\*\\codex.exe 最新版，防止客户端升级换目录断联
3. 零外部套娃：内置模型直接秒回 subagent / swarm 调度指令 JSON（耗时 < 0.05s）
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import model_radar

CURRENT_DIR = Path(__file__).resolve().parent
ENV_CONFIG_FILE = CURRENT_DIR / "local_env.json"
MODELS_CACHE_FILE = CURRENT_DIR / "models_cache.json"
FAST_CACHE_FILE = CURRENT_DIR / "models_fast_cache.json"
LOCAL_DELEGATE = CURRENT_DIR / "delegate.py"

BJ_TZ = timezone(timedelta(hours=8))

# 客户端内置三大真实独立配额桶（同桶共享额度，不得在同桶内互为保底）
QUOTA_BUCKETS: dict[str, set[str]] = {
    "gemini_shared": {
        "gemini_shared", "neon", "neon_5h", "argon", "argon_weekly",
        "gemini-4-carbon-*", "gemini-4-neon-*", "gemini-4-hydrogen-*",
        "gemini-4-argon-*", "gemini-3.8-flash-*",
        "gemini-pro-orchestrator", "gemini-pro-orchestrator-argon", "gemini-pro-orchestrator-neon",
    },
    "claude_shared": {"claude_shared", "claude", "claude_5h", "claude-opus-*", "claude-sonnet-*", "gpt-oss-120b*"},
}


def quota_bucket(slug: str) -> str | None:
    return next((bucket for bucket, patterns in QUOTA_BUCKETS.items()
                 if any(fnmatchcase(slug, pattern) for pattern in patterns)), None)


def model_exhausted(slug: str, exhausted: set[str]) -> bool:
    return slug in exhausted or quota_bucket(slug) in exhausted

# 全局统一模型矩阵（E06 与 E07 100% 共用同一套代号）
NATIVE_MODELS: dict[str, dict[str, Any]] = {
    # Tier 2: 客户端内置两大共享池（跨池接力）
    "1A": {
        "code": "1A",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "gemini_shared",
        "runner": "native",
        "name": "Gemini 3.8 Flash (Gemini 共享池)",
        "slug": "gemini-3.8-flash-medium",
        "subagent_model": "flash",
        "quota_default": "Gemini 共享池",
        "fallback_chain": [
            "gemini-3.8-flash-medium",
            "gemini-3.8-flash-low",
            "gemini-4-hydrogen-low",
            "claude-sonnet-5-5-low",
            "gemini-4-argon-low",
        ],
        "desc": "毫秒级响应 · 快速查文件/日志过滤/单文件小修",
    },
    "1B": {
        "code": "1B",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "gemini_shared",
        "runner": "native",
        "name": "Gemini 4 Hydrogen Low (Gemini 共享池)",
        "slug": "gemini-4-hydrogen-low",
        "subagent_model": "flash",
        "quota_default": "Gemini 共享池",
        "fallback_chain": [
            "gemini-4-hydrogen-low",
            "gemini-3.8-flash-medium",
            "claude-sonnet-5-5-low",
            "gemini-4-argon-low",
        ],
        "desc": "Gemini 共享池极速替补 · 轻量高并发跑腿",
    },
    "1C": {
        "code": "1C",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "claude_shared",
        "runner": "native",
        "name": "Claude Sonnet 5.5 Low (Claude池)",
        "slug": "claude-sonnet-5-5-low",
        "subagent_model": "flash",
        "quota_default": "Claude 5h池",
        "fallback_chain": [
            "claude-sonnet-5-5-low",
            "gemini-3.8-flash-medium",
            "gemini-4-hydrogen-low",
            "gemini-4-argon-low",
        ],
        "desc": "Claude 池跨池轻量接力",
    },
    "2A": {
        "code": "2A",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "claude_shared",
        "runner": "native",
        "name": "Claude Sonnet 5.5 (Claude池)",
        "slug": "claude-sonnet-5-5-medium",
        "subagent_model": "pro",
        "quota_default": "Claude 5h池",
        "fallback_chain": [
            "claude-sonnet-5-5-medium",
            "claude-sonnet-5-5-high",
            "gemini-4-hydrogen-medium",
            "gemini-4-argon-medium",
        ],
        "desc": "内置编码首选（默认 medium 省配额）➔ 跨 Gemini 共享池",
    },
    "2B": {
        "code": "2B",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "gemini_shared",
        "runner": "native",
        "name": "Gemini 4 Hydrogen (Gemini 共享池)",
        "slug": "gemini-4-hydrogen-medium",
        "subagent_model": "pro",
        "quota_default": "Gemini 共享池",
        "fallback_chain": [
            "gemini-4-hydrogen-medium",
            "gemini-4-hydrogen-high",
            "claude-sonnet-5-5-medium",
            "gemini-4-argon-medium",
        ],
        "desc": "Gemini 共享池敏捷全栈编码主力 ➔ 跨 Claude 共享池",
    },
    "3A": {
        "code": "3A",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "gemini_shared",
        "runner": "native",
        "name": "Gemini 4 Argon (Gemini 共享池)",
        "slug": "gemini-4-argon-medium",
        "subagent_model": "pro",
        "quota_default": "Gemini 共享池",
        "fallback_chain": [
            "gemini-4-argon-medium",
            "gemini-4-argon-high",
            "claude-opus-5-5-medium",
            "gemini-pro-orchestrator-neon",
        ],
        "desc": "Gemini 共享池全局视野统筹 ➔ 跨 Claude 共享池",
    },
    "3B": {
        "code": "3B",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "claude_shared",
        "runner": "native",
        "name": "Claude Opus 5.5 (Claude池)",
        "slug": "claude-opus-5-5-medium",
        "subagent_model": "pro",
        "quota_default": "Claude 5h池",
        "fallback_chain": [
            "claude-opus-5-5-medium",
            "claude-opus-5-5-high",
            "gemini-4-argon-medium",
            "gemini-pro-orchestrator-neon",
        ],
        "desc": "Claude 池顶层设计与文档规范 ➔ 跨 Gemini 共享池",
    },
    "3C": {
        "code": "3C",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "gemini_shared",
        "runner": "native",
        "name": "Orchestrator (Gemini 共享池)",
        "slug": "gemini-pro-orchestrator-neon",
        "subagent_model": "pro",
        "quota_default": "Gemini 共享池",
        "fallback_chain": [
            "gemini-pro-orchestrator-neon",
            "gemini-4-argon-medium",
            "claude-opus-5-5-medium",
        ],
        "desc": "Gemini 共享池双阶段统筹（强模型规划 + 轻模型执行）",
    },
    "4A": {
        "code": "4A",
        "pool": "4",
        "pool_name": "🔍 深度挑刺推理池 (Tier 2 内置)",
        "tier": "native_free",
        "bucket": "gemini_shared",
        "runner": "native",
        "name": "Gemini 4 Neon High (Gemini 共享池)",
        "slug": "gemini-4-neon-high",
        "subagent_model": "pro",
        "quota_default": "Gemini 共享池",
        "fallback_chain": [
            "gemini-4-neon-high",
            "gemini-4-neon-xhigh",
            "claude-opus-5-5-high",
            "gemini-4-argon-high",
        ],
        "desc": "红方挑刺首选（Gemini 共享池）➔ 跨 Claude 共享池",
    },
}


def model_matrix() -> dict[str, dict[str, Any]]:
    policy = model_radar.load_policy()
    try:
        codex_models = model_radar.read_codex_models()
    except (OSError, ValueError, KeyError, TypeError):
        codex_models = {}
    matrix = dict(NATIVE_MODELS)
    for role in model_radar.resolve_codex_roles(policy, codex_models).values():
        code = role["code"]
        matrix[code] = {
            "code": code, "pool": "9", "pool_name": "Codex 周期订阅池",
            "tier": "codex_subscription", "runner": role["runner"],
            "name": role["display_name"], "slug": role["slug"],
            "native_fallback_code": role["fallback_native_code"], "quota_default": "周期订阅",
            "fallback_chain": role["fallback_chain"], "desc": role["desc"],
        }
    for code, model in policy["dsh_defaults"]["models"].items():
        role = policy["roles"][model["role"]]
        matrix[code] = {
            "code": code, "pool": "8", "pool_name": "DeepSeek 官方 API 按量咨询席",
            "tier": role["tier"], "runner": role["runner"], "provider": role["provider"],
            "name": model["display_name"], "slug": role["model_id"], "quota_default": "按量先问",
            "fallback_chain": [role["model_id"]], "desc": model["desc"],
        }
    return matrix


POOL_DEFAULTS = {
    "1": "1A",
    "2": "2A",
    "3": "3A",
    "4": "4A",
    "8": "8A",
    "9": "9B",
}

SLUG_TO_SUBAGENT_MODEL = {
    "gemini-3.8-flash-medium": "flash",
    "gemini-3.8-flash-low": "flash",
    "gemini-3.8-flash-high": "flash",
    "gemini-4-hydrogen-low": "flash",
    "gemini-4-hydrogen-medium": "pro",
    "gemini-4-hydrogen-high": "pro",
    "claude-sonnet-5-5-low": "flash",
    "claude-sonnet-5-5-medium": "pro",
    "claude-sonnet-5-5-high": "pro",
    "claude-opus-5-5-medium": "pro",
    "claude-opus-5-5-high": "pro",
    "gemini-4-argon-low": "flash",
    "gemini-4-argon-medium": "pro",
    "gemini-4-argon-high": "pro",
    "gemini-4-neon-medium": "pro",
    "gemini-4-neon-high": "pro",
    "gemini-4-neon-xhigh": "pro",
    "gemini-pro-orchestrator-neon": "pro",
    "gpt-oss-120b-medium": "inherit",
}


def expand_exhausted_buckets(raw_exhausted: set[str]) -> set[str]:
    """根据两大共享池扩展耗尽集合，确保同池不原地撞墙。"""
    expanded = {x.strip().lower() for x in raw_exhausted if x.strip()}
    expanded.update(bucket for slug in tuple(expanded) if (bucket := quota_bucket(slug)))
    return expanded


def is_deepseek_half_price_window(now: datetime | None = None) -> tuple[bool, str]:
    """判断当前是否处于 DeepSeek 空闲半价时段。
    规则：北京时间周一至周五（不含中国法定节假日）09:00-12:00、14:00-18:00 为高峰原价时段；
    其余时段及周末/中国法定节假日全天均为空闲半价时段。
    """
    bj_now = now.astimezone(BJ_TZ) if now else datetime.now(BJ_TZ)
    is_peak = bj_now.weekday() < 5 and ((9 <= bj_now.hour < 12) or (14 <= bj_now.hour < 18))
    return (not is_peak), bj_now.strftime("%H:%M")


def load_env_config() -> dict[str, Any]:
    if ENV_CONFIG_FILE.exists():
        try:
            return json.loads(ENV_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "python_interpreter": sys.executable,
        "dsh_binary": r"E:\A001-软件安装\deepseek\resources\runtime\cli\bin\dsh.cmd",
        "codex_binary": "auto",
        "default_choice": "9B",
        "default_runner": "codex_then_native",
        "paid_external_default": False,
        "tasks_dir": str(Path.home() / ".gemini" / "antigravity" / "scratch" / "e07_tasks"),
    }


def get_tasks_dir() -> Path:
    cfg = load_env_config()
    td = model_radar.tasks_dir()
    if not os.environ.get("E07_TASKS_DIR") and cfg.get("tasks_dir"):
        td = Path(cfg["tasks_dir"])
    td.mkdir(parents=True, exist_ok=True)
    return td


def get_cooldown_file() -> Path:
    return get_tasks_dir() / "codex_cooldown.json"


def get_codex_cooldown() -> dict[str, Any]:
    cf = get_cooldown_file()
    if not cf.is_file():
        return {"active": False}
    try:
        data = json.loads(cf.read_text(encoding="utf-8"))
        until_ts = float(data.get("until_ts", 0))
        now_ts = time.time()
        if until_ts > now_ts:
            rem_min = max(1, int((until_ts - now_ts + 59) // 60))
            return {
                "active": True,
                "until": data.get("until_iso", ""),
                "remaining_minutes": rem_min,
                "reason": data.get("reason", "codex quota/free cooldown"),
            }
    except Exception:
        pass
    return {"active": False}


def set_codex_cooldown(minutes: int, reason: str) -> dict[str, Any]:
    until_ts = time.time() + max(1, minutes) * 60
    until_iso = datetime.fromtimestamp(until_ts, tz=BJ_TZ).isoformat()
    payload = {
        "until_ts": until_ts,
        "until_iso": until_iso,
        "minutes": minutes,
        "reason": reason,
        "updated_at": datetime.now(BJ_TZ).isoformat(),
    }
    get_cooldown_file().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "COOLDOWN_SET", **payload}


def clear_codex_cooldown() -> dict[str, Any]:
    cf = get_cooldown_file()
    if cf.exists():
        cf.unlink()
    return {"status": "COOLDOWN_CLEARED"}


def discover_codex_binary() -> str | None:
    """动态定位最新的 codex.exe（防客户端升级换哈希目录断联）。"""
    env_bin = os.environ.get("OIL_DELEGATE_CODEX_BIN")
    if env_bin and Path(env_bin).is_file():
        return str(Path(env_bin).resolve())

    if os.name == "nt":
        local_app = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        bin_root = local_app / "OpenAI" / "Codex" / "bin"
        if bin_root.is_dir():
            candidates = sorted(
                bin_root.glob("*/codex.exe"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for cand in candidates:
                if cand.is_file():
                    return str(cand.resolve())

    which_bin = shutil.which("codex")
    if which_bin and Path(which_bin).is_file():
        return which_bin

    cfg_bin = load_env_config().get("codex_binary")
    if cfg_bin and cfg_bin != "auto" and Path(cfg_bin).is_file():
        return str(Path(cfg_bin).resolve())
    return None


def load_fast_codex_cache(force_refresh: bool = False) -> dict[str, Any]:
    """优先读取 <2KB 的 models_fast_cache.json；若 ~/.codex/models_cache.json 更新则自动刷新感知 Free 状态。"""
    src = Path.home() / ".codex" / "models_cache.json"
    src_newer = False
    if src.is_file():
        if not FAST_CACHE_FILE.is_file():
            src_newer = True
        else:
            try:
                src_newer = src.stat().st_mtime > FAST_CACHE_FILE.stat().st_mtime
            except OSError:
                src_newer = True

    if not force_refresh and not src_newer and FAST_CACHE_FILE.is_file():
        try:
            return json.loads(FAST_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    fast_models = []
    if src.is_file():
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            for m in data.get("models", []):
                slug = m.get("slug", "")
                if slug and not slug.endswith("-auto-review") and slug != "gpt-reserve":
                    fast_models.append({
                        "slug": slug,
                        "display_name": m.get("display_name", slug),
                        "description": (m.get("description") or "")[:60],
                    })
        except Exception:
            pass

    if not fast_models:
        alt = Path.home() / ".codex" / "models_fast_cache.json"
        if alt.is_file():
            try:
                return json.loads(alt.read_text(encoding="utf-8"))
            except Exception:
                pass

    payload = {
        "version": "1.1.0",
        "source": str(src),
        "updated_at": datetime.now(BJ_TZ).isoformat(),
        "valid_codex_slugs": [m["slug"] for m in fast_models],
        "codex_models": fast_models,
    }
    if not force_refresh:
        return payload
    try:
        FAST_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


def probe_local_models(force: bool = False, *, persist: bool = False) -> dict[str, Any]:
    fast_codex = load_fast_codex_cache(force_refresh=force)
    codex_bin = discover_codex_binary()
    cooldown = get_codex_cooldown()
    probe_result = {
        "schema_version": "1.2.0",
        "probed_at": datetime.now(BJ_TZ).isoformat(),
        "status": "READY",
        "policy": "tier1_codex_subscription_then_tier2_native_buckets_then_tier3_ask_deepseek",
        "codex_binary": codex_bin,
        "codex_cooldown": cooldown,
        "codex_valid_slugs": fast_codex.get("valid_codex_slugs", []),
        "quota_buckets": {k: sorted(v) for k, v in QUOTA_BUCKETS.items()},
        "matrix": model_matrix(),
    }
    if not persist:
        return probe_result
    try:
        saved = model_radar.read_json(MODELS_CACHE_FILE) if MODELS_CACHE_FILE.exists() else {}
        MODELS_CACHE_FILE.write_text(json.dumps({**saved, **probe_result}, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return probe_result


def resolve_choice(choice_code: str) -> dict[str, Any]:
    raw = (choice_code or "9B").strip().upper()
    if raw in POOL_DEFAULTS:
        raw = POOL_DEFAULTS[raw]
    matrix = model_matrix()
    if raw not in matrix:
        raw = "2B"
    return dict(matrix[raw])


def resolve_with_quota_fallback(item: dict[str, Any], exhausted_slugs: set[str]) -> dict[str, Any]:
    """当首选内置模型所在配额桶耗尽时，沿跨池 fallback_chain 自动顺延接力。"""
    primary_slug = item["slug"]
    chain = item.get("fallback_chain", [primary_slug])
    selected_slug = primary_slug
    fallback_triggered = False

    if model_exhausted(primary_slug.lower(), exhausted_slugs):
        fallback_triggered = True
        for candidate in chain:
            if not model_exhausted(candidate.lower(), exhausted_slugs):
                selected_slug = candidate
                break

    subagent_model = SLUG_TO_SUBAGENT_MODEL.get(selected_slug, item.get("subagent_model", "inherit"))
    return {
        "code": item["code"],
        "pool": item["pool"],
        "pool_name": item["pool_name"],
        "tier": item["tier"],
        "runner": item["runner"],
        "primary_model_slug": primary_slug,
        "selected_model_slug": selected_slug,
        "subagent_model": subagent_model,
        "fallback_triggered": fallback_triggered,
        "exhausted_models": sorted(exhausted_slugs),
        "fallback_chain": chain,
    }


def _build_native_payload(
    resolved: dict[str, Any],
    prompt: str,
    workspace: str,
    exhausted_set: set[str],
    *,
    status: str = "NATIVE_DISPATCH_READY",
    dispatch_mode: str = "native",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    half_price, bj_time = is_deepseek_half_price_window()
    all_exhausted = model_exhausted(resolved["selected_model_slug"].lower(), exhausted_set)
    payload: dict[str, Any] = {
        "status": status,
        "dispatch_mode": dispatch_mode,
        "paid_external_triggered": False,
        "choice_code": resolved["code"],
        "pool_name": resolved["pool_name"],
        "runner": "native",
        "primary_model": resolved["primary_model_slug"],
        "selected_model": resolved["selected_model_slug"],
        "subagent_model": resolved["subagent_model"],
        "fallback_triggered": resolved["fallback_triggered"],
        "fallback_chain": resolved["fallback_chain"],
        "all_native_exhausted": all_exhausted,
        "deepseek_consult_recommended": all_exhausted,
        "deepseek_half_price_window": half_price,
        "beijing_time": bj_time,
        "workspace": workspace,
        "invoke_subagent_args": {
            "TypeName": "self",
            "Role": f"E07 {resolved['code']} Worker",
            "Model": resolved["subagent_model"],
            "Prompt": prompt,
        },
        "swarm_add_args": {
            "action": "add",
            "name": f"worker-{resolved['code'].lower()}",
            "model": resolved["selected_model_slug"],
            "brief": prompt,
        },
    }
    if all_exhausted:
        payload["status"] = "NATIVE_QUOTA_EXHAUSTED"
        payload.pop("invoke_subagent_args")
        payload.pop("swarm_add_args")
    if extra:
        payload.update(extra)
    return payload


def _build_subprocess_env(cfg: dict[str, Any], codex_bin: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if codex_bin:
        env["OIL_DELEGATE_CODEX_BIN"] = codex_bin
    dsh_bin = cfg.get("dsh_binary")
    if dsh_bin and Path(dsh_bin).is_file():
        env["OIL_DELEGATE_DSH_BIN"] = dsh_bin
    return env


def dispatch_task(
    choice_code: str,
    prompt: str,
    workspace: str,
    role: str | None = None,
    exhausted_csv: str = "",
    dry_run: bool = False,
    refresh: bool = False,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    item = resolve_choice(choice_code)
    raw_exhausted = {s.strip() for s in exhausted_csv.split(",") if s.strip()}
    exhausted_set = expand_exhausted_buckets(raw_exhausted)
    cfg = load_env_config()
    half_price, bj_time = is_deepseek_half_price_window()
    half_price_note = (
        f"当前处于 DeepSeek 空闲半价时段（北京时间 {bj_time}；除工作日 09:00–12:00、14:00–18:00 外及周末/中国法定节假日全天均为半价）"
        if half_price
        else f"当前处于工作日高峰原价时段（北京时间 {bj_time}；周一至周五 09:00–12:00、14:00–18:00 为高峰，若当天为中国法定节假日则全天半价）"
    )

    # Tier 2: 客户端内置两大共享池
    if item["tier"] == "native_free":
        resolved = resolve_with_quota_fallback(item, exhausted_set)
        return _build_native_payload(resolved, prompt, workspace, exhausted_set)

    # Tier 1: OpenAI Codex 周期订阅优先池（带健康检查与 Free/冷却自动回退至 Tier 2）
    if item["tier"] == "codex_subscription":
        fallback_reason: str | None = None
        codex_bin = discover_codex_binary()
        cooldown = get_codex_cooldown()

        model_slug = next((slug for slug in item["fallback_chain"] if slug not in exhausted_set), None)
        if not item["slug"]:
            fallback_reason = "codex_role_unavailable_in_cache"
        elif "codex" in exhausted_set or not model_slug:
            fallback_reason = "codex_exhausted_or_free"
        elif cooldown.get("active"):
            fallback_reason = f"codex_cooldown ({cooldown.get('remaining_minutes')}m remaining: {cooldown.get('reason')})"
        elif not codex_bin:
            fallback_reason = "codex_binary_not_found"

        if fallback_reason:
            fb_code = item.get("native_fallback_code", "2A")
            fb_item = resolve_choice(fb_code)
            fb_resolved = resolve_with_quota_fallback(fb_item, exhausted_set)
            fb_resolved["fallback_triggered"] = True
            return _build_native_payload(
                fb_resolved,
                prompt,
                workspace,
                exhausted_set,
                status="NATIVE_FALLBACK_READY",
                dispatch_mode="native_fallback",
                extra={
                    "requested_choice": item["code"],
                    "requested_model": item["slug"],
                    "fallback_reason": fallback_reason,
                },
            )

        sub_env = _build_subprocess_env(cfg, codex_bin=codex_bin)
    else:
        # Tier 3: 按量付费 DeepSeek 咨询席（永不自动调用，必须询问用户）
        if not dry_run and not user_confirmed:
            return {
                "status": "ASK_USER_CONFIRMATION_REQUIRED",
                "dispatch_mode": "payg_ask_first",
                "ask_user_required": True,
                "paid_external_triggered": False,
                "choice_code": item["code"],
                "runner": item["runner"],
                "selected_model": item["slug"],
                "deepseek_half_price_window": half_price,
                "beijing_time": bj_time,
                "half_price_note": half_price_note,
                "message": "DeepSeek 为即时按量付费模型，请先向用户确认（附半价时段提示）并加 --user-confirmed 再启动。",
            }
        sub_env = _build_subprocess_env(cfg)
        model_slug = item["slug"]

    py_bin = cfg.get("python_interpreter")
    if not py_bin or not Path(py_bin).is_file():
        py_bin = sys.executable
    runner = item["runner"]
    cmd = [
        py_bin,
        str(LOCAL_DELEGATE),
        "run",
        "--runner",
        runner,
        "--workspace",
        workspace,
        "--prompt",
        prompt,
        "--model",
        model_slug,
    ]
    if runner == "dsh":
        cmd.extend(["--dsh-provider", item["provider"]])
    if role:
        cmd.extend(["--role", role])
    if refresh:
        cmd.append("--refresh")

    if dry_run:
        cmd.extend(["--dry-run", "--json"])
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=sub_env,
        )
        try:
            delegate_payload = json.loads(proc.stdout.strip())
        except Exception:
            delegate_payload = {
                "returncode": proc.returncode,
                "raw_stdout": proc.stdout.strip(),
                "raw_stderr": proc.stderr.strip(),
            }
        is_payg = item["tier"] == "payg_ask_first"
        return {
            "status": ("PAYG_EXTERNAL_DRY_RUN" if is_payg else "CODEX_SUBSCRIPTION_DRY_RUN")
            if proc.returncode == 0 else "DELEGATE_DRY_RUN_FAILED",
            "dispatch_mode": "payg_ask_first" if is_payg else "codex_subscription",
            "paid_external_triggered": False,
            "ask_user_required": (is_payg and not user_confirmed),
            "deepseek_half_price_window": half_price if is_payg else None,
            "beijing_time": bj_time,
            "half_price_note": half_price_note if is_payg else None,
            "choice_code": item["code"],
            "runner": runner,
            "selected_model": model_slug,
            "codex_binary": sub_env.get("OIL_DELEGATE_CODEX_BIN"),
            "delegate_dry_run": delegate_payload,
        }

    tasks_dir = get_tasks_dir()
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    meta_file = task_dir / "meta.json"
    log_file = task_dir / "output.log"

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with open(log_file, "w", encoding="utf-8") as out_fp:
        proc = subprocess.Popen(
            cmd,
            stdout=out_fp,
            stderr=subprocess.STDOUT,
            cwd=workspace,
            env=sub_env,
            creationflags=creationflags,
        )

    is_payg = item["tier"] == "payg_ask_first"
    meta = {
        "status": "PAYG_EXTERNAL_DISPATCHED" if is_payg else "CODEX_SUBSCRIPTION_DISPATCHED",
        "dispatch_mode": "payg_ask_first" if is_payg else "codex_subscription",
        "paid_external_triggered": is_payg,
        "task_id": task_id,
        "pid": proc.pid,
        "choice_code": item["code"],
        "runner": runner,
        "model": model_slug,
        "task_status": "RUNNING",
        "description": prompt[:100],
        "workspace": workspace,
        "log_path": str(log_file),
        "start_time": time.time(),
        "created_at": datetime.now(BJ_TZ).isoformat(),
    }
    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def check_pid_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            out = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /NH', shell=True).decode("gbk", errors="ignore")
            return str(pid) in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def list_active_tasks() -> list[dict[str, Any]]:
    tasks_dir = get_tasks_dir()
    results = []
    now = time.time()
    for task_folder in sorted(tasks_dir.glob("task_*"), reverse=True):
        meta_file = task_folder / "meta.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            pid = meta.get("pid")
            status = meta.get("task_status", meta.get("status", "UNKNOWN"))
            if pid and status == "RUNNING":
                if not check_pid_alive(pid):
                    status = "COMPLETED"
                    meta["task_status"] = "COMPLETED"
                    meta["end_time"] = now
                    meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            meta["duration"] = int(now - meta.get("start_time", now))
            if status == "RUNNING":
                results.append(meta)
        except Exception:
            continue
    return results


def get_task_status(task_id: str) -> dict[str, Any]:
    task_dir = get_tasks_dir() / task_id
    meta_file = task_dir / "meta.json"
    log_file = task_dir / "output.log"
    if not meta_file.exists():
        return {"error": f"Task {task_id} not found"}
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    pid = meta.get("pid")
    if pid and meta.get("task_status") == "RUNNING" and not check_pid_alive(pid):
        meta["task_status"] = "COMPLETED"
        meta["end_time"] = time.time()
        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        meta["log_tail"] = "\n".join(lines[-30:])
    return meta


def print_hud(running_tasks: list[dict[str, Any]] | None = None, new_request: str = "", force_refresh: bool = False) -> None:
    probe = probe_local_models(force=force_refresh)
    if running_tasks is None:
        running_tasks = list_active_tasks()
    half_price, bj_time = is_deepseek_half_price_window()
    cd = probe.get("codex_cooldown", {})
    matrix = probe["matrix"]
    codex_ok = bool(probe.get("codex_binary")) and not cd.get("active") and any(matrix[code]["slug"] for code in ("9A", "9B", "9C", "9D"))
    codex_state = (
        f"🟢 就绪 ({len(probe.get('codex_valid_slugs', []))} 模型)"
        if codex_ok
        else f"🟡 冷却/受限 ({cd.get('reason', '未就绪')}) ➔ 自动走 Tier 2"
    )
    ds_window_tag = (
        f"🟢 空闲半价中({bj_time}, 工作日非09-12/14-18及周末节假日均半价)"
        if half_price
        else f"⚪ 高峰原价({bj_time}, 工作日09-12/14-18高峰, 若法定节假日全天半价)"
    )

    task_lines = []
    if running_tasks:
        for t in running_tasks:
            task_lines.append(
                f"│      • [后台运行中] ID: {t['task_id']} │ 引擎: {t['runner']} ({t.get('model')}) │ 耗时: {t['duration']}s"
            )
    else:
        task_lines.append("│      • [状态] 无挂起任务；≤3步小事当前会话秒办，重型独立活优先 Codex 周期池")

    hud = f"""┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E07 · 三级阶梯派发与跨池接力中心 v1.2.0]               │
│    [🟢 轻量直办] │ [🥇 Tier1 Codex 周期] ➔ [🥈 Tier2 两共享池] ➔ [🥉 问DeepSeek]│
├────────────────────────────────────────────────────────────────────────────┤
│ 💡 活跃监控 & 三级阶梯可用性:                                              │
{chr(10).join(task_lines)}
│    • 🥇 Tier 1 · OpenAI Codex 周期订阅池 [{codex_state}]:
│      [9B] {matrix['9B']['name']}（主力） │ [9A] {matrix['9A']['name']}（旗舰）
│      [9C] {matrix['9C']['name']}（视觉） │ [9D] {matrix['9D']['name']}（批量）
│    • 🥈 Tier 2 · 客户端内置两大共享池（Codex Free/耗尽自动接力 · 跨池顺延）:│
│      [1] 跑腿：Gemini [1A/1B] ↔ Claude [1C]
│      [2] 编码：Claude [2A] ↔ Gemini [2B]
│      [3] 架构：Gemini [3A/3C] ↔ Claude [3B]
│      [4] 审查：Gemini [4A] ↔ Claude [3B]
│    • 🥉 Tier 3 · DeepSeek 按量咨询席（🔒永不自动调，异常先问 · {ds_window_tag}）:
│      [8A] {matrix['8A']['name']} │ [8B] {matrix['8B']['name']}
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 全局 .前缀零撞车快捷口令（释放裸字母 A/B/C/D 给选择题）:                │
│    • [9A~9D] Tier1 Codex │ [1A~4A] Tier2 内置 │ [8A/8B] 确认后按量 DeepSeek│
│    • [.s/状态] 进度与额度 │ [.?/面板/选模] 唤出此看板（唯一焦点锁）         │
└────────────────────────────────────────────────────────────────────────────┘"""
    print(hud)


def main() -> None:
    if sys.argv[1:2] == ["radar"]:
        raise SystemExit(model_radar.main(sys.argv[2:]))
    parser = argparse.ArgumentParser(description="E07 三级阶梯派发与跨池接力中心 v1.2.0")
    subparsers = parser.add_subparsers(dest="subcommand")

    hud_p = subparsers.add_parser("hud", help="展示三级阶梯 HUD 看板")
    hud_p.add_argument("--request", default="", help="需求预览")
    hud_p.add_argument("--refresh", action="store_true", help="强制刷新缓存")

    probe_p = subparsers.add_parser("probe", help="输出模型矩阵与快速缓存")
    probe_p.add_argument("--force", action="store_true", help="强制刷新")

    disp_p = subparsers.add_parser("dispatch", help="按统一代号派发任务（支持 Tier1->Tier2 回退、两池跨池顺延与 Tier3 确认门禁）")
    disp_p.add_argument("--choice", default="9B", help="模型代号 (9A~9D Codex周期; 1A~4A 内置两池; 8A/8B DeepSeek按量)")
    disp_p.add_argument("--prompt", required=True, help="任务描述")
    disp_p.add_argument("--workspace", default=os.getcwd(), help="工作区路径")
    disp_p.add_argument("--role", default=None, help="角色")
    disp_p.add_argument("--exhausted", default="", help="已耗尽的模型 slug 或桶名（逗号分隔，自动扩展同桶模型）")
    disp_p.add_argument("--dry-run", action="store_true", help="干跑验证命令生成，不启动真实外部进程")
    disp_p.add_argument("--refresh", action="store_true", help="强制重新探测缓存")
    disp_p.add_argument("--user-confirmed", action="store_true", help="Tier 3 DeepSeek 按量付费已获用户明确确认")

    cd_p = subparsers.add_parser("cooldown", help="管理 Codex Free/429 冷却状态")
    cd_p.add_argument("--minutes", type=int, default=60, help="冷却分钟数")
    cd_p.add_argument("--reason", default="codex quota exhausted or free tier", help="冷却原因")
    cd_p.add_argument("--clear", action="store_true", help="清除冷却状态")

    stat_p = subparsers.add_parser("status", help="查看后台任务状态")
    stat_p.add_argument("--task-id", default=None)

    coll_p = subparsers.add_parser("collect", help="收集后台任务结果")
    coll_p.add_argument("--task-id", required=True)

    subparsers.add_parser("radar", help="运行模型变化雷达")
    args = parser.parse_args()
    if args.subcommand == "hud":
        print_hud(new_request=args.request, force_refresh=args.refresh)
    elif args.subcommand == "probe":
        print(json.dumps(probe_local_models(force=args.force, persist=True), ensure_ascii=False, indent=2))
    elif args.subcommand == "cooldown":
        out = clear_codex_cooldown() if args.clear else set_codex_cooldown(args.minutes, args.reason)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.subcommand == "dispatch":
        res = dispatch_task(
            args.choice,
            args.prompt,
            args.workspace,
            role=args.role,
            exhausted_csv=args.exhausted,
            dry_run=args.dry_run,
            refresh=args.refresh,
            user_confirmed=args.user_confirmed,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if res["status"] == "DELEGATE_DRY_RUN_FAILED":
            raise SystemExit(1)
    elif args.subcommand == "status":
        out = get_task_status(args.task_id) if args.task_id else list_active_tasks()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.subcommand == "collect":
        print(json.dumps(get_task_status(args.task_id), ensure_ascii=False, indent=2))
    else:
        print_hud()


if __name__ == "__main__":
    main()
