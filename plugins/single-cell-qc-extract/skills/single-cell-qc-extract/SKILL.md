---
name: single-cell-qc-extract
description: Extract structured single-cell RNA-seq project QC information from Chinese project descriptions and screenshots/images of Cell Ranger, Seurat QC, clustering, and cell-type annotation reports. Use when the user provides project text containing contract/project metadata such as LC project IDs, customer names, species/sample counts, tissue, sequencing volume, expected captured cells, QC status, service scope, plus images containing Sample-level metrics like Estimated number of cells, Mean reads per cell, Mean genes per cell, Reads mapped to genome, Sequencing saturation, and Cell type annotations.
---

# Single Cell QC Extract

## Workflow

1. Parse the project description first. Extract project-level fields before reading images:
   - Project ID: patterns like `LC-X20260302026`.
   - Customer name: the segment after the project ID in the title, often Chinese.
   - Omics plan: the title segment describing the assay, for example `单细胞转录组(华大C4)-定制分析项目`.
   - Species and sample count: parse tokens such as `小鼠_3`; keep species and sample count separately.
   - Sequencing volume: parse suffixes such as `100g` or `100G`.
   - Tissue: parse `组织来源：【...】`.
   - Expected captured cells: parse `预期捕获细胞数：...`.
   - Concerned cell type: parse `关注：...`; `无` means no concerned cell type.
   - Pre-experiment cell QC: parse statuses such as `合格上机`.
   - Service scope: parse statuses such as `分析项目`.
   - Analysis path: preserve the full path if provided.

2. Inspect each provided image. Extract only visible values; do not infer hidden rows or columns.
   - From Cell Ranger/summary tables, capture by `Sample`: `Estimated number of cell`, `Mean reads per cell`, `Mean genes per cell`, `Reads mapped to genome`, and `Sequencing saturation`.
   - From annotation tables, capture by `Sample`: `Cell type` exactly as shown, preserving percentages and cell-type order.
   - If a sample appears in one image but not another, keep the sample row and leave missing fields blank.
   - Ignore plots unless they contain text labels needed for `Cell type` or sample names.

3. Produce a single tidy table with one row per sample when sample-level metrics are present. Repeat project-level fields on each sample row.

4. Leave unrecognized or unavailable values blank. Do not write guesses such as `NA` unless the source explicitly says `NA`.

5. Mention any uncertainty briefly after the table, especially when values were read from a low-resolution screenshot.

## Output Fields

Use the schema in `references/output-schema.md` when exact column names matter.

Prefer Chinese table headers for user-facing responses unless the user asks for English. Preserve original metric names in parentheses when helpful.

## Image Reading Notes

- Read screenshots manually if the values are legible in the prompt.
- If local image files are available but the embedded preview is unclear, use image viewing/OCR tools to zoom or inspect them.
- Keep commas and percent signs exactly as shown.
- For sample identifiers, preserve case and underscores exactly, for example `D807_D811_CCM`.

