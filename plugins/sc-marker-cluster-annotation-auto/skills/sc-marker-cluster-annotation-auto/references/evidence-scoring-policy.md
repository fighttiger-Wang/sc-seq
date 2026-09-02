# Qualitative annotation evidence policy

The active evidence core is `qualitative_evidence_core.py`. Annotation is an
expert biological decision and must not calculate or consume an aggregate
identity score, confidence grade, candidate rank, score margin, or weighted
quality value.

## Evidence modes

- `minimal`: average expression plus positive Marker statistics. Missing genes
  are unknown.
- `ratio_enhanced`: verified gene-by-cluster detection ratios. Missing genes may
  be interpreted only according to the verified matrix completeness contract.
- cell-level evidence: optional evidence for co-expression, resolving mixed
  populations, and doublet review. Cluster averages cannot replace it.

## Per-gene evidence

Retain available `mean_expr`, `expr_ratio`, `log2FC`, `pct.1`, and `pct.2` for
each Marker. Conservative absolute or dataset-relative thresholds may decide
whether one gene supports a gate. These thresholds must never be combined into
one candidate score.

## Biological gates

Each applicable gate is reported as `通过`, `不通过`, `未确定`, or `不适用`:

1. identity-anchor program;
2. parent-lineage program;
3. sibling competition;
4. explicit exclusions and mutually exclusive programs;
5. tissue-relevant off-parent programs;
6. development and state programs;
7. UMAP consistency;
8. mixed-population and doublet interpretation.

Candidate arbitration follows an explicit biological precedence ladder:
complete identity program, required absolute program, branch-defining anchors,
number of strong identity anchors, number of supported identity anchors,
explicit conflicts, supportive markers, and supported ontology depth. These
criteria are considered sequentially and are recorded in the decision trace;
they are not added, weighted, normalized, or presented as a ranking table.

## Identity and state

Identity is resolved before development, activation, cycling, exhaustion,
interferon response, stress, hypoxia, or other states. A state requires a
coherent multi-gene program; one state Marker is insufficient. State never
replaces an otherwise coherent identity.

## Mixed populations and doublets

Retain a clearly dominant identity. If complete incompatible programs have no
biological dominance, use `Multi_cell` in subcluster work or carry mixed
evidence beside the retained major identity in major-celltype work. Aggregate
evidence never confirms same-cell co-expression or doublets. Never
automatically delete, filter, merge, or modify cells.

## Annotation depth

Every cluster receives a result. A subcluster result remains at the requested
sibling/leaf level. Incomplete evidence triggers further sibling comparison,
exclusion review, literature research, an explicit evidence gap, and a
validation recommendation; it does not justify retreating to the supplied
parent.

## Formal output

Only `qualitative_annotation_evidence` is a formal evidence object. Historical
score fields and `deterministic_annotation_evidence` are invalid in new runs.
The workbook contract is defined in `../annotation-universal-contract.md`.
