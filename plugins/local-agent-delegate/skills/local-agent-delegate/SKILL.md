---
name: local-agent-delegate
displayName: E06 · 红蓝对抗闭环 v1.2.0
description: E06 · 红蓝对抗闭环 v1.2.0：【通用软件/App/工程代码专用】专职双脑红蓝对抗闭环器。日常单任务走 E07-派发，生信科研评审走 E02-生信三方评审；仅当软件/工程开发需要【蓝方施工 ⚔ 红方挑刺】多轮交叉审核与两阶段提交闭环时触发。默认 1 号阵容采用双周期异构王牌（9B Codex GPT-6.2 Sol ⚔ 4A Gemini 4 Neon High），Codex Free/耗尽时自动跨客户端三大内置池接力；按量 DeepSeek 永不自动调用；快捷口令 .?（面板）与 .s（状态）。
---

# E06 · 红蓝对抗闭环 v1.2.0

> **🎯 三大调度与评审 Skill 职责边界**：
> - **`E06-红蓝对抗闭环`（本 Skill）**：专用于**通用软件、App Vibe Coding（`C06`）、前后端架构与工程代码**的“蓝方施工 ⚔ 红方挑刺”多轮死磕与两阶段提交落盘。
> - **`E02-生信三方评审`**：专用于**单细胞注释（`A02`/`A03`）、生信 SOP（`A01~A07`）与科研图表（`B01~B07`）**的红蓝绿三方专家评审。
> - **`E07-派发`**：专用于**日常单任务或多任务并发三级阶梯派发**与跨池额度接力。

`SKILL_DIR` = `C:\Users\fight\.gemini\config\skills\E06-红蓝对抗闭环`  
`<python>` = `C:\Users\fight\.codex\cache\ngs-analysis-workbench\venvs\0.2.10\Scripts\python.exe`

## 一、 全局统一三级阶梯模型代号（与 E07 100% 共用）

- **`[9]` 🥇 Tier 1 · Codex 周期订阅池**：`9A` GPT-6.2 Astra（旗舰架构）│ `9B` GPT-6.2 Sol（主力蓝方）│ `9C` GPT-6.1 Terra（视觉UI）│ `9D` GPT-6 Luna（轻量）
- **`[1]~[4]` 🥈 Tier 2 · 客户端内置三大独立池（跨池接力）**：
  - `[1]` ⚡ 极速跑腿：`1A` 3.8 Flash *(Neon)* ➔ `1B` Hydrogen Low *(Neon)* ➔ `1C` Sonnet Low *(Claude)*
  - `[2]` 💻 写代码：`2A` Sonnet 5.5 *(Claude)* ➔ `2B` Hydrogen *(Neon)* ➔ `3A` Argon *(Argon周池)*
  - `[3]` 🏗️ 统筹架构：`3A` Argon *(Argon周池)* ➔ `3B` Opus 5.5 *(Claude)* ➔ `3C` Orch(Neon) *(Neon)*
  - `[4]` 🔍 深度挑刺：`4A` Neon High *(Neon)* ➔ `3B` Opus High *(Claude)* ➔ `3A` Argon High *(Argon)*
- **`[8]` 🥉 Tier 3 · DeepSeek 按量咨询席（永不自动调用）**：`8A` DeepSeek-R1 │ `8B` DeepSeek-V3（仅前两级异常且先询问用户确认后启用，附 `00:30–08:30` 半价提示）

## 二、 红蓝对攻阵容速选看板（输入 `.?` 或 `面板` / `lineup` 秒呼出）

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E06 · 红蓝对抗闭环 · 阶段 1/4: 对攻阵容速选]           │
│    [▶ 1.选对攻阵容] ➔ [2.定制/确认任务] ➔ [3.多轮红蓝死磕] ➔ [4.两相提交]  │
├────────────────────────────────────────────────────────────────────────────┤
│ 💡 周期/内置免费异构对攻席（支持跨池接力，0 按量扣费）:                    │
│    👉★[1] 双周期异构王牌   : [9B] Codex GPT-6.2 Sol ⚔ [4A] Gemini 4 Neon High │
│           (Codex Free/耗尽 : 蓝方自动退回 [2A] Sonnet 5.5 / [2B] Hydrogen)    │
│       [2] 客户端纯内置异构 : [2A] Claude Sonnet 5.5 ⚔ [4A] Gemini 4 Neon High │
│       [3] 顶级架构统筹对攻 : [9A] Codex GPT-6.2 Astra ⚔ [3B] Opus / [4A] Neon │
│ 💰 按量付费咨询席（🔒永不自动调！仅前两级异常且询问确认后才启用）:         │
│       [8] 按量外援对攻     : [9B/2A] 蓝方施工       ⚔ [8A] DeepSeek-R1 按量   │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 快捷口令: [1/2/3]免费阵容 │ [8]问后按量 │ [0]暂停 │ [.s/状态] │ [.?/面板]  │
└────────────────────────────────────────────────────────────────────────────┘
```

> **唯一焦点锁与零撞车铁律**：处于 `E06-红蓝对抗闭环` 时输入 `.?` 仅呼出本看板；所有裸字母 `A/B/C/D` 与数字 `1~9` 仅归选择题使用，严禁拦截裸 `b/d/r/u/g/s`。

## 三、 任务确认门禁 & 多轮对攻执行

1. 选定阵容后展示【蓝方 ⚔ 红方】模型及跨池接力链，由用户确认任务后推入后台并立即释放输入框。
2. 阵容 `[1]`/`[3]` 中 Codex 蓝方经 `run_local.py` / `delegate.py` 调用（自动感知 `models_cache.json` Free/耗尽并退回内置池），内置方走原生 `swarm`；阵容 `[8]` 需用户确认并加 `--user-confirmed`。

```powershell
& <python> "$SKILL_DIR\scripts\critic_manager.py" lineup 1
& <python> "$SKILL_DIR\scripts\critic_manager.py" switch 4A
& <python> "$SKILL_DIR\scripts\adversarial_loop.py" --task "任务目标" --file ".swarm/draft.py" --output "src/final.py" --dry-run
```
