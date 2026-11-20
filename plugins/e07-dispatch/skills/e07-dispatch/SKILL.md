---
name: e07-dispatch
displayName: E07 · 派发 v1.2.1
description: E07 · 派发 v1.2.1：三级阶梯智能工种派发与跨池额度接力中心。独立重型任务优先吃满周期订阅 OpenAI Codex（9A Astra/9B Sol/9C Terra/9D Luna）；Codex Free/耗尽及本端专属工具任务自动切回客户端三大独立内置池（Neon/Claude/Argon）跨池接力；DeepSeek 按量付费（8A/8B）永不自动调用，仅异常/降智时先征询并提示半价时段；快捷口令 .?（面板/选模）与 .s（状态）。
---

# E07 · 派发 v1.2.1

`SKILL_DIR` = `C:\Users\fight\.gemini\config\skills\E07-派发`  
`<python>` = `C:\Users\fight\.codex\cache\ngs-analysis-workbench\venvs\0.2.10\Scripts\python.exe`

## 一、 核心调度契约与职责边界

1. **职责边界**：
   - **`E07-派发`（本 Skill）**：日常单轨/多轨三级阶梯派发与跨池额度接力（输入 `.?` 或 `面板`/`选模` 默认呼出）。
   - **`E06-红蓝对抗闭环`**：通用软件/App 代码双脑死磕（默认 `9B Codex GPT-6.2 Sol ⚔ 4A Gemini 4 Neon High`）。
   - **`E02-生信三方评审`**：单细胞注释与生信 SOP 红蓝绿三方专家评审。
2. **轻重分流 & 本端工具保留**：`≤ 3 步/10 秒` 小事主会话秒办；需本端专属工具（内置浏览器/3D 分子/交互 Swarm）的任务留内置池；独立重型后台任务优先走 **Tier 1 Codex 周期订阅**。
3. **三级阶梯模型池与跨池接力链**：
   - **🥇 Tier 1 · Codex 周期订阅优先池 `[9]`**：`9A` GPT-6.2 Astra（旗舰架构/深审）、`9B` GPT-6.2 Sol（主力编码）、`9C` GPT-6.1 Terra（视觉/UI审查）、`9D` GPT-6 Luna（轻量批量）。自动校验 `models_cache.json` 与冷却状态，处于 Free 受限或触发 `429` 时自动转入 Tier 2。
   - **🥈 Tier 2 · 客户端三大独立内置池 `[1]~[4]`**（同池共享额度，**严禁同池互为保底**，耗尽时跨池顺延）：
     - **Neon 5h 池**：`Orchestrator (Neon)`、`Gemini 4 Neon`、`Gemini 4 Hydrogen`、`Gemini 3.8 Flash`
     - **Claude 5h 池**：`Claude Opus 5.5`、`Claude Sonnet 5.5`、`GPT-OSS 120B`
     - **Argon 周池**：`Gemini 4 Argon`、`Orchestrator (Argon)`
     - **`[1]` ⚡ 极速跑腿**：`1A` 3.8 Flash *(Neon)* ➔ `1B` Hydrogen Low *(Neon)* ➔ `1C` Sonnet Low *(Claude)*
     - **`[2]` 💻 写代码**：`2A` Sonnet 5.5 *(Claude)* ➔ `2B` Hydrogen *(Neon)* ➔ `3A` Argon *(Argon)*
     - **`[3]` 🏗️ 统筹架构**：`3A` Argon *(Argon)* ➔ `3B` Opus 5.5 *(Claude)* ➔ `3C` Orch(Neon) *(Neon)*
     - **`[4]` 🔍 深度挑刺**：`4A` Neon High *(Neon)* ➔ `3B` Opus High *(Claude)* ➔ `3A` Argon High *(Argon)*
   - **🥉 Tier 3 · DeepSeek 按量咨询席 `[8]`（永不自动调用）**：`8A` DeepSeek-R1/Reasoner │ `8B` DeepSeek-V3/Chat。仅在前两级不可用或明显性能下降时，**先向用户确认并提示当前是否处于空闲半价时段**（空闲半价时段为除工作日周一至周五不含中国法定节假日 `09:00–12:00`、`14:00–18:00` 高峰期外的全部时段，含周末及法定节假日全天；加 `--user-confirmed` 启动）。

## 二、 三级阶梯派发 HUD 看板（输入 `.?` 或 `面板`/`选模` 秒呼出）

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 📍 流水线全景进度: [E07 · 三级阶梯派发与跨池接力中心]                       │
├────────────────────────────────────────────────────────────────────────────┤
│ 🥇 Tier 1 · Codex 周期订阅池（独立重型后台首选，Free/耗尽自动退 Tier 2）:  │
│    👉★[9B] GPT-6.2 Sol (主力编码) │ [9A] GPT-6.2 Astra (旗舰架构/深审)     │
│       [9C] GPT-6.1 Terra (视觉UI) │ [9D] GPT-6 Luna (轻量高速批量)         │
│ 🥈 Tier 2 · 客户端三大独立内置池（支持跨池自动接力）:                      │
│       [1] ⚡ 极速跑腿: [1A] 3.8 Flash(Neon) ➔ [1B] Hydrogen Low ➔ [1C] Sonnet Low│
│       [2] 💻 写代码池: [2A] Sonnet 5.5(Claude) ➔ [2B] Hydrogen(Neon) ➔ [3A] Argon│
│       [3] 🏗️ 统筹架构: [3A] Argon(周池) ➔ [3B] Opus 5.5(Claude) ➔ [3C] Orch(Neon)│
│       [4] 🔍 深度挑刺: [4A] Neon High(Neon) ➔ [3B] Opus High ➔ [3A] Argon High   │
│ 🥉 Tier 3 · DeepSeek 按量付费咨询席（🔒永不自动调，非工作日09-12/14-18均半价）: │
│       [8A] DeepSeek-R1/Reasoner   │ [8B] DeepSeek-V3/Chat                  │
├────────────────────────────────────────────────────────────────────────────┤
│ ⌨️ 快捷口令: [9A~9D]Codex │ [1A~4A]内置 │ [8A/8B]问后按量 │ [.s/状态] │ [.?/面板]│
└────────────────────────────────────────────────────────────────────────────┘
```

> **零撞车铁律**：所有裸单字母 `A/B/C/D` 与裸数字 `1~9` 100% 归当前面板选择题使用，严禁拦截裸单字母 `b / d / r / u / g / s`！

## 三、 命令速查

```powershell
& <python> "$SKILL_DIR\scripts\parallel_dispatch.py" hud
& <python> "$SKILL_DIR\scripts\parallel_dispatch.py" dispatch --choice 9B --prompt "重构" --dry-run
& <python> "$SKILL_DIR\scripts\parallel_dispatch.py" dispatch --choice 9B --prompt "回退测试" --exhausted "codex,claude-sonnet-5-5-medium"
& <python> "$SKILL_DIR\scripts\parallel_dispatch.py" dispatch --choice 8A --prompt "审计" --dry-run
```
