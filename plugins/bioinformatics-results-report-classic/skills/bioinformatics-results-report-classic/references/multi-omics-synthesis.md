# Multi-omics & Multi-module Synthesis

Use this reference when integrating findings across cell proportions (`ROE`), differential expression (`DEG`), functional enrichment (`GO/KEGG/GSEA/GSVA`), cell-cell communication (`CellChat/NicheNet`), and pseudotime trajectories into one coherent scientific narrative.

## Cross-module evidence chain

1. **Anchor on cellular shifts first**: Start from cell-type / subcluster proportion or `ROE` shifts to identify which populations expand, contract, or redistribute across contrasts.
2. **Link to transcriptional programs**: Connect those shifted populations to their `DEG`s and enriched pathways (`GO/KEGG/GSEA/GSVA`), verifying consistent directionality and adjusted significance (`p_val_adj` / `FDR`).
3. **Trace intercellular & dynamic drivers**: Map ligand-receptor interactions (`CellChat/NicheNet`) and pseudotime branch/state transitions onto the same sender/receiver populations and pathway axes.
4. **Separate direct evidence from hypotheses**:
   - Direct table/figure support -> cite exact source table/figure, contrast, and effect/significance.
   - Literature-supported mechanism -> cite verified `author-year / journal` (DOI checked via Crossref).
   - Unverified mechanistic extrapolation -> label explicitly as `未获文献验证的机制推测`.

## Synthesis guardrails

- Organize chapters by **scientific question or biological contrast**, never by raw module/file name.
- Do not fabricate cross-module causality when modules were computed on unmatched sample subsets or different statistical units; disclose any sample/unit mismatch in Limitations.
- Retain original plot palettes and never upgrade descriptive trends to statistical significance.
