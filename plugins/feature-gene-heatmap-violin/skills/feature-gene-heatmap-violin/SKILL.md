---
name: feature-gene-heatmap-violin
description: Create the finalized single-cell full-marker feature-gene heatmap and selected-gene violin panel from a Seurat object and marker table. Use when users ask for 特征基因热图, marker热图, 全marker热图, 指定基因小提琴图, violin plots, or want the fixed publication-style heatmap/violin workflow developed for bone-marrow B-cell data.
---

# 1_特征基因热图及选定基因小提琴图

Use the bundled script to generate exactly one final heatmap and one final violin panel. Do not create iterative `v1`, `v2`, or exploratory figure variants unless the user explicitly requests them.

## Required inputs

- A Seurat `.rds`, `.rda`, or `.RData` object.
- A marker `.csv` or `.xlsx` table containing `cluster` and `gene`; use `avg_log2FC`/`avg_logFC` and `p_val_adj` when present.
- A cluster metadata column, normally `seurat_clusters`.
- Optional existing cell-type metadata column. If absent, infer cluster-to-cell-type mapping from marker signatures.
- Selected violin genes. Default to `PAX5,EBF1,IL7R,RAG1,RAG2,DNTT`.
- Optional reference cell type for Wilcoxon comparison. If absent or invalid, select the group with the highest mean selected-gene expression.

## Workflow

1. Keep original inputs read-only. On Windows, stage copies under an E-drive working directory when required by local policy. On macOS/Linux, use a user-approved writable workspace. Prefer short ASCII staging names only when the local R runtime cannot handle the original path.
2. Inspect the Seurat object and marker-table columns before running.
3. Run `scripts/plot_feature_gene_heatmap_violin.R` once with explicit arguments.
4. Verify both PNG files visually. Confirm that labels, color blocks, guide lines, legend, and violin colors render correctly.
5. Return only the final output directory and the two final figures unless the user asks for implementation details.

```bash
Rscript scripts/plot_feature_gene_heatmap_violin.R \
  --seurat input/Plot.rData \
  --markers input/all_marker_gene.xlsx \
  --output Result \
  --cluster-column seurat_clusters \
  --celltype-column "" \
  --reference-celltype Pro_B \
  --violin-genes PAX5,EBF1,IL7R,RAG1,RAG2,DNTT
```

## Fixed visual contract

- Plot every unique positive marker gene in the heatmap, but label only the configured top representatives per cell type.
- Spread displayed gene labels across the x-axis and connect each label to its true gene column with leader lines.
- Sample a bounded number of cells per cell type for predictable memory use.
- Scale each heatmap gene across sampled cells, clip z-scores to `[-2, 2]`, and use blue-cream-red expression colors.
- Draw a narrow left cell-type annotation strip with small white gaps aligned to heatmap group separators.
- Place the expression legend in an independent lower-left row below all gene labels; never overlay it on labels or leader lines.
- Reuse the exact cell-type palette in every violin plot.
- Compare the reference cell type with all other cells using Wilcoxon rank-sum tests and BH-adjusted stars.

## Final outputs

- `feature_gene_heatmap.png` and `.pdf`
- `selected_gene_violin.png` and `.pdf`
- `run_summary.txt`
- `celltype_mapping.csv` only when annotation is inferred
- `violin_statistics.csv`

Treat missing required genes, empty cell groups, absent assays, and invalid metadata columns as hard errors with clear messages. Never silently substitute simulated data.
