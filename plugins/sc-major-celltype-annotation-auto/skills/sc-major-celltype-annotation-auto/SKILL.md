---
name: sc-major-celltype-annotation-auto
description: Expert-style major-celltype annotation for mixed/all-cell single-cell data using average expression, detection ratio, marker statistics, UMAP topology, tissue/species context, and versioned literature verification.
---

# Major cell-type annotation

Before making any annotation decision, apply the shared [universal annotation contract](../../../../shared/annotation-universal-contract.md). This skill adds the major-level rules below; it does not replace the shared evidence, UMAP, naming, or workbook QA requirements.

Use this skill only for mixed/all-cell collections. The complete table is
annotated at one major-celltype level; never refine only one lineage because its
markers are clearer. Candidate discovery may be open-ended, but final plotting
labels must use controlled, reusable names at one presentation level.

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
order, context, and UMAP audit. Deliver a timestamped Excel workbook to the
order, context, and UMAP audit. Deliver only the timestamped Excel workbook to
the supplied E-drive input directory. Internal evidence/QA JSON sidecars remain
in the E-drive workspace build directory and are not copied to the input
directory unless explicitly requested. Use the approved subcluster workbook as
the formatting baseline: Cambria 11, content-fit frozen columns, fixed long-text
widths, wrapping and shrink-to-fit disabled, sample freeze panes, and red fill
`#F8696B` only on the Chinese-name cell.

### 交付目录纯净与环境调用硬约束 (Delivery Purity & Execution Integrity)
1. **数据目录绝对纯净**：交付件必须且仅允许包含时间戳 Excel 完整注释大表（及按需生成的 `cluster注释信息.xlsx` 简表）。严禁在用户输入数据目录下遗留 `build/`、`scratch/`、`*.json`、`*.py`、`*.qa.json` 等任何过程文件或调试脚本；所有分析计算必须在内存数据流中完成，或使用临时目录并在交付前彻底销毁。
2. **严禁跨项目扩散扫描**：执行过程中严禁使用通配符跳出当前输入路径，去全局递归遍历其他客户历史售后目录（如 `E:\Desktop\售后\*`），杜绝历史项目非标准命名造成的交叉污染及无谓耗时。
3. **环境调用一次到位**：使用预设的稳定 Python 运行时（`~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`），禁止递归全盘查找 Python 路径。

### 开放生物学发现与防负优化保证 (Open Discovery & Non-Degradation Guarantee)
1. **第一阶段纯数据驱动**：注释第一阶段始终基于当前样本自身的全基因组经验基石、连续拓扑流形与双向排他门控，绝对不退化为封闭白名单或死字典硬匹配。
2. **第二阶段文献缓存加速**：内置文献与命名库仅作为成熟通用细胞类型的第二阶段免检索加速池，绝不对陌生、罕见、病理或非模式生物细胞类型行使否决权；面对未知特化程序，完整保留数据驱动特征，触发靶向学术检索或恪守科学诚实原则客观披露待实验验证状态，守护 100% 注释准确性。

Never output generic `Cell`, silently discard a cluster, use one marker or one
UMAP location as sole proof, or claim confirmed doublet from aggregate evidence.
