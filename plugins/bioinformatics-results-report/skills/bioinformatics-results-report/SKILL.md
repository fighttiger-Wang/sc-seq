---
name: bioinformatics-results-report
description: Interpret completed bioinformatics result folders containing tables, figures, and notes, then generate a literature-grounded, self-contained HTML report. Use only when explicitly invoked for cell proportion/ROE, differential expression, GO/KEGG/GSEA/GSVA, cell communication, or pseudotime results; do not use it to recalculate statistics or analyze Seurat/Scanpy objects.
---

# Bioinformatics Results Report

Turn an existing result folder into a professional Chinese HTML report while preserving the statistical claims actually present in the supplied results.

## Boundaries

- Read completed `.xlsx`, `.csv`, `.tsv`, `.png`, `.jpg`, `.jpeg`, `.pdf`, `.txt`, `.md`, and `.docx` outputs.
- Do not open Seurat/Scanpy objects, rerun pipelines, recompute tests, invent missing contrasts, or upgrade descriptive patterns to statistical significance.
- Treat user notes as hypotheses or context, not ground truth. Resolve their claims against the supplied tables and figures.
- Default to Chinese prose; retain gene, pathway, ligand-receptor, method, and necessary technical names in English.
- Do not add client branding, logos, or identifying customer metadata.
- Never upload file contents, sample identifiers, tables, or figures to an external service. Literature queries may contain only scientific concepts such as disease, tissue, species, cell type, gene, pathway, or method.

## Workflow

1. Verify the input is an E-drive result folder. Resolve the shared workspace from `CODEX_SHARED_WORKSPACE_ROOT`, or from the parent of the marketplace containing `skill-pack.json`; keep temporary files in its `tmp` directory and write only the final validated report back to the input folder.
2. Run `scripts/inventory_results.py <folder>` and inspect the original files needed to understand their contents. Exclude prior HTML reports from scientific evidence.
3. Identify the supported analysis modes present. Read only the corresponding analysis references listed below, plus the shared intake and visual references.
4. Ask for missing study background, species/tissue, group meanings, sample counts, and key clinical or experimental variables. Ask one short question at a time; do not require a project template.
5. Before analysis, show the inferred groups, sample counts, file purposes, available contrasts, and planned report coverage. Wait for explicit user confirmation.
6. If sample counts, group labels, comparison directions, significance labels, or figure/table annotations conflict, pause and resolve one contradiction at a time. Do not generate around a known inconsistency.
7. Interpret existing statistics only. Use exact direction, effect size, and adjusted significance fields when supplied. If only a plot or summary value exists, describe it as a visual or descriptive pattern.
8. Search for literature supporting the biological interpretation. Prefer peer-reviewed work from the past five years, authoritative guidelines, and necessary older landmark studies. Put a short `author–year / journal` link beside important claims. Do not create a traditional reference list unless requested.
9. If literature search is unavailable or evidence is insufficient, continue but write the affected statement explicitly as `未获文献验证的机制推测`. Literature support never converts association into causality.
10. Select figures that advance the scientific storyline. Put essential figures in the main narrative; omit redundant or decorative images rather than creating an image pile.
11. Draft a report specification following `references/report-schema.md`. Distinguish evidence levels through wording: `结果显示` for direct data, `结合既往研究，可能反映` for literature-informed interpretation, and `推测/尚需验证` for unsupported mechanisms.
12. Run `scripts/render_report.py` to create a versioned, non-overwriting, self-contained HTML in the source result folder. Use the project-neutral shell in `assets/report-shell.html`; never copy content from an earlier project into a new report.
13. Run `scripts/validate_report.py` on the output. Then visually inspect the rendered page for overflow, image distortion, table usability, navigation, focus behavior, mobile layout, and contrast. If browser inspection is unavailable, state `仅完成静态检查，视觉质检未完成`.

## Required Report Layers

Every report should contain, when evidence is available:

- a concise core summary for mixed audiences;
- a professional results narrative organized by scientific question;
- biological mechanisms tied to supplied evidence and linked literature;
- potential clinical or translational meaning without overclaiming;
- limitations, inconsistencies, and evidence gaps.

The visual language is fixed but the section structure is adaptive: light gray page, navy hierarchy, fixed left contents on desktop, white cards, original scientific figure colors, restrained progress indication, active-section navigation, and accessible image enlargement. Do not introduce dark dashboards, glow, gradients, recolored scientific images, or hero image stacks.

## Analysis Routing

- Always read [intake and evidence rules](references/intake-and-evidence.md).
- For cell proportions or ROE, read [proportion and ROE](references/proportion-roe.md).
- For differential expression, read [differential expression](references/differential-expression.md).
- For GO, KEGG, GSEA, or GSVA, read [enrichment](references/enrichment.md).
- For CellChat, NicheNet, ligand-receptor, or related outputs, read [cell communication](references/cell-communication.md).
- For pseudotime, trajectories, branches, or dynamic genes, read [trajectory](references/trajectory.md).
- Before drafting the JSON specification, read [report schema](references/report-schema.md).
- Before rendering or changing the shell, read [visual system](references/visual-system.md).

## Completion Gate

Do not call the report complete unless the input confirmation occurred, contradictions were resolved, scientific claims remain within the supplied statistical evidence, citations are clickable where used, the output is a single HTML file with embedded figures/styles/scripts, the source directory was not overwritten, and validation results plus any browser-QA gap are reported truthfully.
