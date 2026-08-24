# Project context and annotation-level routing

Read this reference before selecting metadata, parent population, or annotation depth.

## Context discovery order

1. Use explicit user statements and named reference files.
2. Inspect the common input directory and at most two E-drive parent levels for small, directly relevant context files: study-background YAML/JSON/Markdown/text, sample-group workbooks, annotation mappings, and cited papers.
3. Treat generic tokens such as `organoid`, `cell line`, `tumor`, or `single cell` as experimental-system descriptors, not tissue names.
4. Infer tissue and parent population only when supported by filenames, sample/group labels, study text, or a relevant paper. Otherwise ask one consolidated metadata question.
5. Record the evidence path and the inferred `tissue`, `experimental_system`, `parent_population`, and `parent_kind`.

Do not recursively inventory unrelated project trees. Preserve all context files unchanged.

## Parent-kind decision

- Use `mixed` only for an explicit all-cell atlas or evidence-supported multiple broad lineages.
- Use `lineage` for purified cells, derived cell lines, organoid differentiation systems, sorted populations, or a project taxonomy confined to one lineage.
- Use `state` only for an intentionally pooled state bucket such as cycling or activated cells.
- Never default a derived organoid/cell-line experiment to `All_cells/mixed` merely because cluster identities are unknown.

## Annotation-level gate

Route to `$sc-marker-cluster-annotation-auto` before building a major workbook when any condition holds:

- all expected labels belong to one known lineage;
- the requested/project vocabulary contains progenitor, proliferating, EMT, myofibroblast, activated, stress, maturation, or other subtype/state labels;
- an existing annotation map defines within-lineage leaves;
- the parent population is already known and the task is to resolve its internal heterogeneity.

When a user supplies a manual or legacy annotation table during reannotation, use it as an auditable project-taxonomy prior, not as unquestioned ground truth. Check every label against marker evidence and report disagreements.

## Tissue-constrained evidence

Within a confirmed lineage, shared parent markers may not be differential markers. Establish the parent identity from project context and canonical expression before interpreting cluster-specific markers. State/QC programs may define `state` or a project leaf such as proliferating MSC, but they must not create an unrelated off-parent lineage.

Require at least two coherent positive DE markers for any consequential off-parent lineage call. For centered/scaled averages, canonical-expression ranks alone cannot satisfy this requirement.
