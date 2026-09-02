# Acceleration, evidence reuse, and UMAP audit

Use this workflow on every run.

## Selective loading

1. Verify the shared snapshot versions and hashes.
2. Load the global annotation policy, the current parent-lineage ontology nodes and marker panels, and all cross-lineage contamination sentinels.
3. Do not reread unrelated lineage panels or the complete monolithic knowledge base.
4. Reuse canonical candidate evidence IDs and source metadata already stored in the approved knowledge base.
5. Search literature only when a plausible candidate is absent, marker and UMAP evidence conflict, or genuinely newer evidence could change a boundary.

## Dual-track delivery

Run marker annotation and UMAP review independently when possible.

- Temporary delivery: output only `cluster` and `suggested_cell_type` with `scripts/build_interim_mapping.py`.
- If UMAP was supplied, review every cluster before temporary delivery.
- If UMAP is absent, allow marker-only temporary delivery and mark formal delivery blocked.
- Formal delivery: require all-cluster UMAP audit, an explicit identity action for every cluster, resolved/reused research for every marker/UMAP conflict, full historical regression, versioned publication, and the fixed five-sheet workbook.

## UMAP audit

Create one JSON record per cluster with:

- `reviewed=true`
- `topology_summary`
- `nearest_clusters`
- `marker_umap_relation`: `concordant`, `conflict`, or `indeterminate`
- `conflict_reason`
- `research_required`
- `research_status`: `not_required`, `pending`, `resolved`, or `reused`
- `conflict_resolution_basis`: `cell_level_coexpression`, `sample_metadata`, `trajectory_metric`, `reference_mapping`, `quantitative_qc`, `literature_only`, or `none`
- `evidence_ids`
- `review_action`
- `identity_action`: `retain` or `reject_and_reassign`
- `provisional_label`
- `resolved_label` and `resolved_label_cn`
- `reassessment_rationale`
- `reassessment_marker_support`
- `same_label_clusters`: every other cluster carrying the same final stable identity
- `same_label_topology`: `adjacent`, `disconnected`, or `not_applicable`
- `separation_explanation`: `state_dominant`, `sample_effect`, `trajectory_boundary`, or `none`
- `separation_evidence`: concrete state markers, verified sample composition, or trajectory evidence

UMAP is mandatory consistency evidence, not a standalone classifier. A conflict can retain the provisional identity or reject and reassign it only after integrated review. `reject_and_reassign` requires the provisional label to match the pre-UMAP identity, a different canonical resolved label, a concrete topology-plus-Marker rationale, and a coherent multi-gene program already present in current-case evidence for an existing same-level candidate. UMAP cannot create a new identity or retreat to the supplied parent. Formal delivery is blocked when a conflict is unresolved or the identity action was not applied to the plotting and workbook labels.

Repeated labels require a cross-island audit against the final records. A disconnected same-label island may remain concordant only when a concrete dominant state, verified sample effect, or defensible trajectory boundary explains the separation. A state explanation must name a state present in the final record and retain concrete evidence IDs; a generic group-level list of possible states is insufficient. Every disconnected repeated label has `auto_merge_allowed=false`; retaining the same identity is not permission to merge clusters. Without explanatory evidence, set `marker_umap_relation=conflict`, `research_required=true`, and resolve or reuse research before formal delivery. Literature alone cannot resolve sample-specific topology and is invalid as the sole formal `conflict_resolution_basis`. The builder compares `same_label_clusters` with the final labels, so an all-concordant audit written independently of the annotation table cannot pass.

For `validated_external_candidate` or `researched_branch_fallback`, compare the final identity against the labels of `nearest_clusters`. If no nearest cluster shares that identity, plain `concordant/not_required/none` is invalid. Retain a conflict or provide resolved/reused current-case evidence with a concrete basis such as quantitative QC, cell-level coexpression, resolving reclustering, reference mapping, sample metadata, or trajectory metrics.

## Candidate promotion and regression

Promote a validated candidate immediately after all of the following pass:

1. At least two independent sources.
2. Current-case marker and UMAP review where UMAP exists.
3. All registered historical regressions from one frozen candidate snapshot.
4. No unapproved change in identity, state, risk, or automatic-merge behavior.

Run `tests/run_registered_regressions.py`; do not publish after running only an affected-lineage subset. Add every newly discovered generalizable failure to `tests/regression-registry.v1.json` and its registered suite before publication.

Before publication, keep the case record as `validated_external_candidate`. After the regression and versioned knowledge-base publication, use it as a canonical subtype in future runs without repeated literature research.

Run independent UMAP review, literature resolution, and regression groups in parallel when inputs permit. Write centralized task continuity only once at the terminal state.
