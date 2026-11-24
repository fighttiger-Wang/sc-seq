### 自底向上四阶段注释与层级协调架构 (Four-Phase Bottom-Up Annotation Framework)

在执行全细胞/混合谱系大类注释时，强制采用自底向上归纳注释流水线：

1. **第一阶段：全谱系无拘微观探底 (Micro-level Discovery via Open-World Evidence)**
   - **数据第一性原理驱动**：不预设宏观大类限制，结合全基因组背景、DE Marker 统计、检测率（`pct.1/pct.2`）、连续 UMAP 拓扑及全球开放顶刊学术文献，将全表每个 Cluster 直接探底注释到证据充分的最细稳定生物学叶实体（Leaf Identity）。
   - **三轨正交分离**：严格将【谱系身份 (Identity)】、【功能状态 (State: 增殖、缺氧、激活)】与【技术异常 (Abnormality: 碎片、双细胞嫌疑)】分轨记录，状态与技术标记绝不侵占主干身份。

2. **第二阶段：全景层级拓扑审计 (Panoramic Hierarchy & Topology Audit)**
   - 在全员微观身份确立后，从全局高度审视全部 Cluster：
     - **组织实质属性判定**：区分常规多系统复合器官（如肺、肾、肝，包含保守的间质/内皮/免疫微环境）与高度特化实质器官（如视网膜、睾丸、垂体）。
     - **谱系切面对等性检查**：检查各大分支的细分深度是否对等，识别是否存在“某一谱系大部粗化而个别离岛跳级”的父子混淆隐患。

3. **第三阶段：双向有界切面规约与投影 (Bounded Harmonization & Projection)**
   - **祖先-后代互斥定理 (Ancestor-Descendant Exclusion Theorem)**：在交付的主列 `Celltype_EN` 中，严禁出现互为祖先与后代的标签同台并列（如 `Epithelial_cell` 与 `Ciliated_cell` 严禁同列）。
   - **向上有界（锁死大类基石）**：间质分支死死锁定在成纤维、平滑肌、周细胞、间皮 4 大基石；免疫分支死死锁定在 T、B、NK、巨噬、单核等常规大类。**物理阻断向通用 `Stromal_cell` 或 `Immune_cell` 退化的大锅饭合并！**
   - **谱系内特化群规约**：当上皮分支内存在特化亚型（如纤毛、神经内分泌 PNEC），在大类交付时统一规约至主干大类（`Epithelial_cell`），其高分辨率微观特征 **100% 完整保留在 `State`、`Key Markers` 与 `Rationale` 列（零信息损失）**。
   - **外周独立实体保护**：对于软骨细胞（`ACAN+/COL2A1+`）、雪旺细胞（`SOX10+/MPZ+`）或造血祖细胞等独立于四大主干系统的边缘大类，依据特异 Marker 赋予独立大类身份，绝不削足适履硬塞给成纤维或上皮。

4. **第四阶段：契约交付与硬拦截把关 (Contract Delivery & Hard Assertion)**
   - 校验器内置数学断言：严禁祖先与后代标签在 `Celltype_EN` 列同台并列；一旦冲突直接抛出致命异常（Fatal Error）并中断构建，杜绝带病表格流向客户。
   - 交付表格严格遵循契约：5-sheet 分层完整大表（Cambria 11，冻结窗格，禁用自动换行，固定 24pt 行高，浅红警示标色）与标准 3 列简表（`Cluster`, `Celltype_EN`, `中文名称`），数据目录过程文件零残留。
