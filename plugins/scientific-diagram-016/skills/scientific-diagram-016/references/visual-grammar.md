# Visual grammar and limits

Choose the smallest grammar that communicates the scientific relationship accurately.

| Figure class | Use when | Primary source | Avoid |
|---|---|---|---|
| Three-group workflow / study design | groups converge on two comparisons and three analysis stages | fixed Typst/CeTZ templates | generic auto-layout or scaling one wide SVG |
| Evidence chain | three evidence layers converge on one conclusion | fixed Typst/CeTZ templates or a table | implying causal proof from association |
| Comparison framework | groups or conditions follow the same analytical dimensions | Typst templates, matrix JSON, or HTML table | invented quantitative marks |
| Hypothesis matrix | rows are biological programs and columns are groups/conditions | matrix JSON | color intensity that looks quantitative |
| Simple mechanism | a few actors and directional relations require compartments | native SVG | pathway-poster density |
| Simple spatial schema | zones, adjacency, or tissue compartments are the message | native SVG | fake histology or cell-count density |

## Semantic rules

- Separate measured evidence, literature-supported interpretation, and untested hypothesis through wording and visible labels.
- Use arrows for direction or transition, not decoration. Dashed arrows mean conditional/proposed relations and must be explained.
- Use color by scientific role consistently. Do not use a sequential heatmap palette unless actual numeric values are encoded.
- For expected directions use words such as `可能增加`, `可能降低`, `可能回调`, or `待验证`; never fabricate effect size, significance, or variance.

## Complexity threshold

The publication template is deliberately narrow: exactly 3 groups, 2 comparison labels, and 3 analysis modules. A matrix may contain 2–4 groups and at most 6 rows. Split by scientific question when a limit is exceeded. If splitting damages the argument, replace the figure with a structured table.

## Responsive and print target

- Desktop canvas is fixed at 1440 × 880.
- Mobile canvas is independently composed at 390 × 1300.
- Print canvas is independently composed at 842 × 595 for A4 landscape use.
- Do not infer mobile or print success from a desktop screenshot.
