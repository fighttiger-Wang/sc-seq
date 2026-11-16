# Differential expression interpretation

Use this reference for marker tables and group differential-expression outputs.

## Required checks

- Confirm species, cell population, comparison orientation, statistical method, gene identifiers, and whether results are cell-level or pseudobulk/sample-aware.
- Read the actual column meanings for log fold change, adjusted P value, detection fraction, base expression, and direction.
- Keep marker discovery separate from disease-group differential expression.
- If multiple cell types or contrasts exist, organize results by the biological question rather than listing every significant gene.

## Interpretation priorities

1. State the comparison and exact direction.
2. Emphasize genes with both meaningful effect and statistical support when those fields exist.
3. Group genes into coherent functions only when supported by several genes or downstream enrichment.
4. Identify discordant genes, small effects, low detection, or results driven by one cell population when visible.
5. Connect genes to mechanisms using tissue- and disease-relevant literature.

## Boundaries

- RNA abundance is not protein abundance, secretion, enzyme activity, receptor activation, or causal control.
- A transcription factor target pattern does not prove direct regulation without a regulatory analysis.
- One gene should not define a complex state such as exhaustion, senescence, EndMT, M1/M2, or cell death unless a validated multi-gene context is present.
- Do not call a gene a biomarker or therapeutic target based only on differential expression.
- If sample-aware analysis is absent or unclear, name pseudoreplication as a limitation rather than silently accepting cell-level significance.

## Reporting shape

Use a compact table for the most decision-relevant genes and prose for the shared program. Put full gene lists outside the main storyline unless the user asks for them. Explain both the biological signal and alternative explanations such as cell-state composition, technical detection, batch, treatment, sex, age, or disease severity.
