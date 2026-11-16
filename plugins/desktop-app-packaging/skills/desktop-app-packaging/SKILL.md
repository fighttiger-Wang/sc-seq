---
name: C05-桌面应用打包
displayName: C05 · 桌面应用打包 v1.0.0
description: C05 · 桌面应用打包 v1.0.0：基于开源顶级神器 Pake (Rust + Tauri) 与现代 Webview 体系，为不懂复杂底层代码的创作者提供电脑端桌面应用（Windows .exe / macOS .dmg / Linux .AppImage）的极简一键打包方案。支持将线上 Web 地址或本地 HTML/JS/CSS 项目以轻量级架构（仅数 MB、极低内存占用、原生级启动速度）打包为独立桌面软件，内置图标配置、窗口外观微调与多端发布指导。Use when packaging web projects, HTML prototypes, or SaaS URLs into standalone Windows (.exe) or macOS (.dmg) desktop apps using Pake.
---

# C05 · 桌面应用打包 v1.0.0

专为**“零代码基础、独立开发者、产品经理与超级个体”**打造的现代化电脑端桌面 App 打包工具与操作指引。

---

## 核心机制：为什么选择 Pake？

传统桌面应用（如原生开发）门槛高、报错多、编译极度痛苦；老牌方案 Electron 打包出来的安装包动辄 150MB~300MB。
**Pake**（由开发者 tw93 开源，基于 Rust + Tauri）采用**操作系统自带的原生微核心（Windows Webview2 / macOS WebKit）**：
* ⚡ **极小体积**：打包出来的安装包通常只有 **2MB ~ 15MB**（仅为 Electron 的五十分之一）；
* 🚀 **极低资源**：内存占用仅数十 MB，秒速启动；
* 🎯 **原生手感**：支持沉浸式透明标题栏、窗口拖拽、快捷键集成。

**本地运行状态验证**：本机已成功配置全局 `pake-cli v3.19.0` 环境，终端可直接调用 `pake` 命令行。

---

## 一、 极简打包方式（两种路径任选）

### 路径 1：本地终端一键极速打包（最快 30 秒出货）

如果你已经有一个部署在网上的网页（如 Vercel、Bolt.new、Lovable 或自有域名）：

```bash
# 语法结构：pake [网页地址] --name [软件英文名] --title [窗口中文标题]
pake https://my-app.vercel.app --name "LuckyWorkspace" --title "好运工作台"
```

如果打包本地文件夹中的 HTML 文件：
```bash
# 进入你的网页产物目录后打包
pake dist/index.html --name "LocalApp" --title "本地独立应用"
```

#### 常用高级参数组合推荐：
```bash
pake https://my-app.com \
  --name "SuperTool" \
  --title "超级生产力工具" \
  --width 1280 \
  --height 800 \
  --min-width 1024 \
  --min-height 700 \
  --icon "app-icon.ico" \
  --transparent \
  --multi-arch
```
* `--width` / `--height`：预设窗口默认长宽（推荐 1280x800，桌面黄金比例）；
* `--icon`：自定义软件桌面图标（Windows 需 `.ico` 格式，macOS 需 `.icns` 格式）；
* `--transparent`：开启沉浸式无边框/半透明标题栏，视觉感瞬间向苹果原生与小米澎湃拉齐。

---

### 路径 2：GitHub Actions 云端 0 配置在线打包（免本地编译，防报错神技）

如果你遇到本地网络波动或环境权限限制，这是最省心、100% 成功的全自动流水线：

1. 打开 GitHub 官方仓库：[tw93/Pake](https://github.com/tw93/Pake)；
2. 点击右上角 **`Fork`** 将仓库复制到你自己的 GitHub 账号下；
3. 进入你 Fork 的仓库，点击上方 **`Actions`** 选项卡；
4. 找到并点击左侧列表中的 **`Build App With Pake CLI`** 工作流；
5. 点击右侧 **`Run workflow`** 按钮，在弹出的表单中直接填入：
   * `App URL`：填你的网页链接；
   * `App Name`：填你的软件英文名（如 `MyNotes`）；
   * `Platform`：选择 `windows-latest` 或 `macos-latest`；
6. 点击确认运行，云端服务器会在 3 分钟内自动编译完成，并在页面下方直接提供生成的 `.exe` 或 `.dmg` 下载链接！

---

## 二、 桌面应用打包前的关键准备清单

1. **桌面图标（Icon）规范**：
   * 尺寸必须是 $512\times512\text{px}$ 或 $256\times256\text{px}$；
   * Windows 格式：`.ico`；
   * 在线免费转换工具推荐：[convertio.co/png-ico](https://convertio.co/zh/png-ico/)。
2. **离线与缓存策略**：
   * 确认所有引入的外部字体或静态图片资源没有防盗链；
   * 确保软件在无网络或断网时能优雅显示“网络重试”页面，而非白屏。
3. **右键与快捷键保护**：
   * 桌面 App 默认可禁用原生浏览器的右键菜单（如“检查元素”），保持专业客户端的质感：
   ```javascript
   // 放入 HTML 中即可禁用普通右键审查，增强桌面软件质感
   document.addEventListener('contextmenu', event => event.preventDefault());
   ```

---

## 三、 常见问题诊断与排坑指南

| 现象 | 原因分析 | 极速排查解法 |
| :--- | :--- | :--- |
| **打开 .exe 软件显示白屏** | 目标网页开启了严格的 iframe 嵌入限制或 CSP 安全阻拦 | 检查网页的 `X-Frame-Options` 响应头，确保支持 Webview 载入 |
| **Windows 提示“未知发布者”** | 个人打包软件未经过微软昂贵的数字签名证书（EV Code Signing）认证 | 点击“更多信息” $\to$ 选择“仍要运行”即可；商业发布才需购买证书 |
| **窗口无法拖动** | 开启了 `--transparent` 无标题栏，但界面未定义可拖动区域 | 在顶部导航栏的 CSS 中添加 `-webkit-app-region: drag;` 即可将该区域变为拖拽手柄 |

---

## 四、 激活此技能的典型触发词
* “帮我把这个网页打包成 Windows 软件”
* “用 Pake 打包电脑端 App”
* “怎么把做好的原型生成 .exe”
* `/C05-桌面应用打包`
