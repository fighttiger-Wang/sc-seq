---
name: local-agent-delegate
displayName: E06 · 双脑红蓝对抗闭环 v1.0.0
description: "E06 · 本机智能体委托 v1.0.0（专职双脑红蓝对抗闭环器）：日常单任务走 E07；仅当需要【蓝方施工 ⚔ 红方挑刺】多轮交叉审核与两阶段提交闭环时触发。默认 1 号阵容采用客户端内置 0 额外付费异构王牌（2A Claude Sonnet 5.5 ⚔ 4A Gemini 4 Neon High），支持额度耗尽自动接力；付费外援阵容（8/9 DeepSeek/Codex）退居手动选配席，代号与 E07 100% 统一。"
license: MIT
metadata:
  version: "1.0.0"
---

# E06 · 专职双脑红蓝对抗闭环器 v1.0.0

> **职责边界**：日常单任务或并发派发走 `E07-派发`；**仅当需要“蓝方施工 ⚔ 红方挑刺”多轮死磕、直至 `[STATUS: APPROVED]` 才两阶段提交落盘时触发 E06**。

`SKILL_DIR` = `C:\Users\fight\.gemini\config\skills\E06-本机智能体委托`  
`<python>` = `C:\Users\fight\.codex\cache\ngs-analysis-workbench\venvs\0.2.10\Scripts\python.exe`

## 一、 全局统一模型代号矩阵（与 E07 100% 共用）

- **`[1]` ⚡ 极速跑腿池 (内置免费)**：`1A` = Gemini 3.8 Flash │ `1B` = Gemini 4 Hydrogen Low │ `1C` = GPT-OSS 120B
- **`[2]` 💻 写代码工匠池 (内置免费)**：`2A` = Claude Sonnet 5.5 *(蓝方首选)* │ `2B` = Gemini 4 Hydrogen
- **`[3]` 🏗️ 统筹与架构池 (内置免费)**：`3A` = Gemini 4 Argon *(架构首选)* │ `3B` = Claude Opus 5.5
- **`[4]` 🔍 深度挑刺推理池 (内置免费)**：`4A` = Gemini 4 Neon High/XHigh *(红方首选)*
- **`[8]` 💰 付费外援 · DeepSeek (非默认)**：`8A` = DeepSeek-R1/Reasoner │ `8B` = DeepSeek-V3/Chat
- **`[9]` 💰 付费外援 · OpenAI Codex (非默认)**：`9A` = Codex 6.2 Sol (`gpt-6.2-sol`) │ `9B` = Codex 6.1 Sol (`gpt-6.1-sol`)

## 二、 红蓝对攻阵容速选看板（输入 `lineup` 或 `?` 秒呼出）

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E06 v1.0.0 · 阶段 1/4: 红蓝双脑对攻阵容速选]           │
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
│ ⌨️ 快捷键: [1/2/3]内置阵容 │ [8/9]外援阵容 │ [0]暂停 │ [r]刷新 │ [?]看板   │
└────────────────────────────────────────────────────────────────────────────┘
```

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
