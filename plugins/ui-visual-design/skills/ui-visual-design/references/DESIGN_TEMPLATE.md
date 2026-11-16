# DESIGN.md 标准设计规范模板

> 本文件是项目的唯一视觉设计规范源。无论是 Figma 导入还是纯文本设计，所有样式变量与 Token 均在此固化。

---

## 1. 颜色系统 (Color Tokens)

### 品牌主色 (Primary Accent)
* `brand-primary`: `#715BF5` (主强调色，按钮、高亮指示、选中态)
* `brand-primary-light`: `#DCD7FB` (浅紫色，第二柱状对比、微高光)
* `brand-primary-subtle`: `#F2F0FE` (次级淡背景，标签胶囊、选中背景)

### 表面与背景 (Surfaces & Backgrounds)
* `canvas-bg`: `radial-gradient(circle at 10% 20%, #E8EBFD 0%, #FBE8EC 45%, #EBE1F8 85%, #F4EDFA 100%)`
* `surface-glass`: `rgba(255, 255, 255, 0.75)` (主面板毛玻璃底色)
* `surface-card`: `rgba(255, 255, 255, 0.82)` (内部卡片底色)
* `surface-inset`: `rgba(238, 240, 247, 0.9)` (输入框、凹陷分段控制器背景)

### 边框与高光描边 (Borders & Highlights)
* `border-panel`: `1.5px solid rgba(255, 255, 255, 0.85)`
* `border-card`: `1px solid rgba(255, 255, 255, 0.9)`
* `border-subtle`: `1px solid rgba(226, 230, 240, 0.6)`

### 文本与字阶颜色 (Typography Colors)
* `text-primary`: `#1C1D22` (主标题、关键大字)
* `text-secondary`: `#696D7D` (正文说明、卡片副标题)
* `text-muted`: `#8C8E9B` (占位说明、图例标签、时间戳)
* `text-accent-success`: `#10B981` (增长率微标)
* `text-accent-danger`: `#EF4444` (报错指示)

---

## 2. 空间与网格 (Spacing Grid)

严格遵循 **4px / 8px 基础网格系统**：
* `space-1`: `4px`
* `space-2`: `8px`
* `space-3`: `12px`
* `space-4`: `16px`
* `space-5`: `20px`
* `space-6`: `24px`
* `space-8`: `32px`

---

## 3. 圆角与表面阴影 (Radii & Shadows)

### 圆角阶梯 (Border Radius)
* `rounded-panel`: `32px` ~ `36px` (外层主窗口/主看板)
* `rounded-card`: `16px` ~ `20px` (内部模块卡片)
* `rounded-pill`: `9999px` (胶囊按钮、分段控制器、状态微标)
* `rounded-control`: `10px` ~ `12px` (标准表单输入框)

### 弥散投影 (Ambient Shadows)
* `shadow-glass`: `0 20px 50px -12px rgba(113, 91, 245, 0.08), 0 0 0 1px rgba(255, 255, 255, 0.8) inset`
* `shadow-card`: `0 8px 24px -4px rgba(0, 0, 0, 0.03), 0 0 0 1px rgba(255, 255, 255, 0.9) inset`
* `shadow-card-hover`: `0 12px 28px -6px rgba(113, 91, 245, 0.09)`

---

## 4. 桌面环境特定护栏 (Lucky_Note Specifics)

* **Win32 顶栏拖拽保留带**：`height: 65px;` (该高度内绝对禁止放置阻断性事件层)
* **防粘连鼠标手势**：监听 `handleHeaderPointerMove`，5px 死区与 400ms 超时熔断
* **WebView2 字体族**：`"Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
