# Delivery purity, open discovery and workbook formatting

> 本文件由 SKILL.md 原文逐行下沉（verbatim）；文中 `references/...` 链接均相对 skill 根目录（SKILL.md 所在目录）。

Record versions, hashes, counter, source paths, cluster order, parent context,
and the full UMAP audit. Formal delivery requires the fixed four-sheet workbook (`注释与详细证据`, `细胞配色`, `细胞类型与文献`, `说明与数据来源`),
an independently generated `--umap-facts` artifact whose image hash matches the
supplied UMAP, and a hash-matching passing QA sidecar in the workspace build
location; historical five-sheet workbooks are read-only validation inputs only (never generate a new five-sheet workbook). Deliver only the timestamped Excel workbook and
the companion cluster reference table (`cluster注释信息.xlsx`) to the supplied E-drive input directory,
and keep QA JSON sidecars in the workspace unless the user explicitly asks for them. Do not automatically edit or filter
the underlying object.

### 交付目录纯净与环境调用硬约束 (Delivery Purity & Execution Integrity)
1. **交付文件规范与数据目录绝对纯净**：交付件**固定且仅允许保留两份表格**：
   - **时间戳完整亚群注释大表**：`{project_name}_亚群注释结果_{YYYYMMDD_HHMMSS}.xlsx`（4-sheet 标准版：注释与详细证据、细胞配色、细胞类型与文献、说明与数据来源，遵循格式契约）。
   - **简明对应关系表**：`cluster注释信息.xlsx`（固定包含 `Cluster`, `Celltype_EN`, `中文名称` 3列，自适应列宽，无筛选，冻结首行，专供下游快速查阅与对接制图）。
   - **严禁输出无时间戳的大表副本**（杜绝 `{project_name}_亚群注释结果.xlsx` 同名无时间戳冗余大表，避免客户混淆）。
   - **过程文件零残留**：严禁在用户输入数据目录下遗留 `build/`、`scratch/`、`*.json`、`*.py`、`*.qa.json` 等任何过程文件或调试脚本；所有分析计算必须在内存数据流中完成，或使用临时目录并在交付前彻底销毁。
2. **严禁跨项目扩散扫描**：执行过程中严禁使用通配符跳出当前输入路径，去全局递归遍历其他客户历史售后目录（如 `E:\Desktop\售后\*`），杜绝历史项目非标准命名造成的交叉污染及无谓耗时。
3. **环境调用一次到位**：使用预设的稳定 Python 运行时（`~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`），禁止递归全盘查找 Python 路径。

### 开放生物学发现与防负优化保证 (Open Discovery & Non-Degradation Guarantee)
1. **第一阶段纯数据驱动**：亚群注释第一阶段始终基于局部空间重归一化（Local Renormalization）、微模块残差评估（Micro-module Residuals）、连续流形与父群谱系树硬门控，绝对不退化为封闭白名单或死字典硬匹配。
2. **第二阶段文献缓存加速**：内置文献与亚型命名库仅作为成熟通用亚型的第二阶段免检索加速池，绝不对特定组织特化亚型、过渡态、活化态或罕见亚群行使否决权；面对未知微模块程序，完整保留数据驱动特征，触发靶向学术检索或恪守科学诚实原则客观披露待实验验证状态，守护 100% 亚群注释精细度与准确性。

Workbook formatting is part of the delivery contract. Use Cambria 11 as the
workbook font. Save content-fit column widths/row heights for `绘图列表`, for
frozen columns A:C in `注释结果`, for frozen columns A:C in `详细证据`, and for
frozen column A in `细胞类型与文献`; keep long text columns at fixed widths with
wrapping and shrink-to-fit disabled. In `细胞类型与文献`, the visible hyperlink
text in `文献` must show DOI/PMID identifiers when available, not the article
title, while preserving the clickable link.
