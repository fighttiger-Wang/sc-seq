# CHANGELOG · C06-AI设计流水线 (AI Design Pipeline)

## [5.0.0] - 2026-11-20 (Vibe-Agile 拨乱反正版)

### 🚨 重大架构重构（拔除 30 轮对攻密码学毒瘤，找回 `oil-dev-skills` 真精髓）
- **彻底移除密码学自嗨层**：
  - 废除 `c06_crypto.js`、`clearance.js`、`gate-check.js`、`scope-check.js` 中的 Ed25519 五权公私钥体系、RFC 8785 JCS 序列化、15 分钟短期租约 (`l0_lease`)、Merkle 因果账本与 `AST_ZERO_REF_PROOF` 签名门禁。
  - 删除 `references/*.schema.json` 等重型 Schema，解决改一个小按钮也吞噬上百 KB 上下文的顽疾。
- **主入口 `SKILL.md` 极致瘦身（28.5 KB ➔ < 5 KB）**：
  - 收敛 `description` 触发词，精准定位为“面向 App Vibe Coding 的敏捷 UI 设计、微创修 Bug、组件复用与审美自动沉淀流水线”，与 `figma-*`、`canva-*`、`mobbin`、`B07` 划清边界。
  - 升级为**三轨智能分流路由器（按需懒加载子卡片）**：
    - 🟢 **L1 微创直达轨（默认 80%）**：0 问卷、免向导直达！全面解锁 `.css/.ts/.tsx/.js/.jsx/.html/.vue` 修改权限，按需只读 `track-l1-micro.md` 或 `track-bugfix.md`。
    - 🟡 **L2 功能模块轨（15%）**：仅问 3 个核心审美与布局问题，按需只读 `track-l2-feature.md`。
    - 🔴 **L3 全新项目/全局换肤轨（5%）**：精简 5 步设计向导 + 多模型交叉审查 + Pake 打包，按需只读 `track-l3-wizard.md`。
- **内置创作者七大铁律护栏**：
  1. 🪪 **项目身份证 (`PROJECT_ANCHOR.md`)**：通过 `vibe-guard.js anchor` 锁定正式源码目录、禁碰测试草稿目录（如 `L_app`）与受保护函数清单。
  2. 🔍 **改前二开检索与复用 (`vibe-guard.js scan`)**：移植 `oil-explore` 的 `repo_map`、现有组件与 CSS 变量提取、重复函数与硬编码扫描。
  3. 🛡️ **真快照时光机 & 美化禁删函数红线 (`vibe-guard.js snapshot / verify / undo`)**：改前毫秒级物理备份并提取函数符号表；改后自动防删核验，发现既有业务函数丢失立即报错拦截并支持一键物理还原 (`u`)。
  4. 🔥 **事不过二 · 自动换脑熔断**：融合 `oil-bug-fix` 微创四步法，同一 Bug 连续改 2 次未解决强制物理回滚并呼叫异构模型（Codex / DeepSeek）交叉会诊。
  5. 👀 **眼见为实冒烟检查**：结合 `vibe-guard.js verify` 语法校验与 `screenshot.js` 无头渲染确认 0 Console Error。
  6. ✨ **正负双向自动沉淀 (`distill.js --positive / --negative`)**：每次修改完成即刻触发，正样本自动写入项目 `DESIGN.md` / `tokens.css`；负样本写入 `kit/data/design_badcases.json`（完整补录 Lucky Note 误删函数、概念串台、假回滚、视觉盲猜 4 大血泪教训，带容量上限与去重防腐）。
  7. 💬 **创作者四格人话回执单**：固定交付模板（🎨 视觉改了哪 ➔ 🔒 `[X/X 函数完好]` ➔ 🧠 本次沉淀了什么 ➔ ⏪ 撤回口令 `u`）。
- **做实长期工程治理 (`govern.js` / 口令 `g`)**：
  - 1:1 移植 `oil-govern` 能力，一键扫描 `>300` 行超长文件、孤立死函数、过期混乱文档与死链，输出创作者人话体检报告。
- **快捷键防撞车与多端同步 (`sync-release.js`)**：
  - 划清全局快捷键边界：C06 仅使用 `u / d / g / ?`，不抢占多选题 `A/B/C/D`（含 `b`）及 E06/E07 的 `r` / `s`。
  - 新增 `scripts/sync-release.js` 实现主目录、本地共享市场与 Git 仓库一键同步。

---

## [4.0.0-Industrial-Release] - 2026-11-18
- 引入 33 项 Ed25519 信任根验签、T00/T01/T02 三轨任务包、9 大门禁零写入校验（因过度密码学化导致真实 Vibe Coding 体感阻塞，已于 v5.0.0 重构废止）。

## [3.9.0-Industrial] - 2026-11-18
- 统一 `gate-check.js`、`scope-check.js`、`clearance.js`、`screenshot.js` 版本口径与 `L0-A/L0-B/L1/L2` 泳道枚举。

## [2.0.0] - 2026-11-17
- 归档 C01~C05，将 `kit/` 高保真组件库迁入 C06，初步引入 `scope-check` 与长期治理口令 `g`。

## [1.4.0] - 2026-11-17
- 引入 5 步满射向导 S1~S5 与 4+1 格规格核销单。

## [1.2.0 ~ 1.3.1] - 2026-11-17
- 吸收 `oil-ui` / `oil-frontend` 六大工程治理契约、L1~L4 四层验证、Bento 多尺度网格与多模型 Review 路由。

## [1.0.0 ~ 1.1.0] - 2026-11-16
- 初始版本创建：融合事前需求追问、72 项密集表格向导、知识库注入、无头截图走查、经验蒸馏与 Pake 桌面打包。
