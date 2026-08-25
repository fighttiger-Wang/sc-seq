# GO, KEGG, GSEA, and GSVA interpretation

Do not merge these methods into one generic pathway claim. Identify the method and its direction semantics.

## ORA: GO and KEGG over-representation

- Confirm the input gene set, background universe, ontology/database, direction-specific gene list, and multiple-testing field when available.
- Over-representation means a term is more common in the selected gene set than expected; it does not prove pathway activation.
- Group redundant terms into biological themes while keeping representative terms and their statistics visible.
- Broad or annotation-heavy terms may be less informative than coherent, tissue-relevant modules.

## GSEA

- Confirm phenotype orientation and which sign of NES corresponds to which group.
- Use NES, adjusted significance, and leading-edge genes when provided.
- Positive and negative enrichment are not automatically activation and inhibition; describe them as enrichment toward the defined phenotype.
- A pathway supported by a small or unstable leading edge deserves cautious wording.

## GSVA or per-sample pathway scores

- Confirm whether scores are per sample, per cell, or aggregated by cell type.
- Interpret the supplied group comparison of scores, not the raw sign alone.
- A higher score indicates greater relative expression of the gene set under the chosen method; it is not direct biochemical flux or pathway activity unless independently validated.

## Storyline and validation

Prioritize themes that are statistically supported, coherent across related terms, biologically relevant, and consistent with the associated genes or figures. Highlight contradictions between ORA, GSEA, and GSVA rather than forcing agreement. Mention database version, background selection, gene-set overlap, gene-list thresholding, and cell-composition effects when they materially limit interpretation.
