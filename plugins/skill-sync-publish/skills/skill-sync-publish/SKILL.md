---
name: skill-sync-publish
displayName: E05 · Skill同步发布 v0.1.1
description: E05 · Skill同步发布 v0.1.1：改完 Skill 后的 4 步原子级发布流水线（体检/升版/三端同步/推送 GitHub） Execute the 4-step atomic release pipeline after modifying any Skill: (1) cabin robustness validation via E03 `validate_skill_robustness.py`, (2) semantic version bump across `SKILL.md`, `plugin.json`, `openai.yaml`, and `skill-pack.json`, (3) tri-platform sync (`sync-antigravity`), and (4) GitHub `main` push (or `--pr`).
---

# E05 · Skill同步发布 v0.1.1

专职负责改完任何 Skill 后的 **4 步原子级同步与发布流水线**，彻底根治“改了代码漏升版本号”、“手工拷贝破坏 `/` 斜杠菜单”以及“本地改完忘推 GitHub 远端”三大顽疾。

> **职责边界**：
> - **`E05-Skill同步发布`（本 Skill）**：负责**本地改完 Skill 往三端同步并往 GitHub 推送发布**（Outbound Release）。
> - **`E04-Skill市场安装`**：负责新电脑部署、从 GitHub 往本地拉取更新与本地 `/` 菜单修复（Inbound Install & Repair）。
> - **`E03-Skill规范写作`**：负责 Skill 架构分类、编写规范与 5 大鲁棒性护栏定义。

---

## 一、 4 步原子级发布流水线 (`scripts/publish_skill.py`)

无论修改了哪个 Skill，交付前只需运行一条命令即可串联完成全套闭环：

```bash
# 预览发布计划（只读干跑，校验 Step 1 鲁棒性体检与拟升版本号）
python scripts/publish_skill.py <skill-id-or-name> [--version auto|patch|minor|major|X.Y.Z] --dry-run

# 经用户一次确认后，执行完整 4 步闭环并直接推送至 GitHub main 分支
python scripts/publish_skill.py <skill-id-or-name> [--version auto] --push -m "feat(skill): update <skill>"

# 可选：需要走 Pull Request + CI 门禁合入时使用 --pr
python scripts/publish_skill.py <skill-id-or-name> [--version auto] --pr
```

### 流水线 4 大原子步骤详解：

1. **Step 1 · 分舱鲁棒性体检（口令 `.g` / `体检`）**：
   - 自动调用 `E03-Skill规范写作/scripts/validate_skill_robustness.py` 校验目标 Skill；
   - 核验主文件 `<= 8 KB` 红线、无 BOM UTF-8、`displayName` 中点格式、分舱特化规则与三端注册表对齐。若存在任何 `Error` 立即阻断发布。
2. **Step 2 · 四点元数据自动升版本号**：
   - 自动调用 `tools/bump_skill_version.py <skill-id> auto`（或指定版本号 `X.Y.Z`）；
   - 原子级统一更新 `SKILL.md`、`plugin.json`、`agents/openai.yaml` 与 `skill-pack.json`，杜绝“幽灵版本”。
3. **Step 3 · 三端原子同步 (`sync-antigravity`)**：
   - 自动触发 `E04/scripts/setup.py sync-antigravity`；
   - 一次性同步更新：① Antigravity `~/.gemini/config/skills/<NN-中文名>`（自动注入中文 `name` 与 `displayName`）及 `~/.gemini/config/skills.json`；② Codex 本地市场缓存；③ 桌面便携包 `E:\Desktop\检索调用文件\skill`。
4. **Step 4 · GitHub 远端推送（Commit & Push）**：
   - 默认支持在用户一次确认后直接 Commit 并 Push 至 GitHub `fighttiger-Wang/sc-seq` 的 `main` 分支（`--push`）；
   - 同时保留 `--pr` 选项，通过 `setup.py publish --one-step` 走开发分支 PR 与 GitHub Actions CI 合入流程。

---

## 二、 快捷口令与回滚保护

- **`.g`（或中文 `体检`）**：单独触发 Step 1 分舱鲁棒性体检。
- **`.u`（或中文 `撤回`）**：若改坏或升版有误，调用 `validate_skill_robustness.py --rollback <skill>` 1 秒还原改前快照。
