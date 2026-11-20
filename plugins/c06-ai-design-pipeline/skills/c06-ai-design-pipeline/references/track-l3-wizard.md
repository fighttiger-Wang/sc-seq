# 🔴 L3 全新项目 / 全局换肤轨 · 精简五步向导与打包出货卡片

> **适用范围**：从 0 到 1 打造全新桌面/Web 应用、全站视觉大换肤、或将网页应用通过 Pake 编译打包为独立 `.exe` / `.dmg` 客户端。

## 1. 精简版 5 步设计向导（S1 ~ S5）

仅在全新项目或全局大改时启用（可按需查阅 `references/dense_catalog.md`、`bento.md`、`craft.md`、`motion.md` 挑零件）：

- **S1 骨架与导航**：确认整体窗口形态（无边框透明顶栏 / 侧边栏导航 / Bento 仪表盘画布）。
- **S2 核心数据与空状态**：确认核心业务数据字段、唯一持久化权威源（LocalStorage/IndexedDB）及 0 数据空状态引导。
- **S3 关键交互控件**：确认各区域主行动按钮（Primary CTA）、防呆二次确认弹窗（删除/清空必配）与快捷键。
- **S4 微动效与手感**：确认 Hover 微反馈、按压弹性（`active:scale(0.97)`）及核心转场特效（内置 `kit/` 组件库）。
- **S5 品牌基因与桌面特化**：确认主辅配色（符合 WCAG AA 4.5:1 对比度）、圆角/毛玻璃参数及桌面端拖拽区（`-webkit-app-region: drag / no-drag`）。

## 2. 创作者工程底座初始化

1. **生成项目身份证**：运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" anchor <项目目录>` 初始化 `PROJECT_ANCHOR.md`。
2. **初始化设计基因库**：运行 `node "<SKILL_DIR>/scripts/distill.js" --positive --dir <项目目录> ...` 生成 `DESIGN.md` 与 `tokens.css`。
3. **分层模块化编码**：遵守单文件 `< 300 行` 瘦身原则，拒绝全部代码堆进单个几千行的 HTML。

## 3. 多模型交叉走查与 Pake 桌面打包

1. **无头渲染与静态门禁**：
   - 运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" verify` 检验语法与符号完整性；
   - 运行 `node "<SKILL_DIR>/scripts/screenshot.js" <入口HTML> <截图路径>` 确保 0 Console Error。
2. **按需多模型交叉审查（联动 `E06-红蓝对抗闭环` / `E07-派发`）**：
   - 大改完成后，询问用户是否需要唤醒独立子 Agent 或通过 `/E06-红蓝对抗闭环`、`/E07-派发` 对照 `references/audit_checklist.md` 做独立体验走查。
3. **Pake 极简打包（可选）**：
   - 若用户要求生成独立桌面 `.exe`，检查本机 `pake` 环境并打包输出至 `dist/releases/`，同步更新项目 `CHANGELOG.md`。
4. **交付四格回执**：输出标准**创作者四格人话回执单**。
