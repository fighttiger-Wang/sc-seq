# 🟢 L1 微创直达轨 · 轻量美化与小组件调整卡片

> **适用范围**：调整按钮/卡片间距、修改配色/圆角/毛玻璃质感、替换图标、增删局部小元素、单组件微调。  
> **核心铁律**：**0 问卷、免向导直达！严禁向用户弹出 5 步表格，严禁误删任何既有 JS 业务函数！**

## 1. 标准 4 步秒级闭环

1. **锚定与二开扫描（只读 1 秒）**：
   - 运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" anchor <项目目录>` 确认正式源码位置（绝不碰测试草稿目录）。
   - 运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" scan <项目目录>` 查看已有的 CSS 变量 Token 与现成组件。
   - **优先复用**项目既有的 `--primary`、`--radius` 等 CSS 变量，严禁乱写硬编码色值或 `!important` 暴力覆盖。

2. **改前真快照与符号锁定（强制）**：
   - 运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" snapshot <待改文件...>`。
   - 该步骤会将文件原封不动备份至 `.c06/snapshots/`，并自动提取文件中所有的 JS/TS 函数名与事件绑定清单。

3. **精准微创修改 & 防删核验**：
   - 仅修改目标样式或局部 DOM 结构，**严禁顺手重写或删除无关的 JS 函数**（吸取 Lucky Note 误删 `renderSpreadsheet()` 教训）。
   - 改后立即运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" verify`。
   - 若 `verify` 报错提示原有函数丢失或括号不匹配，必须立即运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" undo` 物理回滚并重新微创修改。

4. **审美沉淀 & 四格回执交付**：
   - 若本次调出了新的好看配色、圆角、阴影或动效参数，静默运行：
     `node "<SKILL_DIR>/scripts/distill.js" --positive --dir <项目目录> --category "<类别>" --token "<变量名:值>" --note "<审美说明>"`
   - 使用 `SKILL.md` 中的**创作者四格人话回执单**向用户汇报（告知改了哪、`X/X` 函数完好、沉淀了什么、输入 `.u` 或 `撤回` 可撤回）。
