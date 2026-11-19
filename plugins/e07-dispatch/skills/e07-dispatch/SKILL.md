---
name: e07-dispatch
displayName: E07 · 派发 v1.0.0
description: "E07 · 派发 v1.0.0：日常单轨/多轨智能工种派发与额度接力中心。默认 100% 优先按工种匹配客户端内置免费模型（1A极速跑腿/2A写代码工匠/3A统筹架构/4A深度挑刺），配额耗尽自动沿替补链顺延接力；付费外援（8A/8B DeepSeek、9A/9B Codex）非默认锁定，仅显式点名调用。"
metadata:
  version: "1.0.0"
---

# E07 · 派发 v1.0.0（工种分工 + 额度自动接力 + 付费外援锁定）

`SKILL_DIR` = `C:\Users\fight\.gemini\config\skills\E07-派发`  
`<python>` = `C:\Users\fight\.codex\cache\ngs-analysis-workbench\venvs\0.2.10\Scripts\python.exe`

## 一、 核心调度契约

1. **轻重分流 & 默认 0 额外付费**：`<=3步/10秒内` 的小事主会话秒办；重任务通过 E07 按工种派入后台并立即 End Turn。默认 100% 走内置免费池 (`1A~4A`)。
2. **四大内置工种与额度自动接力链（Quota Fallback Chain）**：
   - 通过 `swarm(action="models", all=true)` 查 `quotas`；若首选额度耗尽，自动沿替补链顺延：
   - **`[1]` ⚡ 极速跑腿池**：`1A` Gemini 3.8 Flash *(默认)* ➔ `1B` Gemini 4 Hydrogen Low ➔ `1C` GPT-OSS 120B
   - **`[2]` 💻 写代码工匠池**：`2A` Claude Sonnet 5.5 *(编码首选)* ➔ `2B` Gemini 4 Hydrogen ➔ `3A` Argon ➔ `1C` GPT-OSS
   - **`[3]` 🏗️ 统筹与架构池**：`3A` Gemini 4 Argon *(周大池首选)* ➔ `3B` Claude Opus 5.5 ➔ Orchestrator
   - **`[4]` 🔍 深度挑刺推理池**：`4A` Gemini 4 Neon High/XHigh *(挑刺首选)* ➔ `3B` Opus 5.5 ➔ `3A` Argon High
3. **付费外援显式门禁（`8`/`9` 非默认席）**：
   - **`[8]` 💰 DeepSeek (`dsh`)**：`8A` = DeepSeek-R1/Reasoner │ `8B` = DeepSeek-V3/Chat
   - **`[9]` 💰 OpenAI Codex (`codex`)**：`9A` = Codex 6.2 Sol (`gpt-6.2-sol`) │ `9B` = Codex 6.1 Sol (`gpt-6.1-sol`)
   - 仅当显式输入 `8A/8B/9A/9B` 时调用本目录 `scripts/delegate.py`（已内置 `<2KB` `models_fast_cache.json` 并砍除 2.41s `dsh --help` 探活）。

## 二、 工种分工 + 额度状态 + 免费/付费分区 HUD 看板（输入 `?` 秒呼出）

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E07 · 智能工种派发与额度自动接力中心 v1.0.0]           │
├────────────────────────────────────────────────────────────────────────────┤
│ 💡 内置免费主力池（0 额外付费 · 支持同工种额度耗尽自动降级接力）:          │
│    👉★[1] ⚡ 极速跑腿池 ── [1A] Gemini 3.8 Flash (94%) ➔ [1B] Hydrogen Low ➔ [1C] GPT-OSS│
│    👉★[2] 💻 写代码工匠 ── [2A] Claude Sonnet 5.5 (34%) ➔ [2B] Gemini 4 Hydrogen (94%)  │
│    👉★[3] 🏗️ 统筹架构师 ── [3A] Gemini 4 Argon (66%周池) ➔ [3B] Claude Opus 5.5 (34%)   │
│    👉★[4] 🔍 深度挑刺池 ── [4A] Gemini 4 Neon High (94%) ➔ [3B] Opus 5.5 ➔ [3A] Argon   │
│ 💰 外部付费外援席（🔒非默认！仅显式输入 8A/8B/9A/9B 点名时调用）:          │
│       [8] DeepSeek CLI ── [8A] DeepSeek-R1/Reasoner   │ [8B] DeepSeek-V3/Chat          │
│       [9] Codex CLI    ── [9A] Codex 6.2 Sol (旗舰)   │ [9B] Codex 6.1 Sol (稳健)      │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 快捷键（E06/E07 统一）: [1A]~[4A]内置 │ [8A/8B/9A/9B]外援 │ [s/c/r/?]   │
└────────────────────────────────────────────────────────────────────────────┘
```

## 三、 命令速查

```powershell
& <python> "$SKILL_DIR\scripts\parallel_dispatch.py" hud
& <python> "$SKILL_DIR\scripts\parallel_dispatch.py" dispatch --choice 2A --prompt "重构" --exhausted "claude-sonnet-5-5-high,claude-sonnet-5-5-medium"
& <python> "$SKILL_DIR\scripts\parallel_dispatch.py" dispatch --choice 8A --prompt "审计" --dry-run
```
