---
name: sc-marker-cluster-annotation-auto
description: Expert-style subcluster annotation within a declared parent population using average expression, detection ratio, marker statistics, UMAP topology, tissue/species context, and versioned literature verification.
---

# Subcluster annotation

Use this skill only when the supplied dataset is already restricted to one
parent population. The complete table is annotated at one consistent
subcluster level within that parent. Do not mix a parent label with its
descendant or refine only the clearest lineage.

## Inputs

Require species, tissue/organ, parent population, average-expression input,
marker workbook, and a UMAP PNG with readable cluster IDs and legend. The
expression file has `gene`, `group`, `mean_expr`, `expr_ratio`, and `norm_expr`;
`expr_ratio` is detection ratio. Marker statistics may include
`Target_Cluster_mean`, `Other_Cluster_mean`, `log2FC`, `pct.1`, and `pct.2`.
Preserve parent scope, input order, and cluster IDs.

## Decision logic

For every cluster:

1. Establish the parent program without using it to hide contamination. Build a
   dataset-wide background profile and downweight signals present across most
   clusters, tissue-wide ambient programs, and housekeeping/QC genes.
2. Compare sibling candidates as complete programs: identity anchors first,
   explicit sibling exclusions second, differentiation programs third, and
   state/QC programs last. UMAP is supporting evidence.
3. Jointly interpret `mean_expr`, `expr_ratio`, `log2FC`, `pct.1`, and `pct.2`.
   High expression in a few cells is not a broadly supported program; a modest
   signal across most cells may be meaningful. `norm_expr` must not be counted
   twice.
4. Audit tissue-relevant off-parent programs. A globally elevated epithelial
   program is background; a locally enriched multi-gene, high-prevalence program
   may indicate contamination, reassignment, or a mixed boundary. One shared
   marker is never enough for a doublet call.
5. Review every cluster on the full UMAP and audit repeated labels: neighboring
   types, continuous trajectories, disconnected same-label islands, isolated
   cycling/state islands, and marker/UMAP conflicts. A conflict triggers
   reassessment, not automatic relabeling.
6. Resolve primary identity, then separately assign any
   `low_quality`, `background_interference`, `abnormal_state`, `debris`,
   `suspected_doublet`, or `mixed_population` flags. Flags may coexist.
7. If competing programs are complete and near-balanced, use `Multi_cell` with
   concrete components and red warning formatting. If one program dominates,
   retain its identity and explain the secondary signal as background,
   contamination, or state with reduced confidence.

## Boundary behavior

Do not infer subtype from a shared state program alone. Cycling, exhaustion,
interferon response, cytotoxicity, antigen presentation, and stress remain
states unless a coherent identity program supports a subtype. For every lineage
boundary record both candidate programs, prevalence, relative dominance,
exclusions, and the decision. If the knowledge base lacks a defensible leaf,
perform targeted research and use a validated external candidate only with two
independent sources and current-case supporting markers; do not silently choose
an arbitrary ancestor.

## Output

Produce a cluster-level `cluster -> celltype_label` mapping usable for UMAP.
Keep the most likely主体细胞类型 even for impurity, low quality, abnormal,
debris, or suspected doublet clusters. Put abnormality, components,
characteristic genes, UMAP judgment, confidence, explanation, literature, and
handling recommendation in separate fields. Mark the annotation cell red when
the cluster should not be interpreted as a normal pure type; do not replace the
plotting label with `Doublet` or `Debris`.

Use the versioned naming dictionary. Established unambiguous abbreviations such
as `gdT` and `Tn` are allowed; short common labels such as B cell and T cell
remain full. One canonical plotting label has one level and one spelling.

## Retrieval and reproducibility

This skill has an independent calibration counter. Its first five uses after
this skill/core/dictionary revision must verify involved types against current
literature and curated atlases. From use six onward retrieve only for
marker/context/UMAP conflicts or knowledge-base gaps. Record source, retrieval
date, species, tissue, supported program, exclusions, and adoption/rejection
rationale in a reusable evidence sheet.

Record versions, hashes, counter, source paths, cluster order, parent context,
and the full UMAP audit. Deliver a timestamped Excel workbook to the supplied
E-drive input directory. Do not automatically edit or filter the underlying
object.

Never output generic `Cell`, mix ancestors and descendants, infer same-cell
coexpression from aggregate data, silently discard off-parent clusters, or
claim confirmed doublet from aggregate-only evidence.
