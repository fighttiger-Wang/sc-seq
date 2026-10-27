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

The final Excel workbook contains exactly these sheets in this order:

1. `绘图列表`
2. `注释结果`
3. `详细证据`
4. `细胞类型与文献`
5. `说明与数据来源`

`绘图列表` contains exactly `Cluster` and `Celltype_EN`. `注释结果`,
`详细证据`, and `绘图列表` contain every cluster, use exact cluster-ID joins,
and share numeric ascending order followed by natural alphanumeric order.
Repeated labels are allowed. `Celltype_EN` must match `[A-Za-z0-9_]+` and must
not be decorated with cluster IDs or marker prefixes. State, program,
disease-role, and topology qualifiers remain in dedicated fields and must not
be concatenated into `Celltype_EN`. A shortened professional name is permitted
only when it is a recognized naming-dictionary abbreviation and receives
explicit expert naming approval.

The result sheet contains no score or confidence field. The evidence sheet has
one row per cluster and includes the final identity, parent context, primary and
competing programs, supporting/conflicting/missing markers, qualitative gates,
off-parent audit, state/development evidence, UMAP audit, mixed/doublet
interpretation, rationale, gaps, and handling.

Marker evidence is rendered as, for example:

```text
FGFBP2(mean=4.67, ratio=70.20%, log2FC=1.74, pct.1=70.20%, pct.2=14.30%)
```

`细胞类型与文献` contains exactly `细胞类型`, `文献`, `经典鉴定 Marker`,
and `本次鉴定使用的 Marker`. One cell type x one reference is one row, cells
are not merged, every final type has at least one source, and links are
clickable. `说明与数据来源` contains `项目 | 内容`, displays filenames only,
and records context, modes, metric definitions, versions, run time,
constraints, sorting/red-fill rules, limitations, and the no-auto-modification
declaration.

Use fixed widths and fixed row heights. Disable wrapping, shrink-to-fit, and
autofilters so long text stays intact but is visually clipped and remains
available in the formula bar. Freeze the first row in every sheet; additionally
freeze the first three columns in `注释结果` and `详细证据`, and the first column
in `细胞类型与文献`.

Apply a static red background only to the `中文名称` cell when a cluster carries
a coherent significant state program, `Multi_cell`, suspected doublet,
low-quality/debris/background interference, or lineage/off-parent boundary.
One isolated state marker does not trigger red fill.
