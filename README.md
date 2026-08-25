# Personal Shared Skills

这是 12 个个人 Codex skill 的可迁移 marketplace。skill 以独立插件保存，统一安装、验证、发布和打包；切换 Codex/OpenAI 账号不影响源码，但每台电脑、每个本地 Codex 配置都需要安装一次。

唯一版本清单是 `skill-pack.json`，规范 marketplace 清单是 `.agents/plugins/marketplace.json`。不要只复制单个 `SKILL.md`，因为插件还可能依赖脚本、参考资料、资产和共享知识文件。

## 新电脑安装

先将整个仓库克隆到稳定位置：

```bash
git clone https://github.com/fighttiger-Wang/sc-seq.git
cd sc-seq
```

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\Test-PersonalSkillMarketplace.ps1
.\Install-PersonalSkillMarketplace.ps1
```

macOS/Linux：

```bash
chmod +x ./*.sh tools/*.sh
./Test-PersonalSkillMarketplace.sh
./Install-PersonalSkillMarketplace.sh
```

安装器会注册 `workspace-local` 并安装全部 12 个插件。跨平台安装器把源码位置记录到 `~/.codex/workspace-local.json`，使后续新任务能够定位仓库而不依赖固定盘符或用户名。如果 `codex` 不在 `PATH`，传入完整路径：

```bash
./Install-PersonalSkillMarketplace.sh --codex-cli /full/path/to/codex
```

安装完成后重启 Codex，并新建任务测试 `/` 技能列表。第 11 个 `bioinformatics-results-report` 和第 12 个 `annotation-knowledge-release` 都允许默认发现。

## 创建便携 ZIP

Windows：

```powershell
.\New-PersonalSkillBundle.ps1 -BundleName personal-codex-skills-current
```

macOS/Linux：

```bash
./New-PersonalSkillBundle.sh --bundle-name personal-codex-skills-current
```

脚本先运行跨平台 doctor，再生成 ZIP、逐文件哈希清单和 ZIP SHA-256。缓存、日志、密钥、SQLite、`__pycache__` 和测试调试目录不会进入成品。

## 注释知识库发布

大类注释和亚类注释共用 `shared/sc-annotation-evidence-core` 作为唯一规范源码。两个插件中的 core、配置和知识库都是生成快照，不应单独编辑。

活跃案例学习库保存在 `<shared-workspace-root>/.sc-annotation-knowledge`。`annotation_cases.sqlite3`、WAL、SHM、客户路径和案例历史不进入 Git 或 ZIP；只有通过案例晋升与回归验证的 `published/current/cell-annotation-knowledge-base.v2.json` 可以正式发布。

Windows：

```powershell
.\Publish-AnnotationKnowledge.ps1
.\Publish-AnnotationKnowledge.ps1 -CheckOnly
```

macOS/Linux：

```bash
./Publish-AnnotationKnowledge.sh
./Publish-AnnotationKnowledge.sh --check-only
```

完整发布会备份仓库文件、导入批准库、重建拆分库和 manifest、同步两个注释插件、统一 cachebuster、运行回归与 doctor、生成 ZIP，并重装本机插件。脚本不自动 Git commit/push；验证后审查变更并普通推送，禁止 force push。

也可以在新 Codex 任务中直接说：

```text
使用 annotation-knowledge-release 更新注释知识库并推送到 GitHub。
```

第 12 个 skill 会定位源码仓库、完成发布门禁、审查 Git 变更、普通提交和推送，并核对远程提交。

## 更新与跨平台规则

- 修改插件后同步更新 `.codex-plugin/plugin.json` 与 `skill-pack.json` 版本。
- 所有维护 skill 都应保持 `allow_implicit_invocation: true`；跨平台 doctor 会阻止再次出现默认清单缺失。
- 可复用逻辑放在 Python/R；`.ps1` 和 `.sh` 只作为薄入口。
- Windows 的 E 盘限制必须写成条件规则，不能应用到 macOS/Linux。
- 文档和配置不得写入固定的 `C:\Users\<name>`、`/Users/<name>` 或 `/home/<name>`。
- 更新后在每台电脑重新运行安装器，并用新任务测试；旧任务可能缓存旧技能清单。
- `.agents/plugins/marketplace.json` 是规范清单；`.codex-plugin/marketplace.json` 是兼容副本，两者插件集合必须一致。

## 运行环境

安装 skill 不等于安装所有分析依赖。具体工作流仍可能需要 Python 3、R/Rscript、Seurat、Pillow、openpyxl、WPS 或其他包。doctor 会报告当前 PATH 中的运行时；缺少可选运行时不会改变插件源码完整性，但会影响对应工作流执行。跨平台脚本优先使用 `codex` 的 `PATH`，否则要求显式传入 `--codex-cli`，不依赖固定的应用内部路径。
