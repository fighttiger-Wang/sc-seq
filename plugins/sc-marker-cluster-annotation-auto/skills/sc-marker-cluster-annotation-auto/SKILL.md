---
name: sc-marker-cluster-annotation-auto
description: Expert-style subcluster annotation within a declared parent population using average expression, detection ratio, marker statistics, UMAP topology, tissue/species context, and versioned literature verification.
---

# Subcluster annotation

Before making any annotation decision, apply the shared [universal annotation contract](../../../../shared/annotation-universal-contract.md). This skill adds the parent-restricted sibling-level rules below; it does not replace the shared evidence, UMAP, naming, or workbook QA requirements.

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
Preserve parent scope and cluster IDs. Final output sorts numeric cluster IDs from small to large, then uses natural alphanumeric order for mixed IDs.

## Decision logic

For every cluster:

1. Establish the parent program without using it to hide contamination. Build a
   dataset-wide background profile and downweight signals present across most
   clusters, tissue-wide ambient programs, and housekeeping/QC genes.
2. Compare sibling candidates as complete programs: identity anchors first,
   explicit sibling exclusions second, differentiation programs third, and
   state/QC programs last. UMAP is supporting evidence. For high-risk
   unconventional-T boundaries, run the configured absolute program gate
   before leaf selection: NKT requires TCR plus distinct NK-receptor and
   cytotoxic programs; MAIT requires a coherent T program, alpha-beta branch
   support, and multiple MAIT-associated markers; DNT tolerates non-dominant
   receptor background but not a dominant competing CD4/CD8 or gamma-delta
   program.
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
   cycling/state islands, and marker/UMAP conflicts. Record an explicit identity
   action. A conflict may reject a provisional label only when integrated
   Marker and topology review selects an already-supported same-level candidate;
   UMAP alone cannot create or overwrite an identity.
   Formal delivery must bind the records to the output of
   `qualitative_evidence_core`: do not hand-author `evidence.json`,
   `records.json`, and `umap_audit.json` by copying a proposed label into all
   three files. A UMAP reassignment is valid only for a documented
   marker/UMAP conflict and only to a candidate present in the core's
   candidate-program audits.
6. Resolve primary identity, then separately assign any
   `low_quality`, `background_interference`, `abnormal_state`, `debris`,
   `suspected_doublet`, or `mixed_population` flags. Flags may coexist.
7. If competing programs are complete and near-balanced, use `Multi_cell` with
   concrete components and red warning formatting. If one program dominates,
   retain its identity and explain the secondary signal as background,
   contamination, or state, and record the unresolved evidence explicitly.

## Boundary behavior

Never let a single receptor chain, a single shared marker, or a state marker
create a subtype. `SLC4A10`, `ZBTB16`, `TRDC`, and cytotoxic genes must be
interpreted as components of a complete program and against cross-cluster
background; aggregate expression cannot establish same-cell coexpression.

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
characteristic genes, UMAP judgment, explanation, literature, and handling
recommendation in separate fields. Do not create confidence or score fields.
Mark the annotation cell red when
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
and the full UMAP audit. Formal delivery requires the fixed five-sheet workbook
and a hash-matching passing QA sidecar; legacy four-sheet output is invalid.
Deliver a timestamped Excel workbook to the supplied E-drive input directory.
Do not automatically edit or filter the underlying object.

For a blind test, invoke the preparation entry point with `--blind-test`.
Do not pass a prior annotation workbook, old records, old UMAP audit,
cluster-specific exclusions, or marker exclusions. The only label-bearing
artifact allowed in the blind run is the ontology's candidate-program
vocabulary. The model-facing digest redacts the qualitative core's
`stable_id`, `suggested_identity`, `primary_program`, major label, derived
rationale, and recommended action. Treat those fields in the internal evidence
pack as audit bindings, never as the annotation answer. First write an
independent provisional label from the current-case multi-gene programs and
the candidate audits; then perform a separate all-cluster UMAP review. UMAP
review must be read from the supplied image and must not be generated from the
core decision or from the provisional label. Final workbook construction is
allowed only after the independent records, UMAP audit, and internal evidence
binding all pass validation.

Never output generic `Cell`, mix ancestors and descendants, infer same-cell
coexpression from aggregate data, silently discard off-parent clusters, or
claim confirmed doublet from aggregate-only evidence.
