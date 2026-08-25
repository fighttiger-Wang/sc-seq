# Personal Shared Skills

这是 11 个个人 Codex skill 的可迁移 marketplace。skill 以独立插件保存，统一安装、验证和打包；登录哪个账号不影响这些本地文件，但每台电脑都需要单独安装一次。

## 包含的插件

唯一版本清单在 `skill-pack.json`，Codex marketplace 清单在 `.agents/plugins/marketplace.json`。当前应包含 11 个插件，不要只复制单个 `SKILL.md`，因为部分插件还依赖同目录下的脚本、参考资料和共享知识文件。

## 新电脑安装

1. 将整个目录克隆或解压到新电脑的稳定位置。
2. 打开 PowerShell，进入本目录。
3. 先检查完整性：

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   .\Test-PersonalSkillMarketplace.ps1
   ```

4. 安装 marketplace 和全部 11 个插件：

   ```powershell
   .\Install-PersonalSkillMarketplace.ps1
   ```

   安装器会为当前 Windows 用户保存 `CODEX_SHARED_MARKETPLACE_ROOT` 和 `CODEX_SHARED_WORKSPACE_ROOT`，使 skill 不依赖固定盘符。若只想临时安装，可加 `-SkipUserEnvironment`。

5. 重启 Codex，并新建一个任务测试 skill 是否可见。

如果 `codex` 不在 PATH 中，显式传入 CLI：

```powershell
.\Install-PersonalSkillMarketplace.ps1 -CodexCli 'D:\path\to\codex.exe'
```

## 创建可复制的 ZIP

```powershell
.\New-PersonalSkillBundle.ps1
```

需要固定文件名以便覆盖更新时：

```powershell
.\New-PersonalSkillBundle.ps1 -BundleName personal-codex-skills-current
```

脚本会先运行结构检查，再生成 ZIP、文件哈希清单和 ZIP 的 SHA-256 文件。缓存、日志、密钥、`__pycache__` 和测试调试目录不会进入成品。

## 放入私有 Git 仓库

本目录已经具备独立仓库所需的 `.gitignore`。创建私有远程仓库后，在本目录执行：

```powershell
git init
git branch -M main
git add .
git commit -m 'Initial personal Codex skill marketplace'
git remote add origin <你的私有仓库地址>
git push -u origin main
```

仓库必须保持私有。提交前运行 doctor，并确认没有 `.env`、API Key、服务器密码、客户数据或项目输入文件。

## 更新规则

- 修改 skill 后同步更新其 `.codex-plugin/plugin.json` 版本和 `skill-pack.json` 中的版本。
- 运行 `Test-PersonalSkillMarketplace.ps1`。
- 在使用该 marketplace 的每台电脑重新运行安装脚本。
- 用新任务测试；已有任务不一定重新加载更新后的 skill。
- `.agents/plugins/marketplace.json` 是规范清单；`.codex-plugin/marketplace.json` 保持为兼容副本，两者的插件集合必须一致。

## 注释知识库发布

大类注释与亚类注释共用 `shared/sc-annotation-evidence-core` 作为唯一规范源码。两个插件中的脚本、配置和知识库只是由发布工具生成的快照，不应单独编辑。

运行中的案例学习库保存在 `<shared-workspace-root>/.sc-annotation-knowledge`。其中 `annotation_cases.sqlite3`、WAL、SHM、项目路径和案例历史不会进入 Git 或 ZIP；只有通过案例门禁与回归验证后生成的 `published/current/cell-annotation-knowledge-base.v2.json` 才能进入正式发布流程。

在主电脑发布最新批准知识库：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\Publish-AnnotationKnowledge.ps1
```

该命令会执行以下不可跳过的一致性链路：

- 导入 `published/current`，并备份将要覆盖的仓库文件到 `tmp`；
- 重建拆分知识库、完整知识库和 SHA-256 manifest；
- 将共享 evidence core、配置与知识库同步到两个注释插件；
- 使用同一个 cachebuster 更新两个插件并同步 `skill-pack.json`；
- 运行回归测试、skill/plugin 验证、marketplace doctor、ZIP 打包和本机重装。

只检查、不写入：

```powershell
.\Publish-AnnotationKnowledge.ps1 -CheckOnly
```

发布脚本成功后再审查 Git 变更、提交并普通推送。其他电脑执行 `git pull --ff-only` 后重新运行 `Install-PersonalSkillMarketplace.ps1` 并重启 Codex。

## 运行环境

插件文件本身可完整迁移，但执行具体分析还取决于新电脑是否具备相应运行时，例如 Python、R/Rscript、PowerShell、WPS 或工作流所需的 R/Python 包。doctor 会报告常用运行时状态；运行时缺失不会改变 skill 文件是否安装成功，但会影响对应工作流能否执行。

需要手动配置时使用：

```powershell
[Environment]::SetEnvironmentVariable('CODEX_SHARED_MARKETPLACE_ROOT', '<marketplace绝对路径>', 'User')
[Environment]::SetEnvironmentVariable('CODEX_SHARED_WORKSPACE_ROOT', '<marketplace父目录>', 'User')
```
