# Universal annotation contract

This contract is shared by major-celltype and subcluster annotation. The two
skills use different candidate vocabularies, but they must use the same
biological reasoning and workbook contract.

## Biological decision model

Annotation is a qualitative expert decision, not a score optimization task.
Never create or use an aggregate quality score, confidence grade, candidate
score, weighted sum, score margin, or ranked-candidate table.

For every cluster, evaluate the following items separately and record each
applicable gate as `通过`, `不通过`, `未确定`, or `不适用`:

1. identity-anchor program;
2. broader parent-lineage program;
3. sibling/competing identity programs;
4. explicit exclusion or incompatible programs;
5. tissue-relevant off-parent programs;
6. developmental and state programs;
7. UMAP neighborhood, continuity, repeated-label islands, and marker/topology
   agreement;
8. mixed-population, doublet, ambient-background, debris, and low-quality
   explanations.

Raw measurements remain evidence attached to individual genes. Preserve
available `mean_expr`, `expr_ratio`, `log2FC`, `pct.1`, and `pct.2`; use `NA`
when a value is absent and never infer zero unless a verified complete matrix
explicitly supports that interpretation. Do not collapse these measurements
into one number.

Identity anchors and coherent multi-gene programs have priority. A single
marker, one high average, a shared pan-lineage gene, or one state marker cannot
define identity. Evaluate positive and negative evidence together and keep
identity, development, state, abnormality, and handling as separate concepts.

Every cluster receives a gate-reviewed plotting decision. In subcluster work,
incomplete evidence triggers further sibling comparison, exclusion review, and
targeted literature research; it does not force a fine-grained subtype. A
parent-level, unresolved, provisional, manual-review, merge, or recluster
decision is valid when the expert plotting standard is not reached.

## Strict anti-lumping and fine-grained annotation mandate (严禁偷懒粗化合并与强制精细化命名规范)

In any single-cell annotation task (major cell types or subclusters), adopt the **Bottom-Up Four-Phase Framework (自底向上四阶段注释与层级协调架构)**:
1. **Phase 1: Full-Spectrum Micro-Discovery (第一阶段：全谱系无拘微观探底)**:
   Every cluster MUST first be explored to its finest, biologically authentic leaf identity supported by differential expression, detection prevalence (pct.1/pct.2), and open-world literature. Never lazily bundle clusters into broad parent labels during discovery. Strictly decouple lineage identity from functional state (cycling/stress) and technical artifacts.
2. **Phase 2 & 3: Panoramic Hierarchy Audit & Bounded Cut Harmonization (第二、三阶段：全景层级拓扑审计与双向有界切面规约)**:
   - **Ancestor-Descendant Exclusion Theorem (祖先-后代互斥定理)**: In any delivered label column (`Celltype_EN`), no primary label may be an ancestor or descendant of another primary label in the same table. A broad parent (e.g., `Epithelial_cell`) and its specialized child (e.g., `Ciliated_cell` or `Neuroendocrine_cell`) MUST NEVER coexist as primary peer labels.
   - **Bounded Upward Projection (向上有界锁死基石)**: Sibling peer lineages within organ systems (e.g., `Fibroblast`, `Smooth_muscle_cell`, `Pericyte`, `Mesothelial_cell` in stroma; `T_cell`, `NK_cell`, `B_cell`, `Macrophage`, `Monocyte` in immune; `Endothelial_cell`, `Lymphatic_endothelial` in endothelium) represent genuine anatomical peer cuts and MUST NEVER be coarsened into generic `Stromal_cell` or `Immune_cell`.
   - **Intra-lineage Cut Harmonization (谱系内特化群规约)**: When an epithelial compartment contains specialized sub-lineages (e.g., Ciliated, PNEC), all members are harmonized to the primary lineage cut (`Epithelial_cell`) in `Celltype_EN`, while their full micro-annotation (e.g., Ciliated, PNEC) is 100% preserved in the `state`, `key_markers`, and `rationale` columns (Zero Information Loss).
   - **Outlier Lineage Exception (外周特化实体保护)**: Distinct lineages (e.g., Chondrocytes `ACAN+/COL2A1+`, Schwann cells `SOX10+/MPZ+`, Mast cells `KIT+/CPA3+`) with >= 2 exclusive DE markers retain independent major lineage identity and are never merged into fibroblasts or macrophages.
3. **Phase 4: Subcluster Resolution Mandate (第四阶段：亚群注释禁止退回父级)**:
   In subcluster annotation (04 skill), within a declared parent population, every cluster must resolve to an intra-lineage sibling leaf. Retreating to the parent label in `Celltype_EN` is strictly prohibited.

## UMAP and mixed populations

Review every cluster on the complete UMAP. UMAP is mandatory consistency
evidence but never a standalone classifier. A disconnected repeated label,
boundary position, or marker/topology conflict requires an explicit audit.

Cluster-level averages may show competing programs but cannot prove same-cell
co-expression or doublets. Retain a clearly dominant identity. Use
`Multi_cell` only when no coherent program is dominant or supplied cell-level
evidence confirms multiple component populations. Never automatically delete,
filter, merge, or modify cells.

## Stable workbook contract

各技能的文档权威为各自的输出契约：

- A02：`sc-major-celltype-annotation-auto/references/output-schema.md`
- A03：`sc-marker-cluster-annotation-auto/references/output-schema.md`

工作表名称、顺序、列、样式与 QA 以对应的 `references/output-schema.md` 为准。
总览中每个不同的 `Celltype_EN` 在 `细胞类型与文献` 恰好占 1 行，展示 1 篇直接支持最终标签的代表作。
QC 或无直接文献时保留 1 行如实说明。其余候选文献保留在研究证据包中。
严禁合并单元格或对同一细胞类型拆分多行。

正式交付流程为 `build_annotation_workbook.py` → `copy_final_workbook.py`。
