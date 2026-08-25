---
name: kegg-flow-bubble-plot
description: Create publication-ready KEGG gene-pathway flow-bubble plots from enrichment result tables containing pathway names, hit genes, DEG counts, background counts, and FDR/Q values. Use when users request KEGG流泡图、基因-通路流线气泡图、桑基式富集气泡图、论文图4e/f样式重绘，或要求基因节点、通路节点、透明带状连接和富集气泡组合展示。
---

# KEGG Flow-Bubble Plot

Generate the fixed final style with `scripts/plot_kegg_flow_bubble.R`. Do not reconstruct the plot from earlier experimental scripts.

## Required input

Accept a tab-delimited KEGG enrichment table containing `Pathway_Name`, `IDs`, `S`, `TS`, and `Q.value`. Parse `IDs` as comma-separated genes and calculate `GeneRatio = S / TS`. Ignore optional up/down columns and never color gene nodes by regulation direction.

## Run workflow

1. Verify the current and output directories are in the user-approved writable workspace. Enforce the E-drive rule only on Windows hosts that use that local policy.
2. Copy the source enrichment table into the user-scoped output folder without modifying it.
3. On Windows, if R cannot read or write a non-ASCII path, stage the input and outputs in an ASCII-only E-drive directory, run there, then copy final artifacts back.
4. Run:

```bash
Rscript scripts/plot_kegg_flow_bubble.R <input.tsv> <output_dir> 6 20 "<comparison title>" <prefix>
```

5. Render the produced PDF to PNG and visually verify it before delivery.

Arguments after `output_dir` are optional: top pathway count, maximum displayed genes, plot title, and output prefix.

## Fixed visual specification

Preserve these defaults unless the user explicitly requests a change:

- Select the six smallest finite `Q.value` pathways; break ties by larger `GeneRatio`.
- Display at most 20 representative genes, prioritizing genes linked to more selected pathways.
- Give every gene a distinct curated color. Use fixed node width; never vary width.
- Set node height to `connection_count * slot_height`.
- Allocate one separate vertical slot to every gene-pathway link at both ends.
- Draw each link as a smooth ribbon exactly one slot high. Stacked ribbon height must equal node height.
- Use semi-transparent grey ribbons (`grey68`, alpha about `0.42`) so crossings become progressively darker.
- Sort link slots by the opposite node position to reduce unnecessary crossings.
- Place pathway names in the connection region without a background box; use moderately enlarged bold text.
- Use slightly enlarged regular-weight gene labels.
- Align each bubble exactly with its pathway node.
- Map bubble x-position to `GeneRatio`, size to `S`, and color to `-log10(FDR)`.
- Give bubbles a thin black outline and the bubble panel a black border.
- Do not draw grey horizontal grid lines inside the bubble panel.
- Keep tick labels and `Gene.Ratio` title separated.
- Place FDR and Count legends immediately beside the bubble-panel border.
- Export a horizontally compact, centered 300-dpi PNG and vector PDF with limited side whitespace.

## Output contract

Produce `<prefix>.png`, `<prefix>.pdf`, `<prefix>_selected_pathways.csv`, `<prefix>_gene_nodes.csv`, `<prefix>_link_slots.csv`, and `<prefix>_parameters.txt`.

## Validation checklist

- Confirm every ribbon endpoint occupies a distinct node slot.
- Confirm summed ribbon heights equal the corresponding node height.
- Confirm overlaps visibly darken while isolated ribbons remain light.
- Confirm node widths are identical.
- Confirm pathway labels do not have opaque backgrounds.
- Confirm bubble rows match pathway-node centers.
- Confirm axis labels, title, and legends do not overlap.
- Confirm the PDF renders without clipping, excessive left whitespace, or broken fonts.

If required columns are missing or no valid pathways remain, stop and report the exact issue rather than fabricating data.
