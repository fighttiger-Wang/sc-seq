# Output schema

The final workbook contains exactly these sheets in order:

1. `绘图列表`
2. `注释结果`
3. `详细证据`
4. `细胞类型与文献`
5. `说明与数据来源`

## 绘图列表

Exactly `Cluster | Celltype_EN`. `Celltype_EN` matches `[A-Za-z0-9_]+`.
Repeated labels are allowed and are not decorated with cluster IDs or Marker
prefixes. `Celltype_EN` is the expert-facing subcluster label. Preserve a
case-supported leaf even when its registered parent is also present elsewhere.
For a neutral contextual identity supported only by identity-like, state, or
program literature, append `_provisional`; this suffix discloses evidence
level and does not create a new ontology identity. If a repeated stable
identity has at least two distinct supported states across clusters, use
`<identity>_state_<state>` so the plotting map communicates the recorded
subcluster difference while internal `stable_id` remains unchanged.

## 注释结果

Columns:

1. Cluster
2. 中文名称
3. Celltype_EN
4. 下位亚类
5. 细胞谱系
6. 发育/成熟阶段
7. 细胞状态
8. 组织/疾病相关角色
9. 关键 Marker
10. 主要竞争候选
11. UMAP 判断摘要
12. 异常/边界标记
13. 可能组成
14. 判定摘要
15. 验证建议
16. 下游处理建议

`下位亚类` is an optional evidence-description field. It may contain a
case-supported lower-level subtype when the current evidence justifies one;
otherwise it remains blank. It does not replace `Celltype_EN`, does not enter
identity arbitration or UMAP resolution, and cannot be used to hide a supported
identity from the plotting mapping.

If a result contains both a registered parent and one of its registered
descendants, keep each cluster's evidence-bound identity in `Celltype_EN`.
Mixed depths are valid when they reflect real differences in evidence
resolution. Do not force a descendant back to the parent for visual uniformity.
If the final identity is a neutral bridge admitted from weak literature
semantics, use `<stable_id>_provisional` in `Celltype_EN`, retain the unsuffixed
identity internally, and preserve the qualified comparison and state in
`下位亚类` and `细胞状态`.

State qualification is a display operation only. Apply it only when one stable
identity is repeated and the current records contain at least two distinct,
non-empty states. Do not invent a state, add cluster IDs, or use a Marker name
as a substitute when no state distinction is supported.

The sheet contains no score, confidence, candidate rank, or numeric quality
field. `关键 Marker` contains gene symbols only.

## 详细证据

One row per cluster. Include final identity, parent context, primary and
competing programs, supporting/conflicting/missing Marker evidence, eight
qualitative gates, off-parent audit, development/state programs, UMAP and
cross-island audit, mixed/doublet explanation, rationale, evidence gaps,
validation, and handling.

The bound evidence record also retains `identity_arbitration` for every
applicable high-risk boundary: rule id, left/right program completeness,
resolution, binding action, and the explicit roles of absolute gates, state,
and topology. These fields support the written gate/rationale columns and are
not converted into a score or confidence value.

Available Marker values use:

```text
FGFBP2(mean=4.67, ratio=70.20%, log2FC=1.74, pct.1=70.20%, pct.2=14.30%)
```

Use `NA` for unavailable values. Do not infer zero without a verified complete
matrix.

## 细胞类型与文献

Exactly `细胞类型 | 文献 | 经典鉴定 Marker | 本次鉴定使用的 Marker`.
One cell type x one reference is one row. Do not merge cells. Every final type
has at least one reference with a clickable PMID, DOI, or URL when available.
The visible text in `文献` must be `DOI:<value>; PMID:<value>` when those
identifiers are known, falling back to the available identifier or URL only
when DOI/PMID is unavailable. Do not use the article title as the visible
hyperlink text.

## 说明与数据来源

Exactly `项目 | 内容`. Show filenames only. Record species, tissue, parent,
mode, metric definitions, versions, run time, constraints, sorting and red-fill
rules, limitations, and the no-auto-modification declaration.

## Shared QA

- All three Cluster sheets use the same numeric ascending order and exact IDs.
- Use Cambria 11 as the workbook font.
- Save concrete column widths/row heights rather than relying on future dynamic
  AutoFit rules. Apply content-fit sizing only to `绘图列表` all columns,
  frozen columns A:C in `注释结果`, frozen columns A:C in `详细证据`, and frozen
  column A in `细胞类型与文献`. Keep the long-text evidence/reference columns at
  fixed widths. Wrapping, shrink-to-fit, and autofilters are disabled.
- Freeze first row; freeze first three columns in result/evidence and first
  column in literature.
- Static red fill applies only to `中文名称` for coherent significant state,
  `Multi_cell`, suspected doublet, low quality, debris, background interference,
  or lineage/off-parent boundary.
- Every cluster receives a final annotation. Subcluster output cannot retreat to
  the supplied parent solely because evidence is incomplete.
- Every formal workbook is bound to its passing QA sidecar by SHA-256 in the
  workspace build location. The delivery copier rechecks sheet order, headers,
  freeze panes, fixed row heights, no-wrap/no-filter formatting, red-fill
  location, and the hash; old four-sheet or QA-unbound workbooks cannot be
  copied as formal output. Final delivery copies only the `.xlsx` workbook to
  the original data directory; QA JSON sidecars stay in the workspace unless
  the user explicitly asks for them.
