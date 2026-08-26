---
name: bioinformatics-results-report-classic
description: Interpret completed bioinformatics result folders and generate a literature-grounded, self-contained Chinese HTML report in a centered classic scientific-document layout. Use for cell proportion/ROE, differential expression, enrichment, cell communication, or pseudotime results when a paper-like report is preferred; do not use for statistical recalculation or Seurat/Scanpy object analysis.
---

# Bioinformatics Results Report — Classic Document Layout

Turn a completed local result folder into a professional Chinese report without exceeding the statistical evidence supplied by the user. The defining presentation is a centered, paper-like scientific document rather than a dashboard.

## Non-negotiable boundaries

- Read completed `.xlsx`, `.csv`, `.tsv`, `.png`, `.jpg`, `.jpeg`, `.pdf`, `.txt`, `.md`, and `.docx` outputs.
- Do not open Seurat/Scanpy objects, rerun pipelines, recompute statistics, invent missing contrasts, or upgrade descriptive patterns to significance.
- Treat notes and filenames as context, not ground truth. Resolve claims against machine-readable tables and figure annotations.
- Default to Chinese prose; retain gene, pathway, ligand-receptor, method, and necessary technical names in English.
- Do not add client branding, logos, or identifying customer metadata.
- Never upload file contents, sample identifiers, tables, or figures to an external service. Literature queries may contain only scientific concepts such as disease, tissue, species, cell type, gene, pathway, or method.
- Keep intermediate inventories and specifications in the approved shared workspace. Write only a new versioned final HTML to the result folder; never overwrite source files or an earlier report.

## Execution

1. Verify the user-supplied local folder, resolve a writable shared workspace, and run `scripts/inventory_results.py <folder>`. Prior HTML reports are never scientific evidence.
2. Read [intake and evidence rules](references/intake-and-evidence.md), then only the analysis references matching the inventory. Inspect the original tables, legends, notes, and figures needed to establish comparison direction and evidence strength.
3. Present one compact confirmation brief covering study context, species/tissue, groups and sample counts, statistical unit, comparison directions, file roles, exclusions, and planned coverage. Mark unknowns explicitly and ask one consolidated confirmation question. Do not repeat this checkpoint if the user already confirmed the same facts in the current task.
4. If a material contradiction remains, pause and resolve one contradiction at a time. Do not generate around conflicting sample counts, group meanings, directions, significance labels, or figure/table annotations.
5. Build an evidence ledger for every major conclusion: direct source file/table or figure, comparison, direction/effect, significance basis, evidence level, and nearby literature support. Interpret exact adjusted significance and effect fields when available; otherwise use descriptive wording.
6. Search recent peer-reviewed literature, authoritative guidance, and necessary landmark studies using scientific concepts only. Put short clickable `author–year / journal` citations beside supported interpretation. Label unsupported mechanisms exactly `未获文献验证的机制推测`.
7. Select only figures that advance the scientific storyline. Preserve their original palette, labels, aspect ratio, and scientific meaning.
8. Read [report schema](references/report-schema.md) and [visual system](references/visual-system.md), draft a fresh JSON specification, and render with `scripts/render_report.py`. Do not reuse prose or specifications from another project.
9. Run `scripts/validate_report.py`, then inspect desktop and mobile rendering, print layout, table/figure overflow, image enlargement, focus behavior, contrast, and citations. If browser inspection is unavailable, report `仅完成静态检查，视觉质检未完成`.

## Required Report Layers

Every report should contain, when evidence is available:

- a concise core summary for mixed audiences;
- a professional results narrative organized by scientific question;
- biological mechanisms tied to supplied evidence and linked literature;
- potential clinical or translational meaning without overclaiming;
- limitations, inconsistencies, and evidence gaps.

Organize the professional narrative by scientific question or contrast, not by file name. Keep direct data, literature-informed interpretation, and unresolved hypotheses visibly distinguishable through wording and source notes.

The visual language is fixed but the section structure is adaptive: a centered white scientific document, burgundy chapter hierarchy, restrained gray section bands, traditional bordered tables, original scientific figure colors, an in-flow contents block, and accessible image enlargement. Do not introduce a fixed sidebar, dashboard KPI styling, dark themes, glow, gradients, recolored scientific images, or decorative hero stacks.

## Analysis routing

- For cell proportions or ROE, read [proportion and ROE](references/proportion-roe.md).
- For differential expression, read [differential expression](references/differential-expression.md).
- For GO, KEGG, GSEA, or GSVA, read [enrichment](references/enrichment.md).
- For CellChat, NicheNet, ligand-receptor, or related outputs, read [cell communication](references/cell-communication.md).
- For pseudotime, trajectories, branches, or dynamic genes, read [trajectory](references/trajectory.md).
- Before drafting the JSON specification, read [report schema](references/report-schema.md).
- Before rendering or changing the shell, read [visual system](references/visual-system.md).

## Completion gate

Do not call the report complete unless the confirmation checkpoint occurred, material contradictions were resolved, core claims are traceable to supplied evidence, citations are clickable where used, the output is one versioned HTML with embedded figures/styles/scripts, source files were not overwritten, static validation passed, and any visual-QA gap is reported truthfully.
