# Cell proportion and ROE interpretation

Use this reference for sample-level cell proportions, group proportions, observed/expected ratios, enrichment heatmaps, and composition comparisons.

## Required checks

- Confirm whether values are sample-level proportions, pooled-cell proportions, group means, medians, counts, or ROE.
- Confirm the denominator: all cells, a parent lineage, a tissue compartment, or another subset.
- Confirm whether statistical tests were performed across biological samples or only summarized across pooled cells.
- Preserve annotation resolution. A broad `Myeloid` cluster is not automatically inflammatory macrophages; `Stromal` is not a specific fibroblast subtype; broad SMC cannot support subtype-specific thresholds.
- Do not import disease-specific cutoffs from another project unless the same subtype definitions and measurement scale are present.

## Composition logic

Cell proportions are compositional: one population can appear increased because another population fell. When total cell counts, tissue recovery, viability, or absolute abundance are unavailable, state that relative enrichment cannot distinguish expansion from loss elsewhere.

Interpret three layers separately:

1. Statistical result: direction, effect size, uncertainty, and adjusted significance from the supplied table.
2. Biological pattern: coordinated changes across related populations, reciprocal shifts, or disease-stage gradients.
3. Mechanistic explanation: recruitment, survival, differentiation, tissue loss, or sampling effects, supported by literature or marked as speculation.

## ROE

- ROE greater than 1 means observed representation exceeds the expectation defined by the analysis; below 1 means depletion relative to that expectation.
- Do not call ROE a percentage, fold change between disease groups, or absolute abundance unless the method explicitly defines it that way.
- Report the expectation model if known. A strong ROE can coexist with a low absolute proportion.
- Compare ROE and raw proportions when both exist. Discordance may be mathematically valid and should be explained, not concealed.

## Scientific storyline

Prioritize:

- pan-condition changes versus control;
- the primary biological contrast;
- subtype contrasts or progression gradients;
- reciprocal cell-state or lineage shifts;
- classification ratios already calculated in the supplied results;
- outliers and annotation limitations.

Do not invent ratio classifiers. If a supplied ratio appears useful, describe it as an exploratory candidate unless externally validated.
