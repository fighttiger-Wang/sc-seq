---
name: scientific-diagram-016
description: Create stable, publication-ready scientific workflow diagrams, study-design maps, comparison frameworks, hypothesis matrices, evidence chains, and simple mechanism or spatial schematics as self-contained SVG. Use for newly authored conceptual figures; do not use for measured quantitative charts, existing result figures, complex biological illustration, or image generation.
---

# Scientific Diagram 016

Create concise scientific concept figures whose structure remains readable in HTML, on a 390 px screen, and in A4 print. Prefer fixed Typst/CeTZ templates that produce separate desktop, mobile, and print SVGs. Produce editable source plus self-contained SVG; label non-data-derived figures clearly.

## Supported scope

- workflow
- study-design
- comparison-framework
- hypothesis-matrix
- evidence-chain
- simple-mechanism
- simple-spatial-schema

Do not redraw supplied result figures, encode invented measurements, create statistical charts, or attempt detailed anatomical/cellular illustration. If the request exceeds this scope, split it into simpler panels or use a table and state the limitation.

## Route by visual grammar

1. For a three-group study design, three-stage workflow, comparison framework, or evidence chain that fits the fixed card grammar, read [Typst renderer](references/typst-renderer.md) and use the three dedicated templates.
2. Use the deterministic matrix renderer for a compact group-by-hypothesis or group-by-feature comparison when a plain HTML table is not clearer.
3. Use a simple authored SVG only when a few compartments, tissue positions, or direct relations cannot be expressed faithfully by the templates or a table.

Read [visual grammar and limits](references/visual-grammar.md) before choosing a route. For hypothesis matrices, read [matrix schema](references/matrix-schema.md).

## Stable renderers

- Run `scripts/render_typst_variants.py <spec.json> <output-dir> --stem <ascii-stem> --typst <path>` for the fixed study-design grammar. It accepts only Typst 0.13.1, vendored CeTZ 0.3.4, and an installed approved open-source Chinese font. It never downloads dependencies.
- The Typst route must produce three independent sources and SVGs: `.desktop`, `.mobile`, and `.print`. Never create responsiveness by scaling the desktop SVG.
- Render a compact hypothesis matrix with `scripts/render_hypothesis_matrix.py <input.json> <output.svg>` using Python standard library only.
- Validate every SVG with `scripts/validate_svg.py <figure.svg> --require-concept-label` when a reader could confuse the figure with measured project data.
- If the exact Typst compiler, approved font, fixed grammar, or visual QA is unavailable, do not install packages or switch to another auto-layout engine. Use a simple SVG or HTML table fallback and disclose the downgrade.

## Composition limits

- Prefer one scientific message per figure.
- The fixed Typst study-design grammar accepts exactly 3 groups, 2 comparison labels, and 3 analysis modules.
- Use at most 4 groups and 6 rows in one hypothesis matrix.
- Keep node titles short; move methodological detail into the caption.
- If labels remain long after scientifically safe editing, enlarge the canvas or split the figure. Never shrink essential text below the print/mobile readability threshold merely to fit.

## Required output

For each figure, retain the editable `.typ`, `.json`, or source `.svg` beside the finalized `.svg`. Keep the renderer manifest with exact source/SVG SHA-256 values. Use transparent or white backgrounds, approved local Chinese fonts, a `viewBox`, `<title>`, and `<desc>`. Typst may vectorize body glyphs; the finalizer must add a real-text visible concept label. Do not use scripts, event handlers, `foreignObject`, web fonts, external images, remote CSS, gradients, pseudo-3D effects, or decorative shadows.

When a downstream report schema supports an authored-concept flag, set it and require the consumer to embed this exact SVG. Compare the final report's recorded relative source path and SHA-256 with the finalized SVG; a same-stem PNG or a separately inspected SVG is not equivalent evidence.

When the figure is conceptual rather than data-derived, include a visible statement such as `概念示意 · 非项目实测结果`, and describe it in the report as `本报告根据课题设计绘制，非数据结果`.

## Quality gate

Do not finish until all are true:

- the reading order and every arrow path match the intended scientific logic;
- no text overlaps, clipping, connector-label collision, or excessive blank canvas is visible;
- typography, alignment, semantic colors, spacing, and visual center are consistent;
- the figure is understandable without using the caption to decode its basic structure;
- static SVG validation passes;
- the Typst renderer manifest identifies version 0.13.1, CeTZ 0.3.4, the selected open-source font, and all three variant hashes;
- the downstream report, when applicable, records and embeds the exact finalized SVG rather than an older raster derivative;
- the figure has been inspected at native size, around 390 px width, and in A4 print or print preview.

If visual inspection is unavailable, report `仅完成静态检查，视觉质检未完成` instead of claiming completion.
