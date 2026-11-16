---
name: sc-major-celltype-annotation-auto
displayName: A02 · 大类谱系注释 v0.9.1
description: A02 · 大类谱系注释 v0.9.1：跨全细胞或混合谱系自动完成大类注释、审计与原目录交付 Expert-style major-celltype annotation for mixed/all-cell single-cell data using average expression, detection ratio, marker statistics, UMAP topology, tissue/species context, and versioned literature verification.
---

# A02 · 大类谱系注释 v0.9.1

Before making any annotation decision, apply the shared [universal annotation contract](references/annotation-universal-contract.md). This skill adds the major-level rules below; it does not replace the shared evidence, UMAP, naming, or workbook QA requirements.

Use this skill only for mixed/all-cell collections. The complete table is
annotated at one major-celltype level; never refine only one lineage because its
markers are clearer. Candidate discovery may be open-ended, but final plotting
labels must use controlled, reusable names at one presentation level.

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
   - 交付表格严格遵循契约：4-sheet 完整大表（Cambria 11，冻结窗格，状态浅红标注）与标准 3 列简表（`Cluster`, `Celltype_EN`, `中文名称`），数据目录过程文件零残留。

## Inputs

Require species, tissue/organ, average-expression input, marker workbook, and a
UMAP PNG with readable cluster IDs and legend. The quantitative file has
`gene`, `group`, `mean_expr`, `expr_ratio`, and `norm_expr`; `expr_ratio` is
detection ratio. Marker statistics may include `Target_Cluster_mean`,
`Other_Cluster_mean`, `log2FC`, `pct.1`, and `pct.2`; interpret `pct.1/pct.2`
as target/background prevalence. Final output sorts numeric cluster IDs from small to large, then uses natural alphanumeric order for mixed IDs.

## Decision logic

For every cluster:

1. Build a dataset-wide background profile. Downweight programs elevated across
   most clusters, housekeeping/ribosomal/mitochondrial programs, and
   tissue-wide ambient signals. A globally elevated epithelial or immunoglobulin
   program must not redefine every cluster.
2. Evaluate coherent major programs with explicit qualitative gates using
   multiple anchors, relative specificity, mean expression, detection ratio,
   and competing-lineage exclusions. Preserve per-gene values, but never turn
   them into an aggregate score or ranking. `norm_expr` is secondary evidence.
3. Use species and tissue as facts. Do not treat inferred disease, treatment,
   age, sex, or anatomy as user-provided facts.
4. Treat marker tables as candidate discovery evidence. A high `log2FC` with
   low `pct.1` is a clue, not a decisive identity call.
5. Review every cluster on the full UMAP: same-type islands, interleaving,
   plausible transitions, neighboring lineages, and marker/UMAP conflicts.
   UMAP is a global consistency check, not a hard identity gate.
6. Resolve primary identity first, then separately classify
   `low_quality`, `background_interference`, `abnormal_state`, `debris`,
   `suspected_doublet`, and `mixed_population`; multiple flags may coexist.
7. If two incompatible programs are complete and competitive, retain the
   dominant identity when one clearly dominates; otherwise use `Multi_cell` and
   list concrete components. Aggregate evidence cannot prove same-cell
   coexpression.

## Open candidate discovery and controlled delivery

Do not use a closed ontology as a whitelist for biological discovery. Search
current species/tissue atlases and literature when a tissue-specific, transitional,
or naming-conflicted program is encountered. Before binding a final label, verify
that it is a stable, same-level major label; keep finer identity, synonyms,
parent compartment, alternatives, and unresolved interpretation in separate
fields. `Fibroblast_like` is not a default label: use `Fibroblast` when the
program is supported, and reserve `*_like` for a documented evidence gap.

Broad compartments may contain explicit branches. For example,
`Mesenchymal_stromal` may contain `Fibroblast`, `Decidual_stromal_cell`,
`Pericyte`, and `Vascular_smooth_muscle_cell`. Preserve the branch in
`Parent_compartment` or `细胞谱系` so the final label remains useful without
creating a false claim that all terms are identical in ontology depth.

## Output

Produce a cluster-level mapping with one stable plotting label per cluster.
Keep identity, parent compartment, optional finer identity, state, abnormality,
components, characteristic genes, UMAP judgment, evidence, literature, and
handling recommendation in separate fields. The finer-identity field is blank
when it merely repeats `Celltype_EN`; it is populated only when it adds a
supported lower-level interpretation. Do not create confidence or score fields.
For an impurity or non-pure plotting cluster, retain the most likely主体细胞类型
and mark its annotation cell red; do not replace the plotting identity with
`Doublet` or `Debris`.

Use the versioned naming dictionary. Established unambiguous abbreviations such
as `gdT` or `Tn` are allowed; short common labels such as B cell and T cell
remain full. Never mix a major label with a descendant subtype.

## Retrieval and reproducibility

This skill has an independent calibration counter. Its first five uses after
this skill/core/dictionary revision must verify involved types against current
literature and curated atlases. From use six onward retrieve only for
marker/context/UMAP conflicts or knowledge-base gaps. Record source, retrieval
date, species, tissue, defining program, exclusions, and adoption rationale.

Write a reusable data-specific evidence sheet listing involved types, markers,
definitions, and sources. Record versions, hashes, counter, input paths, cluster
order, context, and UMAP audit. Deliver only the timestamped Excel workbook and
the companion cluster reference table (`cluster注释信息.xlsx`) to the supplied E-drive input directory.
Internal evidence/QA JSON sidecars remain in the E-drive workspace build directory and are not copied
to the input directory unless explicitly requested. Use the approved subcluster workbook as
the formatting baseline: Cambria 11, content-fit frozen columns, fixed long-text
widths, wrapping and shrink-to-fit disabled, sample freeze panes, and red fill
`#F8696B` only on the Chinese-name cell.

### 交付目录纯净与环境调用硬约束 (Delivery Purity & Execution Integrity)
1. **交付文件规范与数据目录绝对纯净**：交付件**固定且仅允许保留两份表格**：
   - **时间戳完整注释大表**：`{project_name}_大类注释结果_{YYYYMMDD_HHMMSS}.xlsx`（4-sheet 标准版：注释与详细证据、细胞配色、细胞类型与文献、说明与数据来源，遵循格式契约）。
   - **简明对应关系表**：`cluster注释信息.xlsx`（固定包含 `Cluster`, `Celltype_EN`, `中文名称` 3列，自适应列宽，无筛选，冻结首行，专供下游快速查阅与对接制图）。
   - **严禁输出无时间戳的大表副本**（杜绝 `{project_name}_大类注释结果.xlsx` 同名无时间戳冗余大表，避免客户混淆）。
   - **过程文件零残留**：严禁在用户输入数据目录下遗留 `build/`、`scratch/`、`*.json`、`*.py`、`*.qa.json` 等任何过程文件或调试脚本；所有分析计算必须在内存数据流中完成，或使用临时目录并在交付前彻底销毁。
2. **严禁跨项目扩散扫描**：执行过程中严禁使用通配符跳出当前输入路径，去全局递归遍历其他客户历史售后目录（如 `E:\Desktop\售后\*`），杜绝历史项目非标准命名造成的交叉污染及无谓耗时。
3. **环境调用一次到位**：使用预设的稳定 Python 运行时（`~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`），禁止递归全盘查找 Python 路径。

### 开放生物学发现与防负优化保证 (Open Discovery & Non-Degradation Guarantee)
1. **第一阶段纯数据驱动**：注释第一阶段始终基于当前样本自身的全基因组经验基石、连续拓扑流形与双向排他门控，绝对不退化为封闭白名单或死字典硬匹配。
2. **第二阶段文献缓存加速**：内置文献与命名库仅作为成熟通用细胞类型的第二阶段免检索加速池，绝不对陌生、罕见、病理或非模式生物细胞类型行使否决权；面对未知特化程序，完整保留数据驱动特征，触发靶向学术检索或恪守科学诚实原则客观披露待实验验证状态，守护 100% 注释准确性。

Never output generic `Cell`, silently discard a cluster, use one marker or one
UMAP location as sole proof, or claim confirmed doublet from aggregate evidence.
