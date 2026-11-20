---
name: personal-skill-marketplace-setup
displayName: E04 · Skill市场安装 v0.4.1
description: E04 · Skill市场安装 v0.4.1：新电脑部署、从 GitHub 拉取更新与本地 / 斜杠菜单修复器 Pure downloader, installer, and local slash-menu repair utility (`bootstrap` / `install` / `update` / `sync-antigravity` / `repair` / `audit`) for the shared Codex and Antigravity skill marketplace. Never run network `preflight` or `git fetch` automatically before routine chat tasks; use `E05-Skill同步发布` for publishing modified skills.
---

# E04 · Skill市场安装 v0.4.1

跨平台（Windows / macOS）**纯下载、安装与本地环境修复器**。使用 `scripts/setup.py` 管理本地共享技能市场（Git 远端仓库：`https://github.com/fighttiger-Wang/sc-seq.git`）。

> **职责边界与零减速铁律**：
> - **`E04-Skill市场安装`（本 Skill）**：只做**“从远端往本地拉取安装”**和**“本地 `/` 斜杠菜单与缓存修复”**。
> - **`E05-Skill同步发布`**：专职负责本地改完 Skill 后的升版本号、三端同步与向 GitHub 推送发布。
> - **🚨 拔除联网减速陷阱（No Routine Network Fetch）**：**`preflight` 仅在换电脑、换账号或用户显式要求检查远端更新时手动调用**！**绝对严禁**在日常每次对话任务前自动联网执行 `git fetch` 拖慢响应！

---

## 一、 三大核心职责与标准命令

### 1. 📥 新电脑 / 新环境一键部署 (`bootstrap` / `install`)
在全新电脑或切换 Codex/OpenAI 账号后，一键克隆或挂载共享市场并完成双端注册：

```bash
# 全新电脑首次克隆并初始化工作区配置
python scripts/setup.py bootstrap --destination <approved-clone-path> --workspace-root <approved-workspace>

# 基于本地已有权威克隆目录直接安装注册
python scripts/setup.py install --marketplace-root <approved-clone-path> --workspace-root <approved-workspace>
```

### 2. 🔄 按需从 GitHub 拉取最新稳定版 (`update` / 按需 `preflight`)
仅当用户主动说“更新一下 Skill 库”、“拉取最新 GitHub 技能”或刚换到另一台电脑时调用：

```bash
# 从 GitHub origin/main 快进拉取最新稳定版并重装受影响插件
python scripts/setup.py update

# 按需检查本地与远端 origin/main 提交差异并同步（严禁日常每轮对话自动调用）
python scripts/setup.py preflight
```

### 3. 🛠️ 修复本地 `/` 斜杠菜单与三端映射 (`sync-antigravity` / `repair` / `audit`)
离线零网络依赖，1 秒修复 Antigravity 中文斜杠菜单、Codex 缓存或桌面便携包：

```bash
# 离线一键同步 A~E 全套标准 Skill 至 ~/.gemini/config/skills/、skills.json 及桌面便携包
python scripts/setup.py sync-antigravity

# 离线重新校验并修复本地 Codex 插件缓存
python scripts/setup.py repair

# 只读诊断本地市场源、版本一致性与安装健康度（0 写入、0 联网）
python scripts/setup.py audit
```

---

## 二、 安全护栏与会话生效说明

1. **唯一权威源原则**：`~/.codex/workspace-local.json` 中记录的 Git 检出目录为唯一权威源，严禁将 `~/.codex/plugins/cache` 当作源码编辑。
2. **智能 Git 自动探测**：`setup.py` 自动从系统 `PATH` 及本机常驻路径（如 `E:\A001-软件安装\Git\cmd\git.exe`）探测注入 Git，无需手工配置环境变量。
3. **非破坏性事务安装**：拒绝根目录、用户主目录或非空无关目录作为克隆目标；不使用 ` git push --force`、`git reset --hard` 或系统包管理器（Homebrew/Chocolatey）。
4. **菜单缓存刷新提示**：执行 `install`、`update` 或 `sync-antigravity` 后，新版本技能已在磁盘落盘，若当前旧聊天窗口的 `/` 自动补全未立即更新，新开一个对话会话即可加载最新元数据。
