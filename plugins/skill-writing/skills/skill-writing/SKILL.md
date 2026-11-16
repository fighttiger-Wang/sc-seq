---
name: skill-writing
description: Create, register, validate, and prepare shared Codex skills for GitHub publication so they remain callable across Windows and macOS computers and after switching Codex/OpenAI accounts. Use when the user asks to write or update a skill, package a slash-callable plugin, maintain the shared marketplace, fix duplicate entries, assign workflow ordering, or make a skill cross-platform.
---

# Skill Writing

## Operating Rule

Build user-facing callable skills as plugins in the shared local marketplace, not as `@personal` plugins and not as bare skills. Resolve its root from `CODEX_SHARED_MARKETPLACE_ROOT`; when working in a checked-out source package, use the nearest ancestor containing `skill-pack.json`. Its configured name is `workspace-local`, and its source plugin directory is `<shared-marketplace-root>\plugins`.

Before editing, invoke `personal-skill-marketplace-setup` in `preflight` mode once for the task. If it installs an update, stop and ask the user to restart Codex and open a new task before continuing. Never edit an installed plugin cache as source.

Codex/OpenAI accounts can be switched and the package can be cloned to Windows or macOS. The plugin source remains in the configured shared marketplace while account-specific Codex registration can change. Keep exactly one active source for every maintained skill: `workspace-local`. Do not use `~/.codex/plugins/cache` as a source because it is only an installed cache.

Normalize every internal skill/plugin id to lowercase ASCII hyphen-case. Keep the requested Chinese name in UI metadata.

Every maintained skill display name must use exactly this format:

```text
[A-Z]\d{2} · Name
```

- `[A-Z]\d{2}` is the category letter followed by a two-digit group workflow order (e.g., A01–A07, B01–B07, C01–C02, D01–D02, E01–E04).
- The separator is the Unicode middle dot `·` (`U+00B7`) with exactly one ASCII space on each side.
- Example: `A02 · 大类谱系注释 v0.9.1`.
- Do not omit the separator or replace it with `路`, `.`, `•`, `-`, `:`, a full-width dot, or another visually similar character.
- Set the identical full display name in `plugin.json` `interface.displayName` and `agents/openai.yaml` `interface.display_name`.

### Skill Naming Conciseness Standard (命名精炼度与抗噪准则)

为了在 `/` 斜杠菜单、狭窄侧边栏以及自动补全列表中实现最佳的视觉扫视体验，杜绝中文字符溢出截断（`...`），所有维护的 Skill 必须严格遵循以下精炼命名法则：

1. **长度控制红线**：
   - 除去编号前缀（如 `A01-`）后，中文名称核心体必须严格控制在 **4 ~ 8 个汉字**以内（极简动宾或核心对象词），严禁超过 10 个汉字。
2. **大类内去冗余原则（No Redundant Namespace）**：
   - 既然大类字母已代表特定业务空间（如 `A` 代表单细胞分析、`B` 代表绘图可视化），**严禁在技能中文名中重复出现“单细胞”、“生信”等同义定语**。例如：采用 `A01-质控过滤提取`，严禁写成 `A01-单细胞数据分析质控过滤提取`。
3. **剔除连词与多动作强行并列**：
   - 严禁在名字中使用“及”、“与”、“和”、“以及”强行缝合两个图表或步骤。例如：采用 `B02-Marker表达图`，严禁写成 `B02-特征基因热图及选定基因小提琴图`。
4. **副标题与细节修饰语全面下沉至 Description**：
   - 名字仅用于**人类快速击键索引与视觉定位**；具体的算法细节、适用场景、图表变体（如“主要谱系”、“经典文档版”、“红蓝绿对抗”），一律放入 YAML Frontmatter 的 `description` 字段。
   - LLM 语义路由 90% 依赖 `description` 向量匹配，精简名字丝毫不影响智能体的调用准确率。

### Core Categorization Architecture (A-E)

1. **A 类：单细胞数据分析与综合生信工作流 (A01~A07)**
   - `A01-质控过滤提取`
   - `A02-大类谱系注释`
   - `A03-亚群精细注释`
   - `A04-知识库发布`
   - `A05-交互解读报告`
   - `A06-文档解读报告`
   - `A07-流程脚本工程`

2. **B 类：单细胞与生信绘图可视化 (B01~B07)**
   - `B01-质控分布图`
   - `B02-Marker表达图`
   - `B03-功能模块热图`
   - `B04-分组表达气泡图`
   - `B05-细胞比例统计图`
   - `B06-KEGG流泡图`
   - `B07-机制流程概念图`

3. **C 类：UI设计与工作台 (C01~C02)**
   - `C01-工作台`
   - `C02-UI视觉设计`

4. **D 类：服务器与HPC算力运维 (D01~D02)**
   - `D01-HPC超算指南`
   - `D02-服务器任务投递`

5. **E 类：Skill工程治理与决策规范 (E01~E04)**
   - `E01-任务交接`
   - `E02-三方专家评审`
   - `E03-Skill规范写作`
   - `E04-Skill市场安装`

### Mandatory Inquiry Gate for Uncategorized Skills (未归类强制中断发问门禁)

凡在后续任务中起草、编写或重构全新 Skill 时，必须遵循以下规则：
1. **自动归类优先**：首先评估新技能的技术领域是否能明确归入现有的 A~E 五大类。若能明确归入，分配该分类下紧接着的下一个两位流水号。
2. **【绝对红线禁令】严禁擅自推断大类**：如果新技能的技术方向或业务边界无法确定归入现有的 A~E 五大类，**智能体绝对严禁自行臆断指派大类字母（如擅自创建 F 类），亦严禁随意强行塞入现有大类**。
3. **【强制挂起发问】**：智能体必须**立即暂停执行，主动向用户提问**，列出该技能的核心功能特征，并明确询问：“*该新技能的方向无法在现有 A-E 架构中明确归类，请指示其应归属的大类字母及组内编号。*” 只有在获得用户的明确回复指令后，方可继续推进编号与目录创建。

## Direct Workflow

1. Read the current `skill-creator` and `plugin-creator` instructions if available.
2. Pick one normalized internal id for both plugin and skill.
3. Check the shared marketplace source and existing `workspace-local` plugin before writing.
4. Update an existing shared plugin in place. If a legacy personal plugin exists, migrate its source content into the shared marketplace and leave the old cache untouched as a recovery copy.
5. Create new plugins under `<shared-marketplace-root>\plugins\<id>` and append the same plugin, in the same workflow position, to all authoritative registries:
   - `skill-pack.json`, including its manifest version and the incremented `expectedPluginCount`;
   - `.agents/plugins/marketplace.json`;
   - `.codex-plugin/marketplace.json`.
6. Set the marketplace installation policy to `INSTALLED_BY_DEFAULT` and authentication policy to `ON_INSTALL`.
7. Create the skill under `<plugin>/skills/<id>/`.
8. Write only necessary files:
   - `.codex-plugin/plugin.json`
   - `skills/<id>/SKILL.md`
   - `skills/<id>/agents/openai.yaml`
   - optional `references/`, `scripts/`, or `assets/` only when they directly support execution
9. Set the same `[A-Z]\d{2} · Name` display name in both `plugin.json` and `agents/openai.yaml`.
10. Read both metadata files back as UTF-8 and verify that the two display names are identical and match `^[A-Z]\d{2} · .+$`; reject `路` or a missing/wrong separator.
11. Run the skill validator, plugin validator, marketplace doctor, and relevant behavioral tests.
12. Invoke `personal-skill-marketplace-setup` in `publish` mode without confirmation. It must return a read-only plan; for an unregistered new plugin, finish the three registries before proceeding.
13. Ask the user for explicit publication confirmation. Only then invoke confirmed publish, which updates cachebusters, synchronizes `skill-pack.json`, tests, commits, and pushes a `codex/*` branch. Create a PR when GitHub CLI/API access is available; otherwise return the compare URL.
14. Treat the PR as the release gate. `main` is the stable source used by other computers; do not merge automatically or report a merge without remote evidence.
15. After the PR is merged, other computers receive it through `preflight`. If plugins are installed or changed, tell the user to restart Codex and open a new task before testing `/`.

Read [shared-git-lifecycle.md](references/shared-git-lifecycle.md) when creating, updating, publishing, merging, or synchronizing a maintained Skill.

## File Requirements

Use UTF-8 without BOM for every plugin and skill file. Check or rewrite these files if slash invocation behaves strangely:

- `.codex-plugin/plugin.json`
- `skills/<id>/SKILL.md`
- `skills/<id>/agents/openai.yaml`
- any directly loaded reference files

Keep `SKILL.md` frontmatter minimal:

```yaml
---
name: skill-writing
description: Clear description containing what the skill does and when to use it.
---
```

Use `agents/openai.yaml` for the slash-menu display:

```yaml
interface:
  display_name: "10 · skill写作"
  short_description: "编写可 / 调用的个人 Codex skill 与插件标准流程"
  default_prompt: "Use $skill-writing to create or update a personal callable Codex skill."

policy:
  allow_implicit_invocation: true
```

Use `plugin.json` for plugin UI metadata. Include `skills: "./skills/"`, a real `author.name`, and useful interface fields such as `displayName`, `shortDescription`, `developerName`, `category`, `capabilities`, and `defaultPrompt`. Only include `composerIcon`, `logo`, or screenshots when the referenced files really exist.

## Validation And Cross-Account Install

Prefer Python 3 and OS-neutral scripts. On Windows, use the bundled Codex runtime Python when system `python` is missing and avoid WindowsApps aliases. On macOS, use `python3` and `codex` from `PATH`, or pass the full CLI path. Do not embed drive letters, usernames, `C:\Users`, `/Users/<name>`, or `/home/<name>` in maintained source.

Run the equivalent of:

```bash
python3 <installed-skill-creator>/scripts/quick_validate.py <plugin>/skills/<id>
python3 <installed-plugin-creator>/scripts/validate_plugin.py <plugin>
python3 <shared-marketplace-root>/tools/test_personal_skill_marketplace.py --marketplace-root <shared-marketplace-root>
python3 <personal-skill-marketplace-setup>/scripts/setup.py publish
```

The first `publish` call is read-only. Do not update cachebusters, commit, push, create a PR, or merge until the user explicitly confirms publication. After a merged update is synchronized, verify every maintained plugin is enabled under `workspace-local`. On macOS, rerun the marketplace installer after switching accounts; the source path is retained in `~/.codex/workspace-local.json`.

## Cross-platform requirements

- Put reusable logic in Python or R and keep `.ps1`/`.sh` as thin wrappers.
- Provide both Windows and macOS commands when a workflow has platform-specific syntax. Prefer one-line or POSIX-style examples for portable tools such as Python and Rscript.
- Make drive restrictions conditional on Windows. On macOS/Linux, require a user-approved writable workspace instead of inventing an E drive.
- Add macOS/Linux font candidates when scripts render Chinese text.
- Run the cross-platform marketplace doctor before packaging; it rejects implicit-invocation regressions and machine-specific home paths.

## Duplicate Cleanup

When `/` shows duplicate entries for the same skill, inspect all active sources. The usual cause is the same skill existing both as a legacy source and as the shared plugin:

- bare source: `~/.codex/skills/<id>`
- legacy personal source/cache: `~/plugins/<id>` and `~/.codex/plugins/cache/personal/<id>`
- shared source: `<shared-marketplace-root>\plugins\<id>`

Keep the shared plugin route. Move a bare skill to a disabled backup such as:

```text
~/.codex/skills.disabled/YYYYMMDD-dedupe/<id>
```

Do not delete the backup unless the user explicitly asks. After cleanup, remind the user that the current Codex session can still show stale menu entries until they open a new thread or restart Codex.

## Update Existing Plugins

When modifying an already installed shared plugin, run task-level preflight, update the authoritative shared source, validate it, and request a read-only publish plan. After explicit confirmation, publish through a `codex/*` branch and PR. Do not update another computer from the development branch; merge the reviewed PR into `main`, run preflight on that computer, and test in a new session.
