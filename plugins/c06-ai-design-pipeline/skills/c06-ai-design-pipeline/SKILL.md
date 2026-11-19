---
name: c06-ai-design-pipeline
displayName: 19 · C06-AI设计流水线 v5.0.0 (Vibe-Agile)
description: 面向 App Vibe Coding 的敏捷 UI 设计、微创修 Bug、组件复用与审美自动沉淀流水线（C06 v5.0.0）。提供三轨智能分流（L1 免问卷微创直达 / L2 三问功能模块 / L3 五步向导与打包）、真快照防删函数护栏与正负样本自动沉淀。不含 Figma/Canva/Mobbin 及科研 SVG 概念图。
---

# C06 · AI设计流水线 v5.0.0 (Vibe-Agile 版)

面向创作者的零摩擦敏捷 UI 设计、微创修 Bug 与工程护栏中枢。彻底废除零信任密码学门禁，回归 **省 Token、免问卷直达、防误删函数、好品味自动沉淀**。

---

## 一、 三轨智能分流路由器（按需懒加载子卡片）

收到需求后先按改动规模路由，**仅按需读取 1 张对应子卡片**（日常 L1 严禁预加载 `dense_catalog.md` 等大文件）：

### 🟢 L1 微创直达轨（默认，占比 80%：改小组件 / UI 美化微调 / 小修 Bug）
- **0 问卷、免向导直达！**
- 允许修改 `.css/.ts/.tsx/.js/.jsx/.html/.vue` 等所有前端代码。
- 只加载对应的一张轻量卡片：
  - UI 美化/小组件微调：`references/track-l1-micro.md`
  - 局部修 Bug：`references/track-bugfix.md`

### 🟡 L2 功能模块轨（占比 15%：新增页面 / 较大组件重构）
- 仅问 **3 个核心审美与布局问题**（不再问 72 项大表）。
- 按需加载：`references/track-l2-feature.md`

### 🔴 L3 全新项目 / 全局换肤轨（占比 5%：从 0 到 1 或大改）
- 启用精简版 **5 步设计向导**，支持 Pake 桌面 `.exe` 打包。
- 按需加载：`references/track-l3-wizard.md`
- 大改动完成后可联动 E06/E07 多模型交叉审查。

---

## 二、 创作者七大护栏规约（每次修改强制生效）

### 1. 🪪 项目身份证 (`PROJECT_ANCHOR.md`)
- 进场先跑 `node "<SKILL_DIR>/scripts/vibe-guard.js" anchor <目录>` 读取或自动生成项目锚点。
- 锁定正式源码目录、禁碰草稿目录（如 `L_app`）、核心功能保护清单，杜绝概念串台。

### 2. 🔍 改前二开检索与复用
- 动手前必跑 `node "<SKILL_DIR>/scripts/vibe-guard.js" scan <目录>`（融合 `oil-dev-skills` 的 `repo_map` 与组件/同义函数扫描）。
- 优先复用现有组件与 CSS 变量，严禁硬编码与重复造轮子。

### 3. 🛡️ 真快照时光机 & 美化禁删函数红线
- 改前必跑 `node "<SKILL_DIR>/scripts/vibe-guard.js" snapshot <文件...>` 备份目标文件并提取全部函数/事件符号清单；
- 改后必跑 `node "<SKILL_DIR>/scripts/vibe-guard.js" verify`；
- 若在 UI 美化/微调中发现原有函数或事件丢失、或语法报错，**自动一键物理回滚 (`undo`)**！

### 4. 🔥 事不过二 · 自动换脑熔断
- 遵循微创法则查源码根因，严禁视觉盲猜；
- 同一 Bug 连续改 2 次未解决，强制触发 `vibe-guard.js undo` 物理回滚至初始干净状态，并提示/派发异构模型（Codex / DeepSeek）交叉会诊。

### 5. 👀 眼见为实冒烟检查
- UI/逻辑改完后，若有本地预览或 HTML，优先结合 `scripts/screenshot.js` 无头浏览器或 `vibe-guard.js verify` 语法静态检查，确认 **0 Console Error** 才交付。

### 6. ✨ 正负双向自动沉淀 (`scripts/distill.js`)
- 不再锁死在打包前！每次修改完成即静默触发：
  - **正样本 (`--positive`)**：自动将用户认可的配色、圆角、阴影、字体、动效 Token 写入项目 `DESIGN.md` / `tokens.css`；
  - **负样本 (`--negative`)**：将踩坑病因写入 `kit/data/design_badcases.json`（已录 Lucky Note 误删函数、概念串台、假回滚、视觉盲猜 4 大教训，带容量上限与去重防腐）。

### 7. 💬 创作者四格人话回执单
- 每次交付强制使用固定四格人话模板：
  - 🎨 **视觉/体验改了哪**：[一句话说明改了哪及具体效果]
  - 🔒 **原有功能安全确认**：[`X/X` 函数完好 | 语法与冒烟 `0` 报错]
  - 🧠 **本次自动沉淀了什么**：[记入 `DESIGN.md` 的审美 Token / 避坑规则]
  - ⏪ **一键撤回口令**：不满意直接输入 `u`，100% 物理还原至改前状态

---

## 三、 快捷键边界与零签名脚本速查

> **快捷键边界**：C06 仅使用 `u / d / g / ?`，**不抢占**多选题 `A/B/C/D`（含 `b`）及 E06/E07 的 `r` / `s`。

- **`u`（撤回快照）**：`node "<SKILL_DIR>/scripts/vibe-guard.js" undo [--dir <目录>]`
- **`d`（手动沉淀）**：`node "<SKILL_DIR>/scripts/distill.js" --positive ...` / `--negative ...`
- **`g`（体检除草）**：`node "<SKILL_DIR>/scripts/govern.js" <目录>`（详见 `references/governance-guide.md`）
- **`?`（状态速览）**：显示当前轨道（L1/L2/L3）、最近快照状态与 `u / d / g` 口令提示
