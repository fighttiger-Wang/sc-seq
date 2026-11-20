---
name: skill-writing
displayName: E03 · Skill规范写作 v0.4.0
description: E03 · Skill规范写作 v0.4.0：编写可 / 调用的双端标准 Skill 与五大零损耗鲁棒性护栏校验 Author, update, and validate dual-platform (Antigravity + Codex) skills across the A-E 5-cabin architecture (20 standard skills) with 5 zero-overhead robustness guardrails (`validate_skill_robustness.py`), snapshot/rollback protection (`.u`), and handoff to `E05-Skill同步发布` for atomic release.
---

# E03 · Skill规范写作 v0.4.0

定义 Antigravity（`~/.gemini/config/skills/`）与 Codex（`<shared-marketplace-root>/plugins/`）双平台统一的 **Skill 架构分类账本、命名与 Frontmatter 铁律、基线防退化门禁** 及 **5 大零损耗自动化鲁棒性护栏**。

> **职责边界**：
> - **`E03-Skill规范写作`（本 Skill）**：负责 Skill 架构设计、分舱编码规范、改前快照回滚与 `scripts/validate_skill_robustness.py` 鲁棒性体检（口令 `.g` / `体检`）。
> - **`E05-Skill同步发布`**：专职负责 Skill 修改完成后的自动升版、三端同步与 GitHub 推送。
> - **`E04-Skill市场安装`**：专职负责新电脑部署、从 GitHub 拉取更新与本地 `/` 菜单修复。

---

## 一、 全平台 A~E 五大类分类账本（共 20 个标准 Skill）

所有正式维护的 Skill 必须归入以下 **A~E 五大类（20 个标准槽位）**。新增技能若无法明确归入现有 A~E 五大类，**必须立即挂起并主动向用户发问确认大类字母及编号**，严禁擅自新建 F 类或强塞！

1. **🧬 A 类：生信分析舱 (`A01~A07`，共 7 个)**
   - `A01-质控过滤提取` (`single-cell-qc-extract`)
   - `A02-大类谱系注释` (`sc-major-celltype-annotation-auto`)
   - `A03-亚群精细注释` (`sc-marker-cluster-annotation-auto`)
   - `A04-知识库发布` (`annotation-knowledge-release`)
   - `A05-交互解读报告` (`bioinformatics-results-report`)
   - `A06-文档解读报告` (`bioinformatics-results-report-classic`)
   - `A07-流程脚本工程` (`workflow-script-structure`)
2. **📊 B 类：科研绘图舱 (`B01~B07`，共 7 个)**
   - `B01-质控分布图` (`single-cell-qc-image-display`)
   - `B02-Marker表达图` (`feature-gene-heatmap-violin`)
   - `B03-功能模块热图` (`celltype-function-heatmap`)
   - `B04-分组表达气泡图` (`sc-group-gene-bubble-stats`)
   - `B05-细胞比例统计图` (`sc-cell-proportion-stats`)
   - `B06-KEGG流泡图` (`kegg-flow-bubble-plot`)
   - `B07-机制流程概念图` (`scientific-diagram-016`)
3. **🎨 C 类：App 敏捷设计舱 (`C06`，共 1 个)**
   - `C06-AI设计流水线` (`c06-ai-design-pipeline`) *(注：原 C01~C05 已全量融合归档入 C06)*
4. **🖥️ D 类：算力运维舱 (`D01~D02`，共 2 个)**
   - `D01-HPC超算指南` (`hpc-computing-guide`)
   - `D02-服务器任务投递` (`server-task-delivery`)
5. **⚙️ E 类：工程治理与调度舱 (`E01~E07`，共 7 个)**
   - `E01-任务交接` (`task-handoff`)
   - `E02-生信三方评审` (`tripartite-expert-review`)
   - `E03-Skill规范写作` (`skill-writing`)
   - `E04-Skill市场安装` (`personal-skill-marketplace-setup`)
   - `E05-Skill同步发布` (`skill-sync-publish`)
   - `E06-红蓝对抗闭环` (`local-agent-delegate`)
   - `E07-派发` (`e07-dispatch`)

---

## 二、 命名精炼度与双端元数据标准

1. **命名精炼度红线**：
   - 除去前缀（如 `A01-`）后，中文名核心体严格控制在 **2 ~ 8 个字符**以内（严禁超过 10 个汉字），不在名中重复大类同义词或用“及/与/和”强行并列，细节一律下沉至 `description`。
2. **`displayName` 严格格式**：
   - 必须符合正则 `^[A-Z]\d{2} · .+ v\d+\.\d+\.\d+$`（分隔符为 Unicode 中点 `·` `U+00B7`，左右各 1 个英文空格，末尾带 `vX.Y.Z` 语义版本号）。
   - `plugin.json` (`interface.displayName`)、`agents/openai.yaml` (`interface.display_name`) 与 `SKILL.md` (`displayName` 及首行 `# 标题`) 四处必须 **100% 完全一致**。
3. **严禁手工拷贝覆盖 `~/.gemini/config/skills/`**：
   - 直接复制源码 `SKILL.md` 会导致 Antigravity 顶层 `name` 变成英文插件 ID 而从 `/` 斜杠菜单消失！必须通过 `E04/scripts/setup.py sync-antigravity`（或 `E05/scripts/publish_skill.py`）自动转译注入 `name: [A-Z]\d{2}-中文名`。

---

## 三、 五大零性能损耗鲁棒性护栏 (`scripts/validate_skill_robustness.py`)

修改任何 Skill 前后，均可通过内置脚本执行毫秒级体检与快照保护（对应全局口令 `.g` / `体检` 与 `.u` / `撤回`）：

```bash
# 1. 改前创建秒级备份快照
python scripts/validate_skill_robustness.py --snapshot <skill-id-or-name>

# 2. 运行全套 20 个 Skill（或单个 Skill）五大护栏分舱体检
python scripts/validate_skill_robustness.py [--skill <skill-id-or-name>] [--json]

# 3. 改坏时 1 秒物理还原（对应口令 .u / 撤回）
python scripts/validate_skill_robustness.py --rollback <skill-id-or-name>
```

### 五大自动化护栏核验法则：
1. 📏 **护栏 1（主文件防肥胖红线 `<= 8 KB`）**：
   - 新编写或重构的 **C 类 / E 类 Skill 主文件 `SKILL.md` 严格强制 `<= 8 KB`**（杜绝 28KB 巨石撑爆上下文）；长篇协议或模板一律下沉至 `references/` 按需读取。
   - 对于历史遗留超 8KB 的 A/B/D 类专业生信 Skill，输出温和 `WARNING` 提示可按需下沉 `references/`，不阻断既有生信管线。
2. 🛡️ **护栏 2（`/` 斜杠菜单防消失锁 & 无 BOM UTF-8）**：
   - 强制校验 Antigravity 目录名 == `SKILL.md` `name` == `ANTIGRAVITY_SKILLS_MAP` 注册项；
   - 强制校验 `displayName` 符合 `^[A-Z]\d{2} · .+ v\d+\.\d+\.\d+$`；
   - 强制校验所有 `.md/.json/.yaml/.py/.js` 为 **UTF-8 无 BOM**。
3. 🧬 **护栏 3（A/B/C/D/E 五大类分舱特化校验）**：
   - **A/B 生信与绘图舱**：校验 `shared/sc-annotation-evidence-core` 知识库快照哈希一致性与生物学规则基线，不强套工程快捷键；
   - **C 前端设计舱**：校验 `vibe-guard.js`、`distill.js`、`govern.js` 核心脚本完备性与防删函数护栏；
   - **D 算力运维舱**：校验无本机个人账户绝对路径硬编码泄漏；
   - **E 治理与调度舱**：校验快捷口令是否统一采用 **`.前缀`（`.? / .u / .d / .g / .s`）**，严禁劫持裸单字母 `A/B/C/D/b`，严禁默认调用付费外援（`dsh`/`codex`）。
4. 🗺️ **护栏 4（三端注册表 100% 对齐核验）**：
   - 校验 `~/.gemini/config/skills/`（20 个标准 Skill）、`~/.gemini/config/skills.json`、`setup.py` 的 `ANTIGRAVITY_SKILLS_MAP` 与 `skill-pack.json` / `marketplace.json` 100% 对齐，无孤儿目录或残留 `_archive_*`。
5. ⏪ **护栏 5（改前真快照与 1 秒回滚）**：
   - 改前 `--snapshot` 自动将插件与 Antigravity 目录备份至 `~/.gemini/archive_e_series_backup/skill_snapshots/`；遇异常随时 `--rollback`（口令 `.u`）1 秒字节级还原。

---

## 四、 修改既有 Skill 的防退化规程与发布交接

1. **既有规则基线保护**：修改任何已有 Skill（尤其是 `A02`/`A03` 生信注释规则）前，必须先通读其当前 `SKILL.md` 及关联 `references/`，仅做最小增量修改（`add`/`clarify`/`strengthen`），未经用户显式授权严禁删减既有生物学判据或质控门禁。
2. **移交 `E05-Skill同步发布` 闭环**：当 Skill 编写或修改通过 `validate_skill_robustness.py`（`0 Error`）后，直接调用 `/E05-Skill同步发布`（`publish_skill.py`）一键完成版本递增、三端同步与 GitHub 远端推送。
