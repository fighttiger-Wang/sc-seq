---
name: local-agent-delegate
displayName: E06 · 红蓝对抗闭环 v1.1.0
description: E06 · 红蓝对抗闭环 v1.1.0：【通用软件/App/工程代码专用】专职双脑红蓝对抗闭环器。日常单任务走 E07-派发，生信科研评审走 E02-生信三方评审；仅当软件/工程开发需要【蓝方施工 ⚔ 红方挑刺】多轮交叉审核与两阶段提交闭环时触发。默认 1 号阵容采用客户端内置 0 额外付费异构王牌（2A Claude Sonnet 5.5 ⚔ 4A Gemini 4 Neon High），支持额度耗尽自动接力；快捷口令统一采用 .?（面板）与 .s（状态）。
---

# E06 · 红蓝对抗闭环 v1.1.0

> **🎯 三大调度与评审 Skill 职责边界**：
> - **`E06-红蓝对抗闭环`（本 Skill）**：专用于**通用软件、App Vibe Coding（`C06`）、前后端架构与工程代码**的“蓝方施工 ⚔ 红方挑刺”多轮死磕与两阶段提交落盘（直至 `[STATUS: APPROVED]` 且真实 Exit Code `0`）。
> - **`E02-生信三方评审`**：专用于**单细胞注释（`A02`/`A03`）、生信 SOP（`A01~A07`）与科研图表（`B01~B07`）**的红蓝绿三方专家评审。
> - **`E07-派发`**：专用于**日常单任务或多任务并发智能工种派发**与额度自动接力。

`SKILL_DIR` = `C:\Users\fight\.gemini\config\skills\E06-红蓝对抗闭环`  
`<python>` = `C:\Users\fight\.codex\cache\ngs-analysis-workbench\venvs\0.2.10\Scripts\python.exe`

## 一、 全局统一模型代号矩阵（与 E07 100% 共用）

- **`[1]` ⚡ 极速跑腿池 (内置免费)**：`1A` = Gemini 3.8 Flash │ `1B` = Gemini 4 Hydrogen Low │ `1C` = GPT-OSS 120B
- **`[2]` 💻 写代码工匠池 (内置免费)**：`2A` = Claude Sonnet 5.5 *(蓝方首选)* │ `2B` = Gemini 4 Hydrogen
- **`[3]` 🏗️ 统筹与架构池 (内置免费)**：`3A` = Gemini 4 Argon *(架构首选)* │ `3B` = Claude Opus 5.5
- **`[4]` 🔍 深度挑刺推理池 (内置免费)**：`4A` = Gemini 4 Neon High/XHigh *(红方首选)*
- **`[8]` 💰 付费外援 · DeepSeek (非默认)**：`8A` = DeepSeek-R1/Reasoner │ `8B` = DeepSeek-V3/Chat
- **`[9]` 💰 付费外援 · OpenAI Codex (非默认)**：`9A` = Codex 6.2 Sol (`gpt-6.2-sol`) │ `9B` = Codex 6.1 Sol (`gpt-6.1-sol`)

## 二、 红蓝对攻阵容速选看板（输入 `.?` 或 `面板` / `lineup` 秒呼出）

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E06 · 红蓝对抗闭环 v1.1.0 · 阶段 1/4: 对攻阵容速选]    │
│    [▶ 1.选对攻阵容] ➔ [2.定制/确认任务] ➔ [3.多轮红蓝死磕] ➔ [4.两相提交]  │
├────────────────────────────────────────────────────────────────────────────┤
│ 💡 客户端内置 0 额外付费异构对攻席（支持额度耗尽自动顺延接力）:            │
│    👉★[1] 默认内置王牌异构对攻 : [2A] Claude Sonnet 5.5 ⚔ [4A] Gemini 4 Neon High │
│           (额度耗尽自动接力链  : [2B] Gemini 4 Hydrogen ⚔ [3B] Opus 5.5 / [3A] Argon)│
│       [2] 内置架构统筹对攻     : [3A] Gemini 4 Argon    ⚔ [3B] Claude Opus 5.5    │
│       [3] 内置极速敏捷对攻     : [2B] Gemini 4 Hydrogen ⚔ [1A] Gemini 3.8 Flash   │
│ 💰 外部付费外援对攻席（🔒非默认！需消耗外部 API，仅手动选 8 或 9 启用）:   │
│       [8] 半托管外援对攻       : [2A] 内置 Sonnet/Gemini ⚔ [8A] 付费 DeepSeek-R1   │
│       [9] 经典全外援付费对攻   : [9A/9B] 付费 Codex Sol  ⚔ [8A/8B] 付费 DeepSeek   │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 快捷口令: [1/2/3]内置阵容 │ [8/9]外援阵容 │ [0]暂停 │ [.s/状态]进度额度 │ [.?/面板]看板 │
└────────────────────────────────────────────────────────────────────────────┘
```

> **唯一焦点锁与零撞车铁律**：当处于 `E06-红蓝对抗闭环` 流程中时，输入 `.?`（或 `面板`）仅呼出本 E06 对攻看板；所有裸单字母 `A/B/C/D` 与裸数字 `1~9` 100% 归当前面板选择题使用，严禁拦截裸单字母 `b / d / r / u / g / s`。

## 三、 任务确认门禁 & 多轮自治对攻闭环

1. **前置确认门禁**：选定阵容后展示【蓝方 ⚔ 红方】模型及替补链，由用户确认任务后推入后台并立即释放输入框。
2. **原生 Swarm / 外部 CLI 双模驱动**：
   - **阵容 `[1]~[3]`（内置 0 额外付费）**：通过原生 `swarm` 拉起蓝方 `author` 与红方 `critic`，遇额度耗尽自动调用 `swarm(action="model")` 顺延接力。
   - **阵容 `[8]~[9]`（显式付费外援）**：通过 `scripts/adversarial_loop.py` 驱动 `delegate.py` 多轮反例挑刺与两阶段提交。

```powershell
& <python> "$SKILL_DIR\scripts\critic_manager.py" lineup 1
& <python> "$SKILL_DIR\scripts\critic_manager.py" switch 4A
& <python> "$SKILL_DIR\scripts\adversarial_loop.py" --task "任务目标" --file ".swarm/draft.py" --output "src/final.py" --max-rounds 3
```
