# Expert identity review and case-driven optimization

Formal subcluster annotation is not complete when structural QA passes. A
qualified reviewer must independently inspect the biological decision for
every cluster before workbook construction.

## Required review

For each cluster, review and record:

1. whether the primary identity is supported by a complete multi-gene program;
2. the nearest sibling or off-parent alternatives, including positive and
   exclusion evidence;
3. whether the proposed plotting label is a canonical identity at one level,
   with state, activation, stress, inflammation, and tissue context kept in
   separate fields;
4. whether marker statistics, prevalence, dataset-wide background, and UMAP
   topology agree;
5. whether the cluster is normal, state-altered, background-interfered,
   low-quality, or a suspected mixed population;
6. what additional evidence would most efficiently resolve the main gap.

The reviewer must not treat a passing script gate, a literature match, or a
UMAP position as a substitute for this review. Aggregate expression cannot
prove same-cell coexpression or a doublet.

## Required record fields

Every formal record must contain:

- `expert_review_status`: `passed` or `conditional`;
- `expert_review_basis`: concise evidence-based review statement;
- `identity_review_summary`: primary identity, closest competing program, and
  the decision boundary;
- `optimization_recommendations`: concrete case-specific next action, or an
  explicit statement that no additional optimization is currently required.

`conditional` is appropriate when the identity is usable but a material
validation gap remains. It must include a non-empty recommendation and a
handling/validation action. A record with missing review fields is blocked
from formal workbook construction.

## User-facing handoff

The final assistant response must summarize the expert review outcome and list
the highest-value optimization recommendations, not only provide the Excel
file. Recommendations should be driven by the current case, for example:
orthogonal markers for a sibling boundary, cell-level coexpression for a
possible mixture, sample/QC stratification for an isolated state island, or
reannotation after obtaining a non-scaled expression matrix. Do not invent a
recommendation when the evidence gap is genuinely absent; state that no extra
optimization is currently required.
