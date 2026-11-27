---
name: e07-dispatch
displayName: E07 · 派发 v1.2.3
description: E07 · 派发 v1.2.3：Gemini 4 Neon Medium 前台省电遥控，后台优先用 Codex 5h 池派发注释、Skill 维护及 Lucky Note App 大任务；客户端两共享池接力；DeepSeek 官方 API 按量先问。支持模型变化雷达及 .? / .s。
---

# E07 · 派发 v1.2.3

## 前台省电，后台精准派单

固定用 **Gemini 4 Neon Medium** 做前台遥控器：只做意图对齐、轻量直办、本端专属工具与验收；后台重活优先派 **Codex 5h 滚动池**，保护前台 Gemini 配额。`routing_policy.json` 是岗位选择和业务规则的唯一策略表。

- **A02/A03 注释**：A02/A03 均不在前台读原始大表，直接传文件路径；A02 用主力 `9B` 中档，A03 默认用主力 `9B` 高档跑全场（1x 成本 / 500K 窗口），仅将少数争议亚群的小切片交旗舰 `9A` 中档点穴终审。**不修改 A02/A03 技能**。
- **Skill 维护**：精准限定目标目录，常规脚本改动派主力中档，跨 Skill 架构或协议改造派旗舰中档。
- **Lucky Note App**：单文件 ≤50 行微调和浏览器预览留前台；>50 行或多文件改造拆单派 Codex，完工后回前台浏览器验收。
- **熔断与验收**：两轮无进展即熔断，物理终止原进程并保留失败路径与证据，再升级档位或换厂商。超过 180 秒先抽检日志、差异或中间产物，不凭口头宣称继续空等。完成须核对可验证证据。

## 三级额度路由

- **Tier 1：Codex 订阅**。`9A` 旗舰、`9B` 主力、`9C` 视觉、`9D` 批量；从本机 `~/.codex/models_cache.json` 按系列和版本解析可见模型，不写死版本。Free/冷却/岗位不可用时转 Tier 2。
- **Tier 2：客户端两大共享池**。`gemini_shared` 覆盖 Carbon、Neon、Hydrogen、Argon、3.8 Flash 和 Orchestrator；`claude_shared` 覆盖 Claude Opus/Sonnet 和 GPT-OSS 120B。以客户端实时 `quotas` 为准；同池别名不是跨池替补。`1A/1B/2B/3A/3C/4A` 属 Gemini，`1C/2A/3B` 属 Claude+GPT-OSS。
- **Tier 3：官方 API 按量先问**。`8A` DeepSeek-V4-Pro (`deepseek-v4-pro`)，`8B` DeepSeek-V4.1-Flash (`deepseek-flash`)，默认 `deepseek-official`，DSH 切模统一用 `--profile headless --patch <tmp.yml>`，禁用 `-m`。不得默认或自动兜底；仅前两级异常或明显退化时核实当前适用费率及半价时段（未核实或遇法定节假日未覆盖时标“待核实”，不直接断言原价或半价）、取得用户明确同意后加 `--user-confirmed` 调用；用户显式点名 `8A/8B` 可直接执行（落入工作日高峰原价时段时先提醒一次）。

## 看板与雷达

`.?` / `面板` / `选模` 呼出当前焦点看板，`.s` / `状态` 看后台进度和实时额度；E06 或 C06 当值时只响应当前焦点。裸字母和数字只用于答选择题。通用软件红蓝闭环用 E06，生信三方评审用 E02。

从本技能的 `scripts/` 目录运行：

```text
python parallel_dispatch.py hud
python parallel_dispatch.py dispatch --choice 9B --prompt "重构" --dry-run
python parallel_dispatch.py dispatch --choice 8A --prompt "审计" --user-confirmed --dry-run
python model_radar.py
python parallel_dispatch.py radar --json --no-save --native-models-json <path>
```

`model_radar.py` 对比上次基线，报告上下架、档位变化、14 天内计划下线及超过 30 天未复核的半价规则。默认基线位于 `~/.gemini/antigravity/scratch/e07_tasks/radar_snapshot.json`；`--quiet-if-unchanged` 无变化静默；`--no-save` 只读。
