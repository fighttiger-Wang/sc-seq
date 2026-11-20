---
name: task-handoff
displayName: E01 · 任务交接 v0.3.0
description: E01 · 任务交接 v0.3.0：自动续接并维护中央交接记录 Maintain centralized, cross-session continuity records for named projects, software, codebases, and skills. Trigger updates ONLY upon major milestone completion, explicit task blocking/pausing, or explicit user request ("写交接"/"先停下"/"接着上次"); skip automatic handoff script calls during routine single-step micro-adjustments to keep responses fast.
---

# E01 · 任务交接 v0.3.0

维护位于 `<shared-workspace-root>\.codex-handoff` 的唯一中央交接库（通过 `CODEX_SHARED_WORKSPACE_ROOT` 或 `~/.codex/workspace-local.json` 解析，严禁在项目根目录散落新建 `HANDOFF.md` 或在插件缓存目录分裂建库）。

跨平台统一入口（Windows / macOS / Linux）：

```bash
python scripts/handoff_store.py <command> <arguments>
```

进阶迁移、合并与存储结构说明按需查阅 [store-format.md](references/store-format.md)。

## 一、 续接与启动规程 (Start or Resume)

1. **识别稳定实体**：仅针对具名项目（Project）、软件产品（Software）、代码库（Codebase）或技能（Skill）建立交接，忽略一次性匿名问答。
2. **精准解析实体**：当用户表达“接着上次”、“继续迭代”、“又发现问题”时，依次按显式名称、别名、Skill ID 与绝对路径锚点检索：
   ```bash
   python scripts/handoff_store.py resolve --query '<name-or-path>'
   ```
3. **防串台铁律**：若返回多个候选或无精确匹配，**必须暂停询问用户**，严禁盲猜或将测试草稿工程（如 `L_app`）串台混入正式生产工程（如 `Lucky Note`）。
4. **以真实文件为准**：匹配唯一实体后运行 `show` 读取 `CURRENT.md` 并记录 `currentRevision`（提交时作为 `--expected-revision`），同时必须核对真实代码库现状，不盲信过期记录。

## 二、 交接更新触发边界（告别单步微调拖慢收尾）

> **核心提速铁律**：**日常单步微调、普通问答、局部样式小修、轻量状态查询或讨论规划，严禁自动跑交接脚本拖慢对话收尾！**

**仅在满足以下 3 类条件之一时，才在最终回复前执行 1 次交接更新**：
1. 🏆 **重大阶段完工（Major Milestone Completed）**：完成完整功能模块交付、正式版本发布、全流程生信注释交付或大型架构重构；
2. 🛑 **任务明确阻塞或暂停（Explicitly Blocked / Paused）**：遇到需外部依赖/数据的硬阻塞，或测试失败留有高价值排障证据；
3. 🗣️ **用户主动指令（Explicit User Trigger）**：用户明确提及“写交接”、“保存进度”、“先停下”、“做个快照/checkpoint”或“接着上次”。

## 三、 标准交接记录格式与提交

更新时编写精炼的 UTF-8（无 BOM）Markdown 草稿，严格包含以下 5 个二级标题：

```markdown
# <canonical name> continuity

> Status: completed | failed | blocked | paused | in-progress
> Updated: <YYYY-MM-DD HH:MM:SS +08:00>
> Revision basis: <loaded revision or new>

## Goal
## Changes
## Verification
## Open issues
## Pitfalls
```

- **已注册实体提交**：
  ```bash
  python scripts/handoff_store.py commit --id '<id>' --content-path '<draft.md>' --expected-revision <loaded-revision> --status '<status>'
  ```
- **新实体首次提交**：先执行 `register --id '<id>' --name '<name>' --type '<type>' --anchor '<abs-path>'`，再以 `--expected-revision 0` 提交。
- **并发防覆盖**：若 `--expected-revision` 不匹配，说明其他会话已更新该实体，必须停止并询问用户，严禁强行覆盖。每个实体最多自动保留最近 30 条历史版本。

## 四、 常用管理命令与质量门禁

- `list`：列出全部注册实体与最新版本号。
- `show --id <id>`：查看实体 Manifest 与 `CURRENT.md`。
- `add-alias --id <id> --alias <name>`：追加无冲突别名。
- `rollback --id <id> --revision <n> --expected-revision <cur>`：从历史版本生成新修订版（绝不篡改历史）。
- `audit`：校验注册表、Manifest、无 BOM UTF-8 编码、SHA-256 哈希一致性与 30 条历史上限（返回 `"ok": true` 且 Exit Code `0`）。
