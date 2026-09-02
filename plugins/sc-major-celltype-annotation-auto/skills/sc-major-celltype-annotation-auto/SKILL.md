---
name: sc-major-celltype-annotation-auto
description: Expert-style major-celltype annotation for mixed/all-cell single-cell data using average expression, detection ratio, marker statistics, UMAP topology, tissue/species context, and versioned literature verification.
---

# Major cell-type annotation

Before making any annotation decision, apply the shared [universal annotation contract](../../../../shared/annotation-universal-contract.md). This skill adds the major-level rules below; it does not replace the shared evidence, UMAP, naming, or workbook QA requirements.

Use this skill only for mixed/all-cell collections. The complete table is
annotated at one major-celltype level; never refine only one lineage because its
markers are clearer.

## Inputs

Require species, tissue/organ, average-expression input, marker workbook, and a
UMAP PNG with readable cluster IDs and legend. The quantitative file has
`gene`, `group`, `mean_expr`, `expr_ratio`, and `norm_expr`; `expr_ratio` is
detection ratio. Marker statistics may include `Target_Cluster_mean`,
`Other_Cluster_mean`, `log2FC`, `pct.1`, and `pct.2`; interpret `pct.1/pct.2`
as target/background prevalence. Final output sorts numeric cluster IDs from small to large, then uses natural alphanumeric order for mixed IDs.

## Decision logic

For every cluster:

1. Build a dataset-wide background profile. Downweight programs elevated across
   most clusters, housekeeping/ribosomal/mitochondrial programs, and
   tissue-wide ambient signals. A globally elevated epithelial or immunoglobulin
   program must not redefine every cluster.
2. Evaluate coherent major programs with explicit qualitative gates using
   multiple anchors, relative specificity, mean expression, detection ratio,
   and competing-lineage exclusions. Preserve per-gene values, but never turn
   them into an aggregate score or ranking. `norm_expr` is secondary evidence.
3. Use species and tissue as facts. Do not treat inferred disease, treatment,
   age, sex, or anatomy as user-provided facts.
4. Treat marker tables as candidate discovery evidence. A high `log2FC` with
   low `pct.1` is a clue, not a decisive identity call.
5. Review every cluster on the full UMAP: same-type islands, interleaving,
   plausible transitions, neighboring lineages, and marker/UMAP conflicts.
   UMAP is a global consistency check, not a hard identity gate.
6. Resolve primary identity first, then separately classify
   `low_quality`, `background_interference`, `abnormal_state`, `debris`,
   `suspected_doublet`, and `mixed_population`; multiple flags may coexist.
7. If two incompatible programs are complete and competitive, retain the
   dominant identity when one clearly dominates; otherwise use `Multi_cell` and
   list concrete components. Aggregate evidence cannot prove same-cell
   coexpression.

## Output

Produce a cluster-level mapping with one stable plotting label per cluster.
Keep identity, state, abnormality, components, characteristic genes, UMAP
judgment, evidence, literature, and handling recommendation in separate
fields. Do not create confidence or score fields. For an impurity or non-pure plotting cluster, retain the most
likely主体细胞类型 and mark its annotation cell red; do not replace the
plotting identity with `Doublet` or `Debris`.

Use the versioned naming dictionary. Established unambiguous abbreviations such
as `gdT` or `Tn` are allowed; short common labels such as B cell and T cell
remain full. Never mix a major label with a descendant subtype.

## Retrieval and reproducibility

This skill has an independent calibration counter. Its first five uses after
this skill/core/dictionary revision must verify involved types against current
literature and curated atlases. From use six onward retrieve only for
marker/context/UMAP conflicts or knowledge-base gaps. Record source, retrieval
date, species, tissue, defining program, exclusions, and adoption rationale.

Write a reusable data-specific evidence sheet listing involved types, markers,
definitions, and sources. Record versions, hashes, counter, input paths, cluster
order, context, and UMAP audit. Deliver a timestamped Excel workbook to the
supplied E-drive input directory. Do not automatically modify or filter data.

Never output generic `Cell`, silently discard a cluster, use one marker or one
UMAP location as sole proof, or claim confirmed doublet from aggregate evidence.
