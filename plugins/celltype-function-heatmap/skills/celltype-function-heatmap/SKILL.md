---
name: celltype-function-heatmap
description: Create exactly two finalized cell-type function gene-expression heatmaps from cell-type and cell-type-by-sample matrices, a gene-module table, and a cell-type color table. Use when users request the fixed epithelial-style heatmap layout with aligned top annotations, centered vertical cell-type labels, right-side gene module blocks, preserved orders, and no clustering.
---

# 细胞类型功能基因热图

Use the bundled R script as the single source of drawing logic. Do not recreate the layout manually or generate exploratory variants unless the user explicitly asks for them.

## Inputs

Read [references/input-contract.md](references/input-contract.md) when preparing or validating inputs. Required inputs are:

- one gene-by-cell-type TSV matrix;
- one gene-by-cell-type-and-sample TSV matrix;
- one Excel gene-module table;
- one Excel cell-type color/order table;
- one YAML parameter file based on [assets/parameters.template.yaml](assets/parameters.template.yaml).

Keep source annotations unchanged. Use `celltype_order` verbatim when it is present; otherwise use `Plot_Order`, then source row order. Use `module_names` only as display labels and keep genes in workbook row/order. Apply gene aliases only when explicitly listed in YAML. Exclude only cell types listed in `exclude_celltypes`.

## Run

Copy the parameter template into a user-approved writable project directory, edit only its values, then run:

```bash
Rscript scripts/draw_celltype_function_heatmaps.R /absolute/or/relative/parameters.yaml
```

Relative paths in YAML resolve from the YAML file directory. The script requires R packages `readxl`, `openxlsx`, `ggplot2`, `patchwork`, `yaml`, `stringr`, and `scales`. Treat missing packages or invalid schemas as hard errors; never substitute simulated data.

## Fixed output contract

Generate exactly two main figures in `<output_dir>/final`:

- `01_all_celltypes.png` and `.pdf`: every retained cell type, no sample split;
- `02_sample_blocks.png` and `.pdf`: all samples in source encounter order, each repeating the same cell-type order.

Also write the two plotted matrices as TSV, `QA_summary.xlsx`, and `run_summary.txt`.

The visual contract is fixed:

- rows follow workbook module and gene order; columns follow explicit `celltype_order` (or the color-table order when no override is provided);
- no row or column clustering;
- expression colors are blue-white-magenta with symmetric clipping;
- top labels, annotation bars, and heatmap share one layout grid;
- cell-type labels are vertical 90 degrees, enlarged, centered over their color blocks, and long labels wrap at underscore boundaries without changing their characters;
- sample and cell-type annotation bars are one heatmap-row high;
- gene names are written on right-side module color blocks aligned to heatmap rows;
- the right module block width is measured from the longest rendered gene name;
- module boundaries use subtle white horizontal gaps; black separator lines are forbidden;
- do not split gene modules into separate figures.

## Verification

After the run:

1. Confirm all checks in `QA_summary.xlsx` are `TRUE`.
2. Confirm the final directory contains exactly two PNG and two PDF main figures.
3. Visually inspect both PNGs at full size.
4. Render page 1 of each PDF with Poppler and confirm it matches the PNG layout: top labels centered over color blocks, top and body columns aligned, right gene labels uncropped, and no black separator lines.
5. Return only the final directory and the two main figures unless implementation details are requested.
