# Personal Shared Skills

这是 13 个个人 Codex skill 的可迁移 `workspace-local` marketplace。唯一版本清单是 `skill-pack.json`，规范 marketplace 清单是 `.agents/plugins/marketplace.json`。不要只复制单个 `SKILL.md`；插件还可能依赖脚本、参考资料和共享知识文件。

## 全新电脑的两阶段引导

全新电脑在个人 Skill 尚未存在时不能直接调用第 13 个管理 Skill。先用 Codex 内置 `skill-installer` 安装它的临时 bare 副本：

```text
使用内置 skill-installer，从 fighttiger-Wang/sc-seq 的
plugins/personal-skill-marketplace-setup/skills/personal-skill-marketplace-setup
安装 personal-skill-marketplace-setup。
```

重启 Codex 并新建任务，然后说：

```text
使用 personal-skill-marketplace-setup 在这台电脑部署我的个人 Skill。
源码目标是 <marketplace-clone-path>，共享工作区是 <workspace-root>。
```

`bootstrap` 会核对 Git、Python 3.10+、Codex CLI、GitHub 访问、目录安全、旧配置和磁盘空间；随后 clone `main`、运行 doctor、注册 `workspace-local`、安装并核对 13 个插件，并向所选工作区的 `AGENTS.md` 写入可重复更新的受管理同步块。它不会覆盖受管理块之外的既有说明。

完整 marketplace 验证成功后，临时 bare Skill 会被报告为重复来源。只有用户明确同意时，才用 `--disable-bootstrap-copy` 把它移动到 `$CODEX_HOME/skills.disabled` 下的可恢复备份；不会直接删除。

也可以不安装临时 Skill，直接 clone 仓库后运行：

```powershell
.\Setup-PersonalSkillMarketplace.ps1 -Mode bootstrap -WorkspaceRoot '<workspace-root>'
```

```bash
./Setup-PersonalSkillMarketplace.sh bootstrap --workspace-root '<workspace-root>'
```

安装或更新插件后需要重启 Codex 并新建任务。

## 日常检测、同步和发布

Bootstrap 写入的受管理规则会要求：每个任务第一次准备使用或修改另一个 `workspace-local` Skill 时，先执行一次 `preflight`。

- 本地与 `origin/main` commit 相同：立即返回 `up-to-date`，不 pull、不重装。
- 本地稳定分支落后：只允许 fast-forward，比较新旧 commit，并仅重装直接受影响的插件；共享文件或 marketplace 核心清单变化时保守地重装全部插件。
- 工作树不干净、分支错误、本地超前或历史分叉：停止，不覆盖。
- 插件发生更新：返回 `restartRequired: true`，当前任务停止，重启 Codex 后再使用新版 Skill。

修改 Skill 后先运行 `publish` 生成只读发布计划。Codex 必须向用户确认；确认后才能使用 `--confirm-publish` 创建 `codex/*` 分支、更新受影响插件 cachebuster、同步 `skill-pack.json`、测试、提交并推送。`--create-pr` 需要本机已安装并登录 GitHub CLI；否则结果会返回 GitHub compare URL 供创建 PR。

可用模式：

- `bootstrap`：新电脑完整部署并安装本机同步触发规则。
- `preflight`：按需检查稳定更新，无变化时零安装。
- `publish`：检测并准备发布；外部提交与推送要求显式确认。
- `audit`：只读检查，不联网更新或安装。
- `install`：安装已有 clone，不写受管理同步规则。
- `update`：兼容旧流程，拉取后验证并重装全部插件。
- `repair`：不联网，按本地源码修复安装。

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
