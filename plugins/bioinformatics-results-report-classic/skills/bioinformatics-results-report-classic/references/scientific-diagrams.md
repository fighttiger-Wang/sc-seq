# Scientific diagram routing and quality gate

Use this reference only when the report requires a newly authored conceptual figure. Existing supplied scientific plots remain unchanged.

## Exact specialist-skill lookup

The only specialist drawing skill approved for this report skill is the machine ID `scientific-diagram-016`.

1. Check the exact installed path `<CODEX_HOME>/skills/scientific-diagram-016/SKILL.md` first.
2. If it is absent, scan only the configured local workspace-skill cache for paths whose final skill directory is exactly `scientific-diagram-016`; do not scan the whole disk and do not fuzzy-match names, display numbers, descriptions, or drawing-related words.
3. Use the specialist only when exactly one readable `SKILL.md` is resolved. Read that file completely before creating the figure, then follow only the references relevant to the selected figure class.
4. Treat zero matches, multiple matches, unreadable instructions, renderer errors, and failed diagram QA as specialist failure. Do not install packages, access the network, or silently switch to another drawing skill.

## Specialist route

When `scientific-diagram-016` resolves successfully, use it for these newly authored figure classes:

- workflow;
- study-design;
- comparison-framework;
- hypothesis-matrix;
- evidence-chain;
- simple-mechanism;
- simple-spatial-schema.

Retain editable source and final SVG together. When the specialist returns dedicated desktop, mobile, and print variants, pass all three through `path`, `mobile_path`, and `print_path`. Apply both the specialist skill's quality gate and the report's embedded-render inspection.
Mark each specialist-generated report image with `"authored_concept": true`. The report renderer must reject a raster source for this flag and the static validation output must list the exact role, relative SVG path, source SHA-256, embedded SHA-256, and MIME for every variant.

## Simple fallback

Use fallback only after the exact specialist route fails, and record the reason in the work notes.

- For a workflow or evidence chain, use numbered steps, a plain HTML table, or a simple authored SVG with no more than 6 boxes, 3 boxes per row, and 1 branch level.
- For a qualitative comparison, prefer a plain HTML table; use a simple authored SVG grid only when position adds real meaning, with no more than 3 groups and 4 rows.
- For mechanisms or spatial relationships, use labeled boxes/compartments and direct arrows only. If that cannot communicate the science cleanly, use prose or a table instead of forcing a diagram.
- Add `概念示意 · 非项目实测结果` where confusion with measured results is plausible.
- State in the final delivery note that the specialist skill was unavailable or failed and that a simple fallback was used.

## Shared evidence rules

- Route measured values to ordinary quantitative plotting tools, never to a conceptual diagram renderer.
- Never draw invented bars, points, heatmaps, error ranges, effect sizes, or significance markers for expected results.
- Preserve supplied result figures without recoloring or semantic changes.
- Record authored concept figures as `本报告根据课题设计绘制，非数据结果` or equivalent.

## Shared quality gate

- Export SVG as the primary deliverable; create PNG only when another consumer cannot display SVG.
- Verify typography, alignment, connector routing, whitespace, semantic color consistency, 390 px readability, browser enlargement, and print rendering.
- Compare the validator's desktop/mobile/print roles, paths, source hashes, embedded hashes, and MIME values with the finalized SVGs before visual sign-off; inspecting a different same-stem file does not count.
- A figure is not complete if text overlaps, arrows enter labels, small annotations become illegible, or the caption is required to decode basic structure.
- SVG must be self-contained: no scripts, event attributes, `foreignObject`, external images, web fonts, or remote styles.
