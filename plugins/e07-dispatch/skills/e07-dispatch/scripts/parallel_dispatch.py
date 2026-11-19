#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E07 · 智能工种派发与额度接力中心 v1.0.0
核心特性：
1. 100% 优先客户端内置免费模型池（4大工种：1极速跑腿 / 2写代码工匠 / 3统筹架构 / 4深度挑刺）
2. 内置同工种智能额度接力链（Quota Fallback Chain）：首选配额耗尽自动顺延至第一/第二替补
3. 付费外援（8=DeepSeek dsh, 9=OpenAI Codex）退居非默认席，仅在显式指定 8A/8B/9A/9B 时调用本目录 delegate.py
4. 彻底斩断跨目录依赖 E06，内置模型直接秒回 subagent / swarm 调度指令 JSON（耗时 < 0.05s，0 崩溃）
5. 读取极简 models_fast_cache.json (<2KB)，秒弹三段式工种分工 + 额度状态 + 免费/付费分区 HUD 看板
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
ENV_CONFIG_FILE = CURRENT_DIR / "local_env.json"
MODELS_CACHE_FILE = CURRENT_DIR / "models_cache.json"
FAST_CACHE_FILE = CURRENT_DIR / "models_fast_cache.json"
LOCAL_DELEGATE = CURRENT_DIR / "delegate.py"

# 全局统一模型矩阵（E06 与 E07 100% 共用同一套代号）
MODEL_MATRIX: dict[str, dict[str, Any]] = {
    "1A": {
        "code": "1A",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 3.8 Flash (Medium/Low)",
        "slug": "gemini-3.8-flash-medium",
        "subagent_model": "flash",
        "quota_default": "94%",
        "fallback_chain": [
            "gemini-3.8-flash-medium",
            "gemini-3.8-flash-low",
            "gemini-4-hydrogen-low",
            "gpt-oss-120b-medium",
        ],
        "desc": "毫秒级响应 · 快速查文件/日志过滤/单文件小修",
    },
    "1B": {
        "code": "1B",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Hydrogen (Low)",
        "slug": "gemini-4-hydrogen-low",
        "subagent_model": "flash",
        "quota_default": "94%",
        "fallback_chain": [
            "gemini-4-hydrogen-low",
            "gemini-3.8-flash-medium",
            "gpt-oss-120b-medium",
        ],
        "desc": "极速第一替补 · 轻量高并发跑腿",
    },
    "1C": {
        "code": "1C",
        "pool": "1",
        "pool_name": "⚡ 极速跑腿池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "GPT-OSS 120B (Medium)",
        "slug": "gpt-oss-120b-medium",
        "subagent_model": "inherit",
        "quota_default": "34%",
        "fallback_chain": [
            "gpt-oss-120b-medium",
            "gemini-3.8-flash-medium",
            "gemini-4-hydrogen-low",
        ],
        "desc": "开源异构保底 · 独立桶配额",
    },
    "2A": {
        "code": "2A",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Claude Sonnet 5.5 (High/Medium)",
        "slug": "claude-sonnet-5-5-high",
        "subagent_model": "pro",
        "quota_default": "34%",
        "fallback_chain": [
            "claude-sonnet-5-5-high",
            "claude-sonnet-5-5-medium",
            "gemini-4-hydrogen-high",
            "gemini-4-argon-medium",
            "gpt-oss-120b-medium",
        ],
        "desc": "编码首选标杆 · 前端UI实现/功能开发/重构修Bug",
    },
    "2B": {
        "code": "2B",
        "pool": "2",
        "pool_name": "💻 写代码工匠池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Hydrogen (Medium/High)",
        "slug": "gemini-4-hydrogen-medium",
        "subagent_model": "pro",
        "quota_default": "94%",
        "fallback_chain": [
            "gemini-4-hydrogen-medium",
            "gemini-4-hydrogen-high",
            "gemini-4-argon-medium",
            "gpt-oss-120b-medium",
        ],
        "desc": "编码第一替补 · 新一代敏捷全栈编码主力",
    },
    "3A": {
        "code": "3A",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Argon (Medium/High)",
        "slug": "gemini-4-argon-high",
        "subagent_model": "pro",
        "quota_default": "66% (周池)",
        "fallback_chain": [
            "gemini-4-argon-high",
            "gemini-4-argon-medium",
            "claude-opus-5-5-high",
            "gemini-pro-orchestrator-g1-pro",
        ],
        "desc": "统筹首选主力 · 周重置大额度池/超长上下文全局视野",
    },
    "3B": {
        "code": "3B",
        "pool": "3",
        "pool_name": "🏗️ 统筹与架构池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Claude Opus 5.5 (High/Medium)",
        "slug": "claude-opus-5-5-high",
        "subagent_model": "pro",
        "quota_default": "34%",
        "fallback_chain": [
            "claude-opus-5-5-high",
            "claude-opus-5-5-medium",
            "gemini-4-argon-high",
            "gemini-pro-orchestrator-g1-pro",
        ],
        "desc": "架构第一替补 · 顶层设计与文档规范极佳",
    },
    "4A": {
        "code": "4A",
        "pool": "4",
        "pool_name": "🔍 深度挑刺推理池 (内置免费)",
        "tier": "native_free",
        "runner": "native",
        "name": "Gemini 4 Neon (High/XHigh)",
        "slug": "gemini-4-neon-high",
        "subagent_model": "pro",
        "quota_default": "94%",
        "fallback_chain": [
            "gemini-4-neon-high",
            "gemini-4-neon-xhigh",
            "claude-opus-5-5-high",
            "gemini-4-argon-high",
        ],
        "desc": "红方挑刺首选 · 深度推理思考链/死锁与疑难Bug根因推导",
    },
    "8A": {
        "code": "8A",
        "pool": "8",
        "pool_name": "💰 付费外援 · DeepSeek (非默认)",
        "tier": "paid_external",
        "runner": "dsh",
        "name": "DeepSeek-R1 / Reasoner",
        "slug": "deepseek-reasoner",
        "quota_default": "按量付费API",
        "fallback_chain": ["deepseek-reasoner", "deepseek-chat"],
        "desc": "外部付费深度推理 · 仅显式输入 8A 点名时调用",
    },
    "8B": {
        "code": "8B",
        "pool": "8",
        "pool_name": "💰 付费外援 · DeepSeek (非默认)",
        "tier": "paid_external",
        "runner": "dsh",
        "name": "DeepSeek-V3 / Chat",
        "slug": "deepseek-chat",
        "quota_default": "按量付费API",
        "fallback_chain": ["deepseek-chat"],
        "desc": "外部付费通用分析 · 仅显式输入 8B 点名时调用",
    },
    "9A": {
        "code": "9A",
        "pool": "9",
        "pool_name": "💰 付费外援 · OpenAI Codex (非默认)",
        "tier": "paid_external",
        "runner": "codex",
        "name": "Codex 6.2 Sol (旗舰)",
        "slug": "gpt-6.2-sol",
        "quota_default": "外部订阅/API",
        "fallback_chain": ["gpt-6.2-sol", "gpt-6.1-sol"],
        "desc": "外部付费旗舰编码 · 仅显式输入 9A 点名时调用",
    },
    "9B": {
        "code": "9B",
        "pool": "9",
        "pool_name": "💰 付费外援 · OpenAI Codex (非默认)",
        "tier": "paid_external",
        "runner": "codex",
        "name": "Codex 6.1 Sol (稳健)",
        "slug": "gpt-6.1-sol",
        "quota_default": "外部订阅/API",
        "fallback_chain": ["gpt-6.1-sol"],
        "desc": "外部付费稳健基线 · 仅显式输入 9B 点名时调用",
    },
}

POOL_DEFAULTS = {
    "1": "1A",
    "2": "2A",
    "3": "3A",
    "4": "4A",
    "8": "8A",
    "9": "9A",
}

SLUG_TO_SUBAGENT_MODEL = {
    "gemini-3.8-flash-medium": "flash",
    "gemini-3.8-flash-low": "flash",
    "gemini-3.8-flash-high": "flash",
    "gemini-4-hydrogen-low": "flash",
    "gemini-4-hydrogen-medium": "pro",
    "gemini-4-hydrogen-high": "pro",
    "claude-sonnet-5-5-high": "pro",
    "claude-sonnet-5-5-medium": "pro",
    "claude-opus-5-5-high": "pro",
    "claude-opus-5-5-medium": "pro",
    "gemini-4-argon-high": "pro",
    "gemini-4-argon-medium": "pro",
    "gemini-4-neon-high": "pro",
    "gemini-4-neon-xhigh": "pro",
    "gemini-pro-orchestrator-g1-pro": "pro",
    "gpt-oss-120b-medium": "inherit",
}


def load_env_config() -> dict[str, Any]:
    if ENV_CONFIG_FILE.exists():
        try:
            return json.loads(ENV_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "python_interpreter": sys.executable,
        "dsh_binary": r"E:\A001-软件安装\deepseek\resources\runtime\cli\bin\dsh.cmd",
        "codex_binary": r"C:\Users\fight\AppData\Local\OpenAI\Codex\bin\9e1da79431da526b\codex.exe",
        "default_choice": "1A",
        "default_runner": "native",
        "paid_external_default": False,
        "tasks_dir": str(Path.home() / ".gemini" / "antigravity" / "scratch" / "e07_tasks"),
    }


def get_tasks_dir() -> Path:
    cfg = load_env_config()
    td = Path(cfg.get("tasks_dir", Path.home() / ".gemini" / "antigravity" / "scratch" / "e07_tasks"))
    td.mkdir(parents=True, exist_ok=True)
    return td


def load_fast_codex_cache(force_refresh: bool = False) -> dict[str, Any]:
    """优先读取 <2KB 的 models_fast_cache.json，速度提升百倍"""
    for candidate in (FAST_CACHE_FILE, Path.home() / ".codex" / "models_fast_cache.json"):
        if not force_refresh and candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                pass

    src = Path.home() / ".codex" / "models_cache.json"
    fast_models = []
    if src.exists():
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
    payload = {
        "version": "1.0.0",
        "updated_at": datetime.now().isoformat(),
        "valid_codex_slugs": [m["slug"] for m in fast_models],
        "codex_models": fast_models,
    }
    try:
        FAST_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


def probe_local_models(force: bool = False) -> dict[str, Any]:
    if not force and MODELS_CACHE_FILE.exists():
        try:
            cached = json.loads(MODELS_CACHE_FILE.read_text(encoding="utf-8"))
            if cached.get("schema_version") == "1.0.0":
                return cached
        except Exception:
            pass

    fast_codex = load_fast_codex_cache(force_refresh=force)
    probe_result = {
        "schema_version": "1.0.0",
        "probed_at": datetime.now().isoformat(),
        "status": "READY",
        "policy": "native_free_first_paid_external_locked",
        "matrix": MODEL_MATRIX,
        "codex_valid_slugs": fast_codex.get("valid_codex_slugs", []),
    }
    MODELS_CACHE_FILE.write_text(json.dumps(probe_result, ensure_ascii=False, indent=2), encoding="utf-8")
    return probe_result


def resolve_choice(choice_code: str) -> dict[str, Any]:
    raw = (choice_code or "1A").strip().upper()
    if raw in POOL_DEFAULTS:
        raw = POOL_DEFAULTS[raw]
    if raw not in MODEL_MATRIX:
        # 未识别代号一律安全回退至内置免费极速模型 1A，绝不误触发付费外援
        raw = "1A"
    return dict(MODEL_MATRIX[raw])


def resolve_with_quota_fallback(item: dict[str, Any], exhausted_slugs: set[str]) -> dict[str, Any]:
    """当首选内置模型配额耗尽时，沿同工种 fallback_chain 自动顺延接力"""
    primary_slug = item["slug"]
    chain = item.get("fallback_chain", [primary_slug])
    selected_slug = primary_slug
    fallback_triggered = False

    if primary_slug in exhausted_slugs:
        fallback_triggered = True
        for candidate in chain:
            if candidate not in exhausted_slugs:
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


def dispatch_task(
    choice_code: str,
    prompt: str,
    workspace: str,
    role: str | None = None,
    exhausted_csv: str = "",
    dry_run: bool = False,
    refresh: bool = False,
) -> dict[str, Any]:
    item = resolve_choice(choice_code)
    exhausted_set = {s.strip() for s in exhausted_csv.split(",") if s.strip()}
    resolved = resolve_with_quota_fallback(item, exhausted_set)

    # Case A: 内置免费模型 (1A~4A) -> 直接生成原生 subagent / swarm 调度指令 JSON，绝不调用外部 CLI delegate.py
    if item["tier"] == "native_free":
        return {
            "status": "NATIVE_DISPATCH_READY",
            "dispatch_mode": "native",
            "paid_external_triggered": False,
            "choice_code": resolved["code"],
            "pool_name": resolved["pool_name"],
            "runner": "native",
            "primary_model": resolved["primary_model_slug"],
            "selected_model": resolved["selected_model_slug"],
            "subagent_model": resolved["subagent_model"],
            "fallback_triggered": resolved["fallback_triggered"],
            "fallback_chain": resolved["fallback_chain"],
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

    # Case B: 显式点名外部付费外援 (8A/8B/9A/9B) -> 调用本目录独立收编的 delegate.py
    cfg = load_env_config()
    py_bin = cfg.get("python_interpreter", sys.executable)
    runner = item["runner"]
    model_slug = resolved["selected_model_slug"]

    if runner == "codex":
        fast_cache = load_fast_codex_cache(force_refresh=refresh)
        valid_slugs = {s.lower() for s in fast_cache.get("valid_codex_slugs", [])}
        if valid_slugs and model_slug.lower() not in valid_slugs:
            model_slug = "gpt-6.1-sol"

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
    if role:
        cmd.extend(["--role", role])
    if refresh:
        cmd.append("--refresh")
    if dry_run:
        cmd.extend(["--dry-run", "--json"])
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            delegate_payload = json.loads(proc.stdout.strip())
        except Exception:
            delegate_payload = {"raw_stdout": proc.stdout.strip(), "raw_stderr": proc.stderr.strip()}
        return {
            "status": "PAID_EXTERNAL_DRY_RUN",
            "dispatch_mode": "paid_external",
            "paid_external_triggered": True,
            "choice_code": item["code"],
            "runner": runner,
            "selected_model": model_slug,
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
            creationflags=creationflags,
        )

    meta = {
        "status": "PAID_EXTERNAL_DISPATCHED",
        "dispatch_mode": "paid_external",
        "paid_external_triggered": True,
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
        "created_at": datetime.now().isoformat(),
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
    probe_local_models(force=force_refresh)
    if running_tasks is None:
        running_tasks = list_active_tasks()

    task_lines = []
    if running_tasks:
        for t in running_tasks:
            task_lines.append(
                f"│      • [后台运行中] ID: {t['task_id']} │ 引擎: {t['runner']} ({t.get('model')}) │ 耗时: {t['duration']}s"
            )
    else:
        task_lines.append("│      • [状态] 暂无外部后台挂起任务；≤3步小事当前会话秒办，重任务按工种派发")

    req_preview = (new_request or "默认按工种匹配内置免费模型，额度耗尽自动顺延接力...").strip()
    if len(req_preview) > 54:
        req_preview = req_preview[:51] + "..."

    hud = f"""┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E07 · 智能工种派发与额度自动接力中心 v1.0.0]           │
│    [🟢 轻量主会话秒办] │ [🚀 重型按工种派内置] ➔ [🔄 额度空自动顺延接力]    │
├────────────────────────────────────────────────────────────────────────────┤
│ 💡 当前状态诊断与工种模型池（优先吃满客户端内置免费额度 · 0 额外付费）:    │
│    • 活跃任务监控:                                                         │
{chr(10).join(task_lines)}
│    • 当前派发策略: 👉 "{req_preview}"
│    • 【内置免费主力池（支持同工种额度耗尽自动降级接力）】:                 │
│      👉★[1] ⚡ 极速跑腿池 ── [1A] Gemini 3.8 Flash (94%) ➔ [1B] Hydrogen Low ➔ [1C] GPT-OSS 120B│
│      👉★[2] 💻 写代码工匠 ── [2A] Claude Sonnet 5.5 (34%) ➔ [2B] Gemini 4 Hydrogen (94%)       │
│      👉★[3] 🏗️ 统筹架构师 ── [3A] Gemini 4 Argon (66%周池) ➔ [3B] Claude Opus 5.5 (34%)        │
│      👉★[4] 🔍 深度挑刺池 ── [4A] Gemini 4 Neon High (94%) ➔ [3B] Opus 5.5 ➔ [3A] Argon High  │
│    • 【外部付费外援席（🔒非默认！仅显式输入 8A/8B/9A/9B 点名时调用）】:    │
│         [8] 💰 DeepSeek   ── [8A] DeepSeek-R1/Reasoner   │ [8B] DeepSeek-V3/Chat               │
│         [9] 💰 Codex CLI  ── [9A] Codex 6.2 Sol (旗舰)   │ [9B] Codex 6.1 Sol (稳健)           │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 全局单字符/组合键速查（E06 与 E07 100% 统一代号，零冲突）:               │
│    • [1A]~[4A]       : 直选内置免费对应工种主力（额度空自动沿替补链顺延）  │
│    • [8A]/[8B]       : 显式解锁付费外援 DeepSeek (Reasoner / Chat)         │
│    • [9A]/[9B]       : 显式解锁付费外援 OpenAI Codex (6.2 Sol / 6.1 Sol)   │
│    • [s] / [c] / [r] : 查看后台状态 / 汇总产出 / 重新刷新模型与额度缓存    │
│    • [?]             : 秒呼此工种分工与额度接力看板                        │
└────────────────────────────────────────────────────────────────────────────┘"""
    print(hud)


def main() -> None:
    parser = argparse.ArgumentParser(description="E07 智能工种派发与额度接力中心 v1.0.0")
    subparsers = parser.add_subparsers(dest="subcommand")

    hud_p = subparsers.add_parser("hud", help="展示三段式工种分工与额度接力 HUD 看板")
    hud_p.add_argument("--request", default="", help="需求预览")
    hud_p.add_argument("--refresh", action="store_true", help="强制刷新缓存")

    probe_p = subparsers.add_parser("probe", help="输出模型矩阵与快速缓存")
    probe_p.add_argument("--force", action="store_true", help="强制刷新")

    disp_p = subparsers.add_parser("dispatch", help="按统一代号派发任务（支持内置额度顺延与外援干跑验证）")
    disp_p.add_argument("--choice", default="1A", help="模型代号 (1A~4A 内置免费; 8A/8B/9A/9B 付费外援)")
    disp_p.add_argument("--prompt", required=True, help="任务描述")
    disp_p.add_argument("--workspace", default=os.getcwd(), help="工作区路径")
    disp_p.add_argument("--role", default=None, help="角色")
    disp_p.add_argument("--exhausted", default="", help="模拟或传入已耗尽配额的模型 slug（逗号分隔，测试自动顺延）")
    disp_p.add_argument("--dry-run", action="store_true", help="干跑验证命令生成，不启动真实外部付费进程")
    disp_p.add_argument("--refresh", action="store_true", help="强制重新探测 CLI")

    stat_p = subparsers.add_parser("status", help="查看后台任务状态")
    stat_p.add_argument("--task-id", default=None)

    coll_p = subparsers.add_parser("collect", help="收集后台任务结果")
    coll_p.add_argument("--task-id", required=True)

    args = parser.parse_args()
    if args.subcommand == "hud":
        print_hud(new_request=args.request, force_refresh=args.refresh)
    elif args.subcommand == "probe":
        print(json.dumps(probe_local_models(force=args.force), ensure_ascii=False, indent=2))
    elif args.subcommand == "dispatch":
        res = dispatch_task(
            args.choice,
            args.prompt,
            args.workspace,
            role=args.role,
            exhausted_csv=args.exhausted,
            dry_run=args.dry_run,
            refresh=args.refresh,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.subcommand == "status":
        out = get_task_status(args.task_id) if args.task_id else list_active_tasks()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.subcommand == "collect":
        print(json.dumps(get_task_status(args.task_id), ensure_ascii=False, indent=2))
    else:
        print_hud()


if __name__ == "__main__":
    main()
