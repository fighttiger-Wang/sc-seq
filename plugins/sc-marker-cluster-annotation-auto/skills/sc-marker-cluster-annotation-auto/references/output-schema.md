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
prefixes.

## 注释结果

Columns:

1. Cluster
2. 中文名称
3. Celltype_EN
4. 细胞谱系
5. 发育/成熟阶段
6. 细胞状态
7. 组织/疾病相关角色
8. 关键 Marker
9. 主要竞争候选
10. UMAP 判断摘要
11. 异常/边界标记
12. 可能组成
13. 判定摘要
14. 验证建议
15. 下游处理建议

The sheet contains no score, confidence, candidate rank, or numeric quality
field. `关键 Marker` contains gene symbols only.

## 详细证据

One row per cluster. Include final identity, parent context, primary and
competing programs, supporting/conflicting/missing Marker evidence, eight
qualitative gates, off-parent audit, development/state programs, UMAP and
cross-island audit, mixed/doublet explanation, rationale, evidence gaps,
validation, and handling.

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

## 说明与数据来源

Exactly `项目 | 内容`. Show filenames only. Record species, tissue, parent,
mode, metric definitions, versions, run time, constraints, sorting and red-fill
rules, limitations, and the no-auto-modification declaration.

## Shared QA

- All three Cluster sheets use the same numeric ascending order and exact IDs.
- Fixed widths and row heights; wrapping, shrink-to-fit, and autofilters are
  disabled.
- Freeze first row; freeze first three columns in result/evidence and first
  column in literature.
- Static red fill applies only to `中文名称` for coherent significant state,
  `Multi_cell`, suspected doublet, low quality, debris, background interference,
  or lineage/off-parent boundary.
- Every cluster receives a final annotation. Subcluster output cannot retreat to
  the supplied parent solely because evidence is incomplete.
- Every formal workbook is bound to its passing QA sidecar by SHA-256. The
  delivery copier rechecks sheet order, headers, freeze panes, fixed row
  heights, no-wrap/no-filter formatting, red-fill location, and the hash; old
  four-sheet or QA-unbound workbooks cannot be copied as formal output.
