# Intake and evidence rules

## Evidence hierarchy

Use the following order when sources disagree:

1. machine-readable statistical tables with explicit comparison and column definitions;
2. figure labels and legends generated from those tables;
3. project methods or analysis notes;
4. filenames and folder names;
5. user or analyst interpretation text.

This order is a diagnostic default, not permission to silently override a contradiction. Pause and ask the user whenever the difference affects sample counts, group meaning, comparison direction, significance, or the report conclusion.

## Confirmation checkpoint

Before interpreting results, summarize and request confirmation of:

- study purpose or disease/experimental context;
- species and tissue;
- group names, biological meanings, and sample counts;
- statistical unit when it is stated;
- available analysis types and pairwise comparisons;
- which table supports each core figure;
- files to exclude, including old reports, previews, or superseded versions;
- proposed report coverage.

Ask one short question at a time when information is missing. Do not ask the user to fill a template.

## Existing statistics only

- Do not recompute P values, adjusted P values, fold changes, correlations, scores, ROE, enrichment, or cell communication metrics.
- Do not infer significance from bar height, color intensity, heatmap contrast, or visual separation.
- If statistical columns are absent, write `描述性趋势` or `图形上呈现`, not `显著`.
- Preserve the actual comparison orientation. `A_vs_B` is not enough if the table does not define whether positive values mean A or B; confirm it.
- Prefer adjusted significance over nominal P values when both exist.
- A large effect with weak statistical support and a small effect with strong support are different findings; report both dimensions when provided.
- Cell-level observations do not replace biological replicates. Never treat thousands of cells as thousands of independent subjects.

## Literature verification

Search using scientific concepts only. Never send paths, filenames containing customer information, sample IDs, raw table rows, or source images to external services.

Prioritize:

1. recent peer-reviewed primary research;
2. recent systematic reviews or consensus/guidelines;
3. older landmark work required to explain an established mechanism.

Check that each source actually supports the nearby claim in the relevant species, tissue, disease, or method context. Do not cite a broad review as proof of a dataset-specific causal mechanism. Use a short linked label such as `Smith 2024 / Nature Medicine` beside the sentence. If no reliable source is found, use the exact phrase `未获文献验证的机制推测`.

## Writing discipline

Express evidence level through language rather than visual badges:

- Direct result: `结果显示`, `统计表提示`, `在给定比较中`.
- Literature-informed interpretation: `结合既往研究，这一变化可能反映`.
- Unsupported mechanism: `推测`, `尚需验证`, plus `未获文献验证的机制推测` when applicable.

Do not use `证明`, `导致`, `驱动`, `治疗靶点`, `诊断标志物`, or `预测进展` unless the supplied study design and external evidence genuinely establish that strength. Prefer `支持`, `一致`, `相关`, `候选`, `潜在`, and `值得验证`.

## Mixed-audience structure

- Core summary: what changed, how well supported, and why it matters.
- Professional body: comparison, effect direction, statistical support, biological context, and linked literature.
- Clinical/translational section: potential value and prerequisites for validation.
- Limitations: missing variables, sample size, annotation resolution, confounding, method assumptions, and literature gaps.
