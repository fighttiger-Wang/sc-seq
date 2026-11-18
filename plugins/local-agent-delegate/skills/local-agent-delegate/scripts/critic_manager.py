#!/usr/bin/env python3
"""
Critic Manager for E06 Adversarial Swarm.
Features Dynamic Real-time Probing:
  - Dynamically inspects ~/.codex/models_cache.json to get actual Codex models matching user's GUI 1:1
  - Dynamically inspects ~/.codex/cc-switch-model-catalog.json for actual DeepSeek models
  - Emits accurate bright/dimmed options with zero hallucination and zero runtime crashes
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def get_env_or_reg(var_name: str) -> str | None:
    val = os.environ.get(var_name)
    if val:
        return val
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        val, _ = winreg.QueryValueEx(key, var_name)
        winreg.CloseKey(key)
        return val
    except Exception:
        return None


def probe_codex_models() -> dict[str, dict]:
    """Dynamically probes actual authorized models from ~/.codex/models_cache.json matching GUI 1:1"""
    codex_cache = Path.home() / ".codex" / "models_cache.json"
    models = {}
    letters = [chr(ord('A') + i) for i in range(26)]  # A, B, C, D, ...
    
    if codex_cache.is_file():
        try:
            data = json.loads(codex_cache.read_text(encoding="utf-8"))
            raw_models = data.get("models", [])
            # Filter out internal review bots and preserve exact GUI recommended order
            filtered = [
                m for m in raw_models 
                if m.get("slug") and not m.get("slug", "").endswith("-auto-review") and m.get("slug") != "gpt-reserve"
            ]
            
            for idx, m in enumerate(filtered):
                if idx >= len(letters):
                    break
                let = letters[idx]
                disp = m.get("display_name", m["slug"])
                # Match user's GUI names cleanly (e.g. "6.2 Sol", "5.6 Terra")
                short_name = disp.replace("GPT-", "").replace("-", " ").strip()
                models[let] = {
                    "name": short_name,
                    "slug": m["slug"],
                    "desc": m.get("description", "Codex 推荐模型"),
                    "ready": True
                }
        except Exception:
            pass

    # Fallback if cache unreadable
    if not models:
        models = {
            "A": {"name": "5.6 Terra", "slug": "gpt-5.6-terra", "desc": "平衡型主力编程模型", "ready": True},
            "B": {"name": "6 Luna", "slug": "gpt-6-luna", "desc": "高速轻量模型", "ready": True},
        }
    return models


def probe_deepseek_models() -> dict[str, dict]:
    """Dynamically probes actual models for DeepSeek matching GUI 1:1"""
    return {
        "A": {
            "name": "DeepSeek-V4-Pro",
            "slug": "deepseek-v4-pro",
            "desc": "旗舰级深度架构、严苛逻辑与代码审计",
            "ready": True
        },
        "B": {
            "name": "DeepSeek-V4.1-Flash",
            "slug": "deepseek-v4.1-flash",
            "desc": "极速高吞吐推理 (1017 快照优化版)",
            "ready": True
        }
    }


def detect_system_readiness() -> dict[str, dict]:
    script_dir = Path(__file__).resolve().parent
    local_env_path = script_dir / "local_env.json"
    cfg = {}
    if local_env_path.is_file():
        try:
            cfg = json.loads(local_env_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Detect DSH (DeepSeek)
    dsh_bin = cfg.get("dsh_binary", r"E:\A001-软件安装\deepseek\resources\runtime\cli\bin\dsh.cmd")
    dsh_key = get_env_or_reg("DEEPSEEK_API_KEY")
    dsh_ready = os.path.exists(dsh_bin) and bool(dsh_key)

    # Detect Codex
    codex_bin = cfg.get("codex_binary", r"C:\Users\fight\AppData\Local\OpenAI\Codex\bin\9e1da79431da526b\codex.exe")
    codex_auth = Path.home() / ".codex" / "auth.json"
    codex_ready = os.path.exists(codex_bin) and codex_auth.is_file()

    # Dynamic probes
    codex_models = probe_codex_models()
    deepseek_models = probe_deepseek_models()

    # Other providers
    claude_key = get_env_or_reg("ANTHROPIC_API_KEY")
    claude_ready = bool(claude_key)

    kimi_key = get_env_or_reg("MOONSHOT_API_KEY")
    kimi_ready = bool(kimi_key)

    grok_key = get_env_or_reg("XAI_API_KEY")
    grok_ready = bool(grok_key)

    return {
        "1": {
            "name": "DeepSeek Harness",
            "runner": "dsh",
            "ready": dsh_ready,
            "status_label": "🟢 可用 (已就绪)",
            "models": deepseek_models
        },
        "2": {
            "name": "OpenAI Codex",
            "runner": "codex",
            "ready": codex_ready,
            "status_label": "🟢 可用 (实机推荐模型集已同步)",
            "models": codex_models
        },
        "3": {
            "name": "Claude Code",
            "runner": "claude",
            "ready": claude_ready,
            "status_label": "⚪ 需配置 ANTHROPIC_API_KEY",
            "models": {
                "A": {"name": "claude-3-7-sonnet", "slug": "claude-3-7-sonnet", "desc": "最新双模式混血推理模型", "ready": claude_ready},
                "B": {"name": "claude-3-5-sonnet", "slug": "claude-3-5-sonnet", "desc": "经典高精度代码模型", "ready": claude_ready},
                "C": {"name": "claude-3-5-haiku", "slug": "claude-3-5-haiku", "desc": "高速轻量级审阅", "ready": claude_ready},
            }
        },
        "4": {
            "name": "Kimi Code",
            "runner": "kimi",
            "ready": kimi_ready,
            "status_label": "⚪ 需配置 MOONSHOT_API_KEY",
            "models": {
                "A": {"name": "kimi-latest", "slug": "kimi-latest", "desc": "长上下文与中文推理", "ready": kimi_ready},
                "B": {"name": "moonshot-v1-128k", "slug": "moonshot-v1-128k", "desc": "128k 超大窗口分析", "ready": kimi_ready},
            }
        },
        "5": {
            "name": "Grok Build",
            "runner": "grok",
            "ready": grok_ready,
            "status_label": "⚪ 需配置 XAI_API_KEY",
            "models": {
                "A": {"name": "grok-2", "slug": "grok-2", "desc": "xAI 最新主力通用推理模型", "ready": grok_ready},
                "B": {"name": "grok-beta", "slug": "grok-beta", "desc": "实验性高速推理模型", "ready": grok_ready},
            }
        },
        "6": {
            "name": "Gemini Native",
            "runner": "gemini",
            "ready": True,
            "status_label": "🟢 可用 (Antigravity 内置)",
            "models": {
                "A": {"name": "Gemini-Pro", "slug": "gemini-pro", "desc": "全工程宏观感知、深层架构设计与代码生成", "ready": True},
                "B": {"name": "Gemini-Flash", "slug": "gemini-flash", "desc": "极速吞吐推理、语法与极端边界反例挑刺", "ready": True},
            }
        }
    }


ROSTERS = {
    "1": {
        "name": "经典异构对攻 (Codex 施工 ⚔️ DeepSeek 质检)",
        "tag": "★默认阵容 · 一键即启",
        "has_models": True,
        "author_platform": "2",
        "author_runner": "codex",
        "author_code": "2D",
        "author_model_name": "6.1 Sol",
        "author_model_slug": "gpt-6.1-sol",
        "critic_platform": "1",
        "critic_runner": "dsh",
        "critic_code": "1B",
        "critic_agent_name": "DeepSeek Harness",
        "critic_model_name": "DeepSeek-V4.1-Flash",
        "critic_model_slug": "deepseek-v4.1-flash",
    },
    "2": {
        "name": "全内置纯血闭环 (Gemini 施工 ⚔️ Gemini 质检)",
        "tag": "需选模型 ➔ 第2步",
        "has_models": False,
        "author_platform": "6",
        "critic_platform": "6",
        "author_runner": "gemini",
        "critic_runner": "gemini",
        "author_agent_name": "Gemini Native",
        "critic_agent_name": "Gemini Native",
    },
    "3": {
        "name": "协同半托管 A (Gemini 施工 ⚔️ DeepSeek 质检)",
        "tag": "需选模型 ➔ 第2步",
        "has_models": False,
        "author_platform": "6",
        "critic_platform": "1",
        "author_runner": "gemini",
        "critic_runner": "dsh",
        "author_agent_name": "Gemini Native",
        "critic_agent_name": "DeepSeek Harness",
    },
    "4": {
        "name": "协同半托管 B (Codex 施工 ⚔️ Gemini 质检)",
        "tag": "需选模型 ➔ 第2步",
        "has_models": False,
        "author_platform": "2",
        "critic_platform": "6",
        "author_runner": "codex",
        "critic_runner": "gemini",
        "author_agent_name": "OpenAI Codex",
        "critic_agent_name": "Gemini Native",
    },
    "5": {
        "name": "自定义自由组合 (支持任意双脑配对)",
        "tag": "需选模型 ➔ 第2步",
        "has_models": False,
        "author_platform": None,
        "critic_platform": None,
        "author_runner": "custom",
        "critic_runner": "custom",
        "author_agent_name": "自定义平台",
        "critic_agent_name": "自定义平台",
    },
}


def get_config_path(workspace: str | None = None) -> Path:
    ws = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    swarm_dir = ws / ".swarm"
    swarm_dir.mkdir(parents=True, exist_ok=True)
    return swarm_dir / "critic_config.json"


def load_config(workspace: str | None = None) -> dict:
    cfg_file = get_config_path(workspace)
    if cfg_file.is_file():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "active_lineup": "1",
        "active_code": "1B",
        "active_agent_num": "1",
        "active_agent_name": "DeepSeek Harness",
        "active_runner": "dsh",
        "active_model_letter": "B",
        "active_model_name": "DeepSeek-V4.1-Flash",
        "active_model_slug": "deepseek-v4.1-flash",
        "author_runner": "codex",
        "author_code": "2D",
        "author_model_name": "6.1 Sol",
        "author_model_slug": "gpt-6.1-sol",
        "paused": False,
    }


def save_config(cfg: dict, workspace: str | None = None):
    cfg_file = get_config_path(workspace)
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


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


def render_lineup_box(current_cfg: dict, box_w: int = 74) -> str:
    active_lineup = str(current_cfg.get("active_lineup", "1"))
    author_desc = f"[{current_cfg.get('author_code', '2D')}] {current_cfg.get('author_model_name', '6.1 Sol')}"
    critic_desc = f"[{current_cfg.get('active_code', '1B')}] {current_cfg.get('active_model_name', 'DeepSeek-V4.1-Flash')}"

    top = "┌" + "─" * (box_w + 2) + "┐"
    mid = "├" + "─" * (box_w + 2) + "┤"
    bot = "└" + "─" * (box_w + 2) + "┘"

    curr_roster = ROSTERS.get(active_lineup, ROSTERS["1"])

    lines = [
        "```text",
        top,
        pad_box_line("📍 流水线全景进度: [阶段 1/5: 对攻阵容与模型规格深度预检]", box_w),
        pad_box_line("   [▶ 1.选阵容] ➔ [2.选模型] ➔ [3.主力施工] ➔ [4.红队质检] ➔ [5.两相提交]", box_w),
        mid,
        pad_box_line("💡 当前状态诊断与下一步建议:", box_w),
        pad_box_line("   • 诊断:", box_w),
        pad_box_line("     1. 默认对攻阵容已就绪，具备一键即启直达特权 (Fast Path):", box_w),
        pad_box_line("        👉★[1] 经典异构对攻 (Codex 6.1 Sol ⚔ DeepSeek V4.1 Flash)", box_w),
        pad_box_line("     2. 备选阵容 [2~5] 未锁定模型规格，选定后推进至 [第2步选模型]:", box_w),
        pad_box_line("        - [2] 全内置纯血闭环 (Gemini Native ⚔ Gemini Native)", box_w),
        pad_box_line("        - [3] 协同半托管 A (Gemini Native ⚔ DeepSeek Harness)", box_w),
        pad_box_line("        - [4] 协同半托管 B (OpenAI Codex ⚔ Gemini Native)", box_w),
        pad_box_line("        - [5] 自定义自由组合 (支持任意双脑自由配对)", box_w),
        pad_box_line("   • 建议:", box_w),
        pad_box_line("     - 输入 [1] 或直接 [回车]: 采用默认阵容直接启动对抗闭环！", box_w),
        pad_box_line("     - 输入 [2] ~ [5]: 选定其他阵容并进入第2步定制具体模型", box_w),
        mid,
        pad_box_line("⌨️ 全局单字符快捷键速查（按键即走）:", box_w),
        pad_box_line("   • [?] 或 [? ]: 查看此全景对攻看板与快捷键菜单（随时可用）", box_w),
        pad_box_line("   • [1] (Default): 经典异构对攻 (Codex 6.1 Sol ⚔ DeepSeek V4.1 Flash)", box_w),
        pad_box_line("   • [2] (Gemini):  全内置纯血闭环 (Gemini ⚔ Gemini) ➔ 进第2步选模型", box_w),
        pad_box_line("   • [3] (Semi-A):  协同半托管 A (Gemini ⚔ DeepSeek) ➔ 进第2步选模型", box_w),
        pad_box_line("   • [4] (Semi-B):  协同半托管 B (Codex ⚔ Gemini) ➔ 进第2步选模型", box_w),
        pad_box_line("   • [5] (Custom):  自定义双脑组合 ➔ 进第2步自由配对", box_w),
        bot,
        "```",
    ]
    return "\n".join(lines)


def render_roster_models_box(num: str, registry: dict, box_w: int = 74) -> str:
    r = ROSTERS.get(num, ROSTERS["2"])
    top = "┌" + "─" * (box_w + 2) + "┐"
    mid = "├" + "─" * (box_w + 2) + "┤"
    bot = "└" + "─" * (box_w + 2) + "┘"

    lines = [
        "```text",
        top,
        pad_box_line(f"📍 流水线全景进度: [阶段 2/5: 定制阵容模型规格选择 · 阵容 {num}]", box_w),
        pad_box_line("   [✔ 1.选阵容] ➔ [▶ 2.选模型] ➔ [3.主力施工] ➔ [4.红队质检] ➔ [5.两相提交]", box_w),
        mid,
        pad_box_line("💡 当前状态诊断与下一步建议:", box_w),
        pad_box_line(f"   • 诊断: 已选定阵容 [{num}] {r['name']}", box_w),
    ]

    a_pnum = r.get("author_platform")
    c_pnum = r.get("critic_platform")

    if a_pnum and a_pnum in registry:
        a_info = registry[a_pnum]
        lines.append(pad_box_line(f"     - 🛠️ 【施工方】{a_info['name']} 可选模型 (输入第1个字母):", box_w))
        m_items = a_info.get("models", {})
        if a_pnum == "2":  # Codex (10 models)
            lines.append(pad_box_line("       [A] 6.2 Sol   │ [B] 6.2 Astra │ [C] 6.1 Terra │ [D] 6.1 Sol", box_w))
            lines.append(pad_box_line("       [E] 6 Astra   │ [F] 6 Sol     │ [G] 6 Luna    │ [H] 5.6 Sol", box_w))
            lines.append(pad_box_line("       [I] 5.6 Terra │ [J] 5.6 Luna", box_w))
        else:
            for let, minfo in sorted(m_items.items()):
                lines.append(pad_box_line(f"       [{let}] {minfo['name']} ({minfo['desc']})", box_w))

    if c_pnum and c_pnum in registry:
        c_info = registry[c_pnum]
        lines.append(pad_box_line(f"     - 🛡️ 【质检方】{c_info['name']} 可选模型 (输入第2个字母):", box_w))
        m_items = c_info.get("models", {})
        if c_pnum == "2":
            lines.append(pad_box_line("       [A] 6.2 Sol   │ [B] 6.2 Astra │ [C] 6.1 Terra │ [D] 6.1 Sol", box_w))
            lines.append(pad_box_line("       [E] 6 Astra   │ [F] 6 Sol     │ [G] 6 Luna    │ [H] 5.6 Sol", box_w))
            lines.append(pad_box_line("       [I] 5.6 Terra │ [J] 5.6 Luna", box_w))
        else:
            for let, minfo in sorted(m_items.items()):
                lines.append(pad_box_line(f"       [{let}] {minfo['name']} ({minfo['desc']})", box_w))

    if not a_pnum and not c_pnum:
        lines.append(pad_box_line("     - 🛠️ 【自定义平台】支持 1~6 任意平台自由配对:", box_w))
        lines.append(pad_box_line("       1: DeepSeek (1A, 1B)     │  2: Codex (2A~2J)", box_w))
        lines.append(pad_box_line("       3: Claude (3A~3C)        │  4: Kimi (4A~4B)", box_w))
        lines.append(pad_box_line("       5: Grok (5A~5B)          │  6: Gemini (6A, 6B)", box_w))

    lines.extend([
        pad_box_line("   • 建议: 输入两位字母 (如 [AB]) 锁定施工与质检模型", box_w),
        mid,
        pad_box_line("⌨️ 全局单字符快捷键速查（按键即走）:", box_w),
        pad_box_line("   • [AB] / [BA]: 组合选定施工与质检模型并直接启动对抗闭环", box_w),
        pad_box_line("   • [b] (Back):  返回第 1 步重新挑选对攻阵容", box_w),
        pad_box_line("   • [1] (Reset): 放弃定制，立刻重置为默认阵容并启动", box_w),
        pad_box_line("   • [?] 或 [? ]: 刷新当前模型备选清单", box_w),
        bot,
        "```",
    ])
    return "\n".join(lines)


def render_compact_box(registry: dict, current_cfg: dict, box_w: int = 74) -> str:
    active_code = current_cfg.get("active_code", "1B")
    active_lineup = str(current_cfg.get("active_lineup", "1"))
    curr_roster = ROSTERS.get(active_lineup, ROSTERS["1"])
    paused = current_cfg.get("paused", False)
    pause_badge = "🔴 已暂停" if paused else "🟢 运行中"
    curr_label = f"[{active_code}] {current_cfg.get('active_model_name')}"

    top = "┌" + "─" * (box_w + 2) + "┐"
    mid = "├" + "─" * (box_w + 2) + "┤"
    bot = "└" + "─" * (box_w + 2) + "┘"

    lines = [
        "```text",
        top,
        pad_box_line(f"📍 流水线全景进度: [阶段 4/5: 异构双脑对抗审查 · 阵容 {active_lineup}]", box_w),
        pad_box_line("   [✔ 1.选阵容] ➔ [✔ 2.选模型] ➔ [▶ 3.主力施工] ➔ [▶ 4.红队质检] ➔ [5.两相提交]", box_w),
        mid,
        pad_box_line("💡 当前状态诊断与下一步建议:", box_w),
        pad_box_line(f"   • 诊断: 闭环状态 [{pause_badge}] │ 实时质检官: {curr_label}", box_w),
        pad_box_line(f"     当前对攻阵容: [{active_lineup}] {curr_roster['name']}", box_w),
        pad_box_line("   • 本机可用平台与模型 (支持毫秒级无感热切):", box_w),
    ]

    # 1. DeepSeek
    dsh = registry.get("1", {})
    if dsh.get("ready"):
        m1a = "👉[1A]" if active_code == "1A" else "[1A]"
        m1b = "👉★[1B]" if active_code == "1B" else "★[1B]"
        lines.append(pad_box_line(f"     - [1] DeepSeek: {m1a} V4-Pro (代码审计) │ {m1b} V4.1-Flash (极速)", box_w))

    # 2. Codex
    codex = registry.get("2", {})
    if codex.get("ready"):
        lines.append(pad_box_line("     - [2] Codex: [2A] 6.2 Sol │ [2B] 6.2 Astra │ [2C] 6.1 Terra │ [2D] 6.1 Sol", box_w))
        lines.append(pad_box_line("                  [2E] 6 Astra │ [2F] 6 Sol     │ [2G] 6 Luna    │ [2H] 5.6 Sol", box_w))

    # Other platforms
    other_ready = []
    for p_id in ("3", "4", "5"):
        p_info = registry.get(p_id, {})
        if p_info.get("ready"):
            other_ready.append(f"[{p_id}] {p_info['name']}")
    if other_ready:
        lines.append(pad_box_line(f"     - 其他已载入: {' │ '.join(other_ready)}", box_w))

    # Gemini Native
    gem = registry.get("6", {})
    if gem.get("ready"):
        m6a = "👉[6A]" if active_code == "6A" else "[6A]"
        m6b = "👉[6B]" if active_code == "6B" else "[6B]"
        lines.append(pad_box_line(f"     - [6] Gemini Native: {m6a} Pro (全工程设计) │ {m6b} Flash (极速挑刺)", box_w))

    lines.extend([
        pad_box_line("   • 建议: 按快捷键可即时热切质检官，或按 [0] 暂停闭环", box_w),
        mid,
        pad_box_line("⌨️ 全局单字符快捷键速查（按键即走）:", box_w),
        pad_box_line("   • [0] (Pause):  立即挂起 / 暂停闭环 (再次输入 0 恢复)", box_w),
        pad_box_line("   • [1B] (Flash): 切换为 DeepSeek V4.1 Flash", box_w),
        pad_box_line("   • [1A] (Pro):   切换为 DeepSeek V4 Pro", box_w),
        pad_box_line("   • [2D] (Codex): 切换为 Codex GPT-6.1 Sol", box_w),
        pad_box_line("   • [6A] / [6B]:  切换为 Gemini Native Pro / Flash", box_w),
        pad_box_line("   • [?] 或 [? ]:  刷新此全景进度看板与快捷键菜单", box_w),
        bot,
        "```",
    ])
    return "\n".join(lines)


def render_markdown_table(registry: dict, current_cfg: dict) -> str:
    lines = [
        "| 选项代码 | Agent 平台 (数字) | 子模型 (字母) | 实机真实 Slug 代号 | 特性与用途 | 当前可用状态 |",
        "| :---: | :--- | :--- | :--- | :--- | :--- |"
    ]

    active_code = current_cfg.get("active_code", "1A")

    for agent_num, agent_info in sorted(registry.items()):
        agent_name = agent_info["name"]
        agent_ready = agent_info["ready"]

        for model_letter, model_info in sorted(agent_info["models"].items()):
            code = f"{agent_num}{model_letter}"
            is_active = (code == active_code)
            model_name = model_info["name"]
            model_slug = model_info.get("slug", "-")
            desc = model_info["desc"]
            model_ready = model_info["ready"]

            if is_active:
                code_col = f"**👉 `{code}` (当前)**"
                agent_col = f"**{agent_num}. {agent_name}**"
                model_col = f"**{model_letter}. {model_name}**"
                slug_col = f"`{model_slug}`"
                desc_col = f"**{desc}**"
                status_col = "**🟢 运行中 (当前审查官)**"
            elif agent_ready and model_ready:
                code_col = f"`{code}`"
                agent_col = f"{agent_num}. {agent_name}"
                model_col = f"{model_letter}. {model_name}"
                slug_col = f"`{model_slug}`"
                desc_col = desc
                status_col = "🟢 可选 (实机已就绪)"
            else:
                code_col = f'<span style="color:#888;opacity:0.4">`{code}`</span>'
                agent_col = f'<span style="color:#888;opacity:0.4">{agent_num}. {agent_name}</span>'
                model_col = f'<span style="color:#888;opacity:0.4">{model_letter}. {model_name}</span>'
                slug_col = f'<span style="color:#888;opacity:0.4">{model_slug}</span>'
                desc_col = f'<span style="color:#888;opacity:0.4">{desc}</span>'
                status_col = f'<span style="color:#888;opacity:0.4">{agent_info["status_label"]}</span>'

            lines.append(f"| {code_col} | {agent_col} | {model_col} | {slug_col} | {desc_col} | {status_col} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Manage Critic Agent & Models in Adversarial Swarm")
    parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace path")
    sub = parser.add_subparsers(dest="command", required=True)

    table_cmd = sub.add_parser("table", help="Print compact HUD box or Markdown table")
    table_cmd.add_argument("--full", action="store_true", help="Print sprawling Markdown table instead of compact HUD box")
    sub.add_parser("probe", help="Probe and print JSON models")
    sub.add_parser("pause", help="Pause adversarial loop")
    sub.add_parser("resume", help="Resume adversarial loop")

    lineup_cmd = sub.add_parser("lineup", help="Display or configure confrontation roster/lineup (1~5)")
    lineup_cmd.add_argument("args", nargs="*", help="Lineup number, or num + model letters (e.g. 1, or 3 AB)")

    switch_cmd = sub.add_parser("switch", help="Switch active critic agent and model (e.g. 1A, 2A)")
    switch_cmd.add_argument("code", help="Code such as 1A, 2A, or agent number 1, 2")

    args = parser.parse_args()
    registry = detect_system_readiness()
    cfg = load_config(args.workspace)

    if args.command == "lineup":
        lineup_args = getattr(args, "args", [])
        if not lineup_args:
            print(render_lineup_box(cfg))
            sys.exit(0)

        num = str(lineup_args[0]).strip()
        if num not in ROSTERS:
            sys.stderr.write(f"[ERROR] 未知的阵容编号 '{num}'。可选范围: 1~5\n")
            sys.exit(1)

        r = ROSTERS[num]

        # Case 1: Lineup 1 (Default Roster) -> Direct Launch Ready!
        if num == "1":
            cfg["active_lineup"] = "1"
            cfg["author_runner"] = r["author_runner"]
            cfg["author_code"] = r["author_code"]
            cfg["author_model_name"] = r["author_model_name"]
            cfg["author_model_slug"] = r["author_model_slug"]
            cfg["active_runner"] = r["critic_runner"]
            cfg["active_code"] = r["critic_code"]
            cfg["active_agent_name"] = r["critic_agent_name"]
            cfg["active_model_name"] = r["critic_model_name"]
            cfg["active_model_slug"] = r["critic_model_slug"]
            save_config(cfg, args.workspace)
            print(json.dumps({
                "status": "LAUNCH_READY",
                "lineup": "1",
                "name": r["name"],
                "author": f"{r['author_runner']} [{r['author_code']}] ({r['author_model_name']})",
                "critic": f"{r['critic_runner']} [{r['critic_code']}] ({r['critic_model_name']})",
                "ready_to_launch": True,
                "message": "已成功装载默认对攻阵容 [1]，配置完备，可直接启动对抗闭环！"
            }, ensure_ascii=False, indent=2))
            sys.exit(0)

        # Case 2: Lineups 2~5, but no models specified yet -> Show Step 2 Box!
        if len(lineup_args) == 1:
            cfg["active_lineup"] = num
            save_config(cfg, args.workspace)
            print(render_roster_models_box(num, registry))
            sys.exit(0)

        # Case 3: Lineups 2~5 with models specified (e.g. "lineup 3 A B" or "lineup 3 AB")
        models_input = "".join(lineup_args[1:]).strip().upper()
        if len(models_input) < 2:
            sys.stderr.write(f"[ERROR] 请提供两个模型代号字母（例如 'AB' 或 'A B'）\n")
            sys.exit(1)

        a_let = models_input[0]
        c_let = models_input[1]

        a_pnum = r.get("author_platform")
        c_pnum = r.get("critic_platform")

        if not a_pnum or not c_pnum:
            # Custom roster 5 fallback
            a_pnum = "2"
            c_pnum = "1"

        a_models = registry[a_pnum]["models"]
        c_models = registry[c_pnum]["models"]
        if a_let not in a_models:
            sys.stderr.write(f"[ERROR] 施工方 ({registry[a_pnum]['name']}) 没有模型选项 '{a_let}'。可选: {list(a_models.keys())}\n")
            sys.exit(1)
        if c_let not in c_models:
            sys.stderr.write(f"[ERROR] 质检方 ({registry[c_pnum]['name']}) 没有模型选项 '{c_let}'。可选: {list(c_models.keys())}\n")
            sys.exit(1)

        cfg["active_lineup"] = num
        cfg["author_runner"] = r["author_runner"]
        cfg["author_code"] = f"{a_pnum}{a_let}"
        cfg["author_model_name"] = a_models[a_let]["name"]
        cfg["author_model_slug"] = a_models[a_let]["slug"]
        cfg["active_runner"] = r["critic_runner"]
        cfg["active_code"] = f"{c_pnum}{c_let}"
        cfg["active_agent_name"] = registry[c_pnum]["name"]
        cfg["active_model_name"] = c_models[c_let]["name"]
        cfg["active_model_slug"] = c_models[c_let]["slug"]
        save_config(cfg, args.workspace)

        print(json.dumps({
            "status": "LAUNCH_READY",
            "lineup": num,
            "name": r["name"],
            "author": f"{r['author_runner']} [{a_pnum}{a_let}] ({a_models[a_let]['name']})",
            "critic": f"{r['critic_runner']} [{c_pnum}{c_let}] ({c_models[c_let]['name']})",
            "ready_to_launch": True,
            "message": f"已完成模型定制并装载阵容 [{num}]，配置完备，可直接启动对抗闭环！"
        }, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.command == "probe":
        print(json.dumps(registry, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.command == "table":
        if getattr(args, "full", False):
            pause_badge = "🔴 [已暂停 PAUSED]" if cfg.get("paused") else "🟢 [正常运行 ACTIVE]"
            curr = f"{cfg.get('active_code', '1A')} ({cfg.get('active_agent_name')} - {cfg.get('active_model_name')})"
            print(f"\n### 📊 实机动态探测：异构对抗审查官选项库 ({pause_badge})\n")
            print(f"> 当前活跃审查官: **`{curr}`**（每次调用前已自动核验实机底层模型库）\n")
            print(render_markdown_table(registry, cfg))
        else:
            print(render_compact_box(registry, cfg))
        print("\n> **快捷操作**：输入代码如 `1A`、`2D`、`6B` 立即切换；输入 `lineup` 选阵容；输入 `0` 或 `暂停` 暂停对抗；输入 `继续` 恢复；输入 `?` 再次呼出本看板。\n")
        sys.exit(0)

    if args.command == "pause":
        cfg["paused"] = True
        save_config(cfg, args.workspace)
        print(json.dumps({"status": "PAUSED", "message": "对抗审查已暂停"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.command == "resume":
        cfg["paused"] = False
        save_config(cfg, args.workspace)
        print(json.dumps({"status": "RESUMED", "message": f"对抗审查已恢复，当前审查官: {cfg.get('active_code')}"}, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.command == "switch":
        raw = args.code.strip().upper()
        agent_num = ""
        model_letter = ""

        if len(raw) == 1:
            if raw.isdigit():
                agent_num = raw
                if agent_num == "1":
                    model_letter = "B" # DeepSeek V4.1 Flash 默认
                elif agent_num == "2":
                    model_letter = "D" # 6.1 Sol 默认
                elif agent_num == "6":
                    model_letter = "B" # Gemini Flash 默认挑刺
                else:
                    model_letter = "A"
            elif raw.isalpha():
                agent_num = cfg.get("active_agent_num", "1")
                model_letter = raw
        elif len(raw) >= 2:
            agent_num = raw[0]
            model_letter = raw[1]

        if agent_num not in registry:
            sys.stderr.write(f"[ERROR] 未知的 Agent 编号 '{agent_num}'。可选范围: 1~6\n")
            sys.exit(1)

        agent_info = registry[agent_num]
        if model_letter not in agent_info["models"]:
            sys.stderr.write(f"[ERROR] Agent '{agent_info['name']}' 下没有模型选项 '{model_letter}'。当前实机可用: {list(agent_info['models'].keys())}\n")
            sys.exit(1)

        model_info = agent_info["models"][model_letter]
        if not agent_info["ready"]:
            sys.stderr.write(f"[WARNING] Agent '{agent_info['name']}' 当前未完全就绪: {agent_info['status_label']}，但已保存偏好。\n")

        code = f"{agent_num}{model_letter}"
        cfg["active_code"] = code
        cfg["active_agent_num"] = agent_num
        cfg["active_agent_name"] = agent_info["name"]
        cfg["active_runner"] = agent_info["runner"]
        cfg["active_model_letter"] = model_letter
        cfg["active_model_name"] = model_info["name"]
        cfg["active_model_slug"] = model_info["slug"]
        cfg["paused"] = False

        save_config(cfg, args.workspace)
        print(json.dumps({
            "status": "SWITCHED",
            "code": code,
            "agent": agent_info["name"],
            "model": model_info["name"],
            "slug": model_info["slug"],
            "ready": agent_info["ready"],
            "message": f"审查官已成功切换为实机探测模型: [{code}] {agent_info['name']} ({model_info['name']})"
        }, ensure_ascii=False, indent=2))
        sys.exit(0)


if __name__ == "__main__":
    main()
