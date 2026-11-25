---
name: local-agent-delegate
displayName: E06 · 红蓝对抗闭环 v1.2.3
description: E06 · 红蓝对抗闭环 v1.2.3：【通用软件/App/工程代码专用】专职双脑红蓝对抗闭环器。日常单任务走 E07-派发，生信科研评审走 E02-生信三方评审；仅当软件/工程开发需要【蓝方施工 ⚔ 红方挑刺】多轮交叉审核与两阶段提交闭环时触发。默认 1 号阵容采用双周期异构王牌（9B Codex GPT-6.2 Sol ⚔ 4A Gemini 4 Neon High），Codex Free/耗尽时自动跨客户端两大内置共享池接力；按量 DeepSeek 永不自动调用；快捷口令 .?（面板）与 .s（状态）。
---

# E06 · 红蓝对抗闭环 v1.2.3

> **🎯 三大调度与评审 Skill 职责边界**：
> - **`E06-红蓝对抗闭环`（本 Skill）**：专用于**通用软件、App Vibe Coding（`C06`）、前后端架构与工程代码**的“蓝方施工 ⚔ 红方挑刺”多轮死磕与两阶段提交落盘。
> - **`E02-生信三方评审`**：专用于**单细胞注释（`A02`/`A03`）、生信 SOP（`A01~A07`）与科研图表（`B01~B07`）**的红蓝绿三方专家评审。
> - **`E07-派发`**：专用于**日常单任务或多任务并发三级阶梯派发**与跨池额度接力。

`SKILL_DIR` = `C:\Users\fight\.gemini\config\skills\E06-红蓝对抗闭环`  
`<python>` = `C:\Users\fight\.codex\cache\ngs-analysis-workbench\venvs\0.2.10\Scripts\python.exe`

## 一、 全局统一三级阶梯模型代号（与 E07 100% 共用）

- **`[9]` 🥇 Tier 1 · Codex 周期订阅池**：`9A` GPT-6.2 Astra（旗舰架构）│ `9B` GPT-6.2 Sol（主力蓝方）│ `9C` GPT-6.1 Terra（视觉UI）│ `9D` GPT-6 Luna（轻量）
- **`[1]~[4]` 🥈 Tier 2 · 客户端两大共享池**：`gemini_shared`（含 Carbon、Neon、Hydrogen、Argon、3.8 Flash 与 Orchestrator）和 `claude_shared`（Claude Opus/Sonnet、GPT-OSS 120B）。以实时 `quotas` 为准；同池别名不能互保，耗尽时只跨池接力。
- **`[8]` 🥉 Tier 3 · DeepSeek 官方 API 按量咨询席**：`8A` DeepSeek-V4-Pro (`deepseek-v4-pro`)，`8B` DeepSeek-V4.1-Flash (`deepseek-flash`)。默认 `deepseek-official`，用 dsh `--patch` 切模，永不自动调用；仅前两级异常时核实费率及当前是否半价，并先取得用户确认。

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
│       [8] 按量外援对攻     : [9B/2A] 蓝方施工       ⚔ [8A] DeepSeek-V4-Pro 按量   │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 快捷口令: [1/2/3]免费阵容 │ [8]问后按量 │ [0]暂停 │ [.s/状态] │ [.?/面板]  │
└────────────────────────────────────────────────────────────────────────────┘
```

> **唯一焦点锁与零撞车铁律**：处于 `E06-红蓝对抗闭环` 时输入 `.?` 仅呼出本看板；所有裸字母 `A/B/C/D` 与数字 `1~9` 仅归选择题使用，严禁拦截裸 `b/d/r/u/g/s`。

## 三、 任务确认门禁 & 多轮对攻执行

1. 仅审查或讨论时直接只读执行。任务涉及修改 Skill、代码或规则时，先在对话中说明拟改范围、改法和验收条件，待用户明确同意该方案后，再启动写入或派发施工。用户已明确指定并授权同一方案时直接执行。选阵容只确认模型选择。已批准范围内的红蓝返修连续进行，仅在实质扩大范围或改变已约定行为时重新确认。
2. 阵容 `[1]`/`[3]` 中 Codex 蓝方经 `run_local.py` / `delegate.py` 调用（自动感知 `models_cache.json` Free/耗尽并退回内置池），内置方走原生 `swarm`；阵容 `[8]` 需用户确认并加 `--user-confirmed`。

```powershell
& <python> "$SKILL_DIR\scripts\critic_manager.py" lineup 1
& <python> "$SKILL_DIR\scripts\critic_manager.py" switch 4A
& <python> "$SKILL_DIR\scripts\adversarial_loop.py" --task "任务目标" --file ".swarm/draft.py" --output "src/final.py" --dry-run
```
