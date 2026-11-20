# 🟢 L1 微创修 Bug 轨 · 根因定位与事不过二熔断卡片

> **适用范围**：按钮点击无反应、弹窗关不掉、局部布局错位、控制台报错、状态未保存等存量 App 缺陷修复。  
> **核心铁律**：**0 问卷、免向导直达！解锁 `.js/.ts/.tsx/.jsx/.html/.vue/.css` 全类型修改权限，严禁视觉盲猜贴补丁！**

## 1. 吸收 `oil-bug-fix` 的微创四步法

1. **查源码根因（严禁凭截图视觉盲猜）**：
   - 先运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" anchor <项目目录>` 锁定正式生产文件。
   - 直接阅读报错行、事件绑定函数与底层 CSS 变量定义，找出导致 Bug 的那 1~3 行确切根因（诊断期不乱改代码）。

2. **改前真快照备份（强制）**：
   - 动手改代码前，必须运行：
     `node "<SKILL_DIR>/scripts/vibe-guard.js" snapshot <待改文件...>`

3. **源头最小微创修改（禁止顺手重构）**：
   - 只在根因位置做最小行数的修改。
   - **三不准**：不准顺手重构旁边正常的业务函数；不准用空 `try { ... } catch(e) {}` 吞掉报错假装修好；不准为了修一个弹窗去重写整个页面的 DOM。

4. **符号防删与运行时核验**：
   - 改后立即运行 `node "<SKILL_DIR>/scripts/vibe-guard.js" verify` 确认零函数误删、零语法错误。
   - 若是 HTML/前端页面，优先跑 `node "<SKILL_DIR>/scripts/screenshot.js" <htmlPath> <outPng>` 验证 0 Console Error。

## 2. 🔥 事不过二 · 自动换脑熔断机制

- 若同一个 Bug **连续修改 2 次仍未解决**（或改完引发新的布局异常）：
  1. **立即停止第 3 次盲改**！
  2. 强制执行 `node "<SKILL_DIR>/scripts/vibe-guard.js" undo` 将代码 100% 物理还原到改前干净基线（严禁凭记忆手写“假回滚”）。
  3. 触发负样本沉淀：`node "<SKILL_DIR>/scripts/distill.js" --negative --category "Bug修复踩坑" --title "<问题简述>" --badcase "<失败改法>" --solution "<待查方向>" --rule "<防再犯红线>"`
  4. 向用户输出四格回执，并建议通过 `E06-红蓝对抗闭环` / `E07-派发` 呼叫异构模型进行双脑交叉会诊。
