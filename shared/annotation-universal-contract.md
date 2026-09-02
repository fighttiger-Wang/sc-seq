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

Every cluster receives a final annotation. In subcluster work, remain at the
requested sibling/leaf level: incomplete evidence triggers further sibling
comparison, exclusion review, and targeted literature research, not retreat to
the supplied parent. If ambiguity remains, report the most biologically
defensible same-level identity, the evidence gap, and a concrete validation
route.

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
not be decorated with cluster IDs or marker prefixes.

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
