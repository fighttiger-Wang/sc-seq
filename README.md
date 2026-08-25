# Personal Shared Skills

这是 13 个个人 Codex skill 的可迁移 `workspace-local` marketplace。唯一版本清单是 `skill-pack.json`，规范 marketplace 清单是 `.agents/plugins/marketplace.json`。不要只复制单个 `SKILL.md`；插件还可能依赖脚本、参考资料和共享知识文件。

## 先说明一个限制

全新电脑在个人 skill 尚未存在时，不能直接调用第 13 个下载安装 skill。这不是提示词能消除的循环依赖。

首次安装需要先通过普通 Codex/Git 操作取得仓库；安装完成后，才可以在新任务直接调用 `personal-skill-marketplace-setup` 完成审计、更新、修复和重装。内置 `skill-installer` 也能先安装第 13 个 skill 的子目录，但会暂时产生 bare skill 与 marketplace plugin 两个来源，因此不是默认推荐路径。

如果希望在全新电脑的一个普通 Codex 任务中完成首次安装，可直接发送下面的启动指令，并把两个占位符改成该电脑上的真实路径：

```text
请把 https://github.com/fighttiger-Wang/sc-seq.git 安装为这台电脑的 workspace-local skills。
源码目标是 <marketplace-clone-path>，共享工作区是 <workspace-root>；两者都不能与 CODEX_HOME 互相嵌套。
先只读检查操作系统、Git、Python 3.10+、Codex CLI、目标目录、现有 workspace-local 注册和磁盘空间；
发现远端错配、非空目标、位置冲突或权限问题就停止说明，不要覆盖。
确认后 clone main，运行仓库的 Setup-PersonalSkillMarketplace.ps1（Windows）或 .sh（macOS），
最后核对 skill-pack.json 中全部 13 个插件均为 installed, enabled 且版本一致。
不要使用 sudo、force、reset，也不要猜 Codex.app 内部路径；codex 不在 PATH 时请我提供完整路径。
```

这是普通 Codex 引导，不是调用尚未安装的个人 skill，因此没有循环依赖。

## 新电脑首次安装

先确认 Git、Python 3.10+ 和 Codex CLI 可用，再选择一个稳定、可写、可备份且空间充足的工作区。不要默认使用系统根目录、临时目录、Codex 插件缓存或未经确认的云同步目录。

```bash
git clone https://github.com/fighttiger-Wang/sc-seq.git <marketplace-clone-path>
cd <marketplace-clone-path>
```

Windows PowerShell：

```powershell
.\Setup-PersonalSkillMarketplace.ps1 -Mode audit
.\Setup-PersonalSkillMarketplace.ps1 -Mode install -WorkspaceRoot '<workspace-root>'
```

只有当本机执行策略明确阻止该脚本时，才在当前 PowerShell 进程临时执行 `Set-ExecutionPolicy -Scope Process Bypass` 后重试；不要修改机器或用户级策略。

macOS：

```bash
chmod +x ./*.sh tools/*.sh
./Setup-PersonalSkillMarketplace.sh audit
./Setup-PersonalSkillMarketplace.sh install --workspace-root "$HOME/CodexWorkspace"
```

工作区示例只是示例，不是通用最佳位置。Windows 盘符、macOS 用户目录、组织权限、备份策略和磁盘配额都可能不同。如果 `codex` 不在 `PATH`，显式传入：

```bash
./Setup-PersonalSkillMarketplace.sh install \
  --workspace-root "$HOME/CodexWorkspace" \
  --codex-cli /full/path/to/codex
```

安装器会：

- 核对 `workspace-local` 是否唯一指向当前源码仓库；
- 运行跨平台 doctor；
- 安装并核对 13 个插件的精确版本和 `installed, enabled` 状态；
- 成功后才写入 `$CODEX_HOME/workspace-local.json`（未设置时为 `~/.codex/workspace-local.json`）；
- 报告 bare skill 或其他 marketplace 中的重复来源，但不会自动删除。

安装完成后重启 Codex，并新建任务。

## 以后直接在新任务使用

```text
使用 personal-skill-marketplace-setup 检查并更新这台电脑上的共享 skills。
```

可用模式：

- `audit`：只读检查，不 clone、不 pull、不安装。
- `install`：安装已有 clone，或把预期仓库 clone 到明确指定的目标后安装。
- `update`：要求干净 Git 工作树，只允许 `git pull --ff-only`，随后验证并重装。
- `repair`：不联网拉取，按当前本地源码重新验证和安装。

第 13 个 skill 会区分直接观察到的事实、尚需目标机器验证的预测，以及工作区/备份/更新策略建议。Windows 通过不等于 macOS 已实机通过。

## 便携 ZIP

Windows：

```powershell
.\New-PersonalSkillBundle.ps1 -BundleName personal-codex-skills-current
```

macOS：

```bash
./New-PersonalSkillBundle.sh --bundle-name personal-codex-skills-current
```

ZIP 不包含缓存、日志、密钥、SQLite、`tmp/`、`outputs/` 或 `__pycache__`。

## 注释知识库发布

大类和亚类注释共用 `shared/sc-annotation-evidence-core` 作为唯一规范源。两个插件内的 core、配置和知识库是生成快照，不应独立编辑。活跃 `annotation_cases.sqlite3`、WAL、SHM、客户路径和案例历史不得进入 Git 或 ZIP。知识库及其快照的 SHA-256 按原始字节计算，因此发布工具强制写入 LF；不要让平台换行转换重新生成 manifest。

Windows：

```powershell
.\Publish-AnnotationKnowledge.ps1
.\Publish-AnnotationKnowledge.ps1 -CheckOnly
```

macOS：

```bash
./Publish-AnnotationKnowledge.sh
./Publish-AnnotationKnowledge.sh --check-only
```

也可以在新任务中说：

```text
使用 annotation-knowledge-release 更新注释知识库并推送到 GitHub。
```

## 重要边界与成本

- 安装 skill 不等于安装 Python/R 包、Seurat、WPS、字体、容器、远程凭据或分析数据。
- 可变的 `main` 分支适合获取当前状态，不等于可复现版本；严格复现应记录已核对的 commit，并使用审核过的 tag 或预先 checkout 到该 commit 后再执行 `install`/`repair`。
- 私有仓库需要现有 Git 凭据或令牌；脚本不会收集或保存密码。
- 更新会消耗网络、磁盘和时间；doctor 的运行时警告不等于插件结构失败，但会影响对应工作流执行。
- 权威源码和共享工作区不得与 `CODEX_HOME` 互相包含；把源码、安装缓存和工作产物混在同一目录树会增加重复来源、误扫描和误清理风险。
- 安装不是完整事务：位置配置只会在 13 个插件全部通过精确版本核对后写入，但 Codex CLI 若中途失败，已经完成的部分插件变更不会自动回滚，应在排除原因后执行 `repair`。
- 工作树有未提交改动、远端错配、分支异常、非 fast-forward、位置配置冲突或同名 marketplace 路径歧义时，管理器会停止，不会覆盖或强制修复。
- 只有在确认迁移唯一权威源码后才使用 `--relocate`（PowerShell 为 `-Relocate`）；它会替换保存的位置并重新注册 `workspace-local`，不是普通更新参数。
- `.agents/plugins/marketplace.json` 是规范清单；`.codex-plugin/marketplace.json` 是兼容副本，两者插件集合必须一致。
