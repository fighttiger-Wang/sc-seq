---
name: single-cell-qc-image-display
description: Create centralized Excel workbooks and presentation-ready PNG overview images from structured single-cell RNA-seq QC data. Use when the user asks to turn single-cell QC tables into a large display image, export the table to Excel, update the table/image with added project fields such as tissue digestion protocol, or reuse the previous single-cell QC table-and-image template for new LC projects and sample-level metrics.
---

# Single Cell QC Image Display

## Purpose

Use this skill to turn extracted single-cell QC project information into two deliverables:

- an Excel workbook with one row per Sample and an optional project overview sheet
- a wide PNG display image with summary cards and the full detailed table

Use it after project metadata and screenshot metrics have already been extracted. If extraction is still needed, first use the single-cell QC extraction workflow, then use this skill for output.

## Data Shape

Prefer one row per Sample. Repeat project-level fields on each sample row.

Default columns:

1. 项目号
2. 客户名
3. 组学方案
4. 实验物种
5. 样本数
6. 测序量
7. 组织
8. 组织消化方案
9. 预期捕获细胞数
10. 关注细胞类型
11. 实验前细胞状态质控
12. 服务范畴
13. Sample
14. Estimated number
15. Mean reads per cell
16. Mean genes per cell
17. Reads mapped to genome
18. Sequencing saturation
19. Cell type

Leave unavailable values as empty strings. Do not invent `NA`.

For full input JSON details, read `references/input-schema.md`.

## Workflow

1. Build a structured JSON object from the current table or user-provided information.
2. Use project ID as the stable grouping key.
3. Add or update project-level columns, such as `组织消化方案`, by matching `项目号`.
4. Keep all sample-level metrics in the same row as `Sample`.
5. Run `scripts/render_single_cell_qc_outputs.py` to create Excel and PNG outputs.
6. Verify the script summary reports the expected row count and output paths.
7. If the PNG is too wide or crowded, rerun with a shorter title/subtitle or reduce the displayed columns only if the user asks for a simplified image.

## Script Usage

Use the bundled script when possible:

```bash
python3 scripts/render_single_cell_qc_outputs.py input.json --output-dir outputs/single-cell-qc-table --basename single-cell-qc-projects
```

The script requires `Pillow` and `openpyxl`. In Codex desktop, prefer the bundled Python runtime if available.

Outputs:

- `<basename>.xlsx`
- `<basename>-big-image.png`

## Visual Rules

- Use a factual programmatic table image, not a generated AI image, so Chinese text and numbers remain exact.
- Put a short title and subtitle at the top.
- Add summary cards for project count, sample count, filled digestion-protocol count, species, and sequencing volume when these fields exist.
- Color project IDs consistently so repeated sample rows from the same project are easy to scan.
- Keep long text wrapped inside cells, especially `组织消化方案`, `关注细胞类型`, and `Cell type`.
- Mention any intentionally blank project-level fields after output, for example when a digestion protocol was not captured.

## Excel Rules

- Freeze the header row.
- Apply filters to the full table.
- Use one sheet named `单细胞QC汇总`.
- Add a `项目概览` sheet when project-level fields can be summarized.
- Keep numeric QC fields numeric where possible and percent fields as visible strings if they already include `%`.

## Update Pattern

When the user adds a new column or correction:

1. Patch the JSON data by project ID or Sample.
2. Regenerate both Excel and PNG so the two outputs stay synchronized.
3. Keep previous output files only if useful; otherwise create a new basename that describes the update, such as `single-cell-qc-projects-with-digestion`.
