# [应用名称] · 工业级设计需求契约书 (Design Spec)

## 1. 核心定位与业务主体
- **定位**：[一句话说明这是什么软件]
- **目标用户**：[目标用户角色与使用环境]
- **核心业务实体 (Entities & Ownership)**：
  - 核心数据对象：[如 Task、Device、Config，明确字段所有权与关系]
  - 唯一权威数据源 (Single Source of Truth)：[如 LocalStorage Key: 'app_data_v1' 或统一 Store]
- **核心交互闭环**：[从打开软件到完成任务的典型 3 步路径]

## 2. 界面骨架与主角拓扑 (One Protagonist & Primary Action)
- **主视窗模式**：[如：左侧侧边栏 (220px) + 顶部状态条 + 响应式主内容区]
- **视口核心主角 (Protagonist)**：[当前首屏核心展示与操作对象，如：主监控面板 / 任务流水线]
- **视口唯一主行动 (Primary Action)**：[当前视口最高权重主操作，如：[创建新任务]，其余操作均为次要态]
- **主功能模块清单**：
  1. [模块一名称]：核心作用与控件
  2. [模块二名称]：核心作用与控件

## 3. 视觉与品牌真理源 (DESIGN.md Tokens)
- **工程模式**：[全新从零创建 (Greenfield) ｜ 存量项目强继承 (Brownfield)]
- **品牌风格真理源**：[如：Linear 极客暗黑 / Stripe 现代纯白 / Notion 温润纸质]
- **主色系与背景**：[浅色 / 深色黑曜石 / 磨砂毛玻璃]
- **强调色**：#ff6900 (小米橙) / #0ea5e9 (科技蓝) / #5e6ad2 (Linear冷紫)
- **圆角与间距规范**：外层容器 14px，内部卡片 10px，小控件 6px

## 4. 交互控件、微动效与容器契约
- **核心按钮与排布**：[如：顶栏右侧 B01 新建实体主按钮 + B02 导入轮廓按钮]
- **已激活微动效清单 (M01~M30)**：
  1. [控件名称] ➔ [动效编号与名称]（如：保存按钮采用 M01-Roll 文字垂直翻换）
  2. [控件名称] ➔ [动效编号与名称]（如：核心统计卡采用 M02-Count 数字滚轮累加）
- **弹窗与浮层容器 (O01~O10)**：[如：指标说明采用 O01-Tooltip 悬浮透镜；配置采用 O02-Drawer 侧边抽屉]

## 5. 极端场景、工程治理与防呆契约
- **空状态**：展示温和插图、引导文案与 [立即创建] 按钮
- **长文本截断**：启用单行 truncate 并悬浮展示完整 Tooltip
- **去伪操作**：杜绝不能交互的纯装饰性 AI 图标或假按钮，内部 UUID 隐藏收敛
- **持久化闭环**：数据增删改查实时同步至本地存储，保证刷新与重启状态无损
- **异常恢复**：异步操作失败时保留用户已输入上下文并弹出非阻塞 Toast

## 6. 4+1 格规格核销单 (Spec Clearance Matrix · 出处绑定防伪)
| 维度代码 | 维度名称 | 状态标识 | 决策来源与出处绑定 (`confirmed_by`) | 核心规范内容与证据 |
| :---: | :--- | :---: | :--- | :--- |
| **Q1** | **几何拓扑** | [✔] | `user#turn-1` | L01~L11 拓扑、网格跨度、固有比例无拉伸 |
| **Q2** | **数据实体** | [✔] | `user#turn-2` | 实体字段、LocalStorage 唯一权威源、空状态 |
| **Q3** | **交互控件** | [✔] | `user#turn-3` | 唯一 Primary CTA (B01)、行内与次要控件 |
| **Q4** | **动效物理** | [✔] | `user#turn-4` | M01~M30 动效绑定清单，或合法 `[N/A (客观无动效)]` |
| **Q5** | **容器品牌** | [✔] | `user#turn-5` | O01~O10 容器形态、D01~D09 品牌 Token、WCAG 对比度 |

## 7. 版本迭代与出货归档 (Release Lifecycle)
- **语义化版本 (SemVer)**：v1.0.0
- **变更类型**：[初始版本 Initial ｜ 特性新增 Minor ｜ 缺陷修复 Patch]
- **归档路径**：`dist/releases/vX.Y.Z/`
- **更新日志概要 (Changelog)**：[本次发布的核心变动点与走查放行状态]

## 8. 代码改动范围物理契约 (Allowed Scope & Guardrails)
- **允许改动范围 (Allowed Scope)**: `src/pages/[PageID]/**`, `src/components/**`
- **物理禁改目录 (Forbidden Paths)**: `scripts/**`, `.c06/**`, `dist/**`, `package.json`

<!-- C06_SCOPE_START -->
```json
{
  "domain": "c06/task-scope/v1",
  "task_id": "T01",
  "lane": "L1",
  "owned_paths": [
    "src/pages/**",
    "src/components/**"
  ],
  "forbidden_paths": [
    "scripts/**",
    ".c06/**",
    "dist/**",
    "package.json"
  ],
  "scope_sha": "sha256:9009a6c858d69a1b612d271e6dbbeb41bcf2cb4af19781dd840c218693705176",
  "scope_user_auth": {
    "domain": "c06/user-auth/v1",
    "task_id": "T01",
    "action": "SCOPE_CONFIRM",
    "turn": 10,
    "subject_sha": "sha256:9009a6c858d69a1b612d271e6dbbeb41bcf2cb4af19781dd840c218693705176",
    "nonce": "a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d",
    "iat": 1794954180,
    "exp": 1795213380,
    "key_id": "ed25519:user:v1",
    "signature": "sig:ed25519:ecbfde61c1d20a2edf11671c1680f3abdb70ac61438a9a8195f4df4c375a89fc6cbd6cba8e200dffb6e7d2ebf345dde39d5faaeda37ac8cb8bd36df3c3942c08"
  }
}
```
<!-- C06_SCOPE_END -->


