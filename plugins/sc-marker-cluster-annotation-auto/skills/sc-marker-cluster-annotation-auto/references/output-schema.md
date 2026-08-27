# Output schema

Every annotation record contains:

| Group | Fields |
|---|---|
| Identity | `cluster_id`, `celltype_cn`, `celltype_en`, `stable_id`, `broad_type`, `fine_type`, `parent_path`, `tissue_module`, `ontology_node_kind` |
| Development/context | `developmental_stage`, `tissue_scope`, `tissue_scope_match`, `tissue_context_review` |
| State/role | `state`, `state_list`, `primary_state`, `disease_role`, `display_label` |
| Species/provenance | `target_species`, `panel_species`, `cross_species_inference`, `marker_panel_evidence_ids`, `marker_panel_evidence_gate` |
| Evidence | `supporting_markers`, `conflicting_markers`, `candidate_labels`, `rationale`, `primary_evidence_major_label`, `formal_identity_fallback`, `identity_boundary_audit`, `boundary_validation_required`, `boundary_validation_resolved`, deterministic scores and decision trace |
| Risk | `mixed_or_doublet`, `mixed_population`, `suspected_doublet`, `mixture_type`, `possible_components`, `auto_merge_allowed`, `manual_review`, `review_action` |
| Parent audit | `expected_parent_id`, `off_parent_detected`, `off_parent_reassignment`, `off_parent_candidate`, `off_parent_candidate_score`, `formal_identity_fallback` |
| Naming audit | `label_basis`, `canonical_subtype`, `top_marker_gene`, `literature_source`, `naming_grammar`, `contextually_excluded_naming_markers` |
| UMAP audit | `umap_same_label_clusters`, `umap_same_label_topology`, `umap_separation_explanation`, `umap_separation_evidence`, `umap_conflict_resolution_basis`, marker/UMAP relation and research status |

Rules:

- `stable_id` is the finest approved identity supported by the cluster.
- `stable_id` must encode identity only. `CD4_Tex` and `CD8_Tex` are forbidden formal outputs; migrate them to `CD4_T`/`CD8_T` or a supported subtype plus `primary_state=Exhausted`.
- `Cell` is forbidden as a final label in every annotation mode. A coherent mixed/multiplet cluster uses `stable_id=Multi_cell`, Chinese name `多细胞`, `formal_identity_fallback=multi_cell_annotation`, populated `possible_components`, manual review, and `auto_merge_allowed=false`. A noncoherent non-mixed cluster must continue targeted resolution and block formal delivery if unresolved.
- Major mode may display its nearest enabled major ancestor; subcluster mode displays the finest defensible within-parent identity.
- `display_label` equals the identity. Store state separately in `state`, preserve all detected states in `state_list`, and retain one `primary_state` for prioritization.
- Repeated canonical labels remain identical; cluster ID provides uniqueness.
- Repeated canonical labels must also pass a final-record-aware cross-island UMAP audit. Disconnected islands require a documented state, sample, or trajectory explanation; without it, formal QA requires a resolved marker/UMAP conflict. Every disconnected repeated identity has `auto_merge_allowed=false` even when the provisional label is retained.
- A marker/UMAP conflict cannot use `conflict_resolution_basis=literature_only` for formal delivery. Literature supports candidate plausibility but does not resolve sample-specific topology.
- `canonical_subtype` must equal `stable_id`, and canonical `celltype_en` must equal the deterministic identity-only `display_label`.
- Reject any final label matching `Exhausted_*_Tex`; it repeats the same exhaustion semantics in both state and identity.
- A final table must not contain an ontology ancestor and one of its descendants at the same time. `branch_identity_no_supported_leaf` is not exempt; it must trigger subtype research and resolution before delivery.
- Structural groups such as `Mature_B` are not valid final subcluster labels.
- A coherent incompatible lineage conflict requires `stable_id=Multi_cell`, `celltype_cn=多细胞`, `mixed_population=true`, `suspected_doublet=true`, `manual_review=true`, populated `possible_components`, and `auto_merge_allowed=false`.
- A deterministic incompatible T-sublineage conflict must also populate `mixture_type=incompatible_T_sublineages`, list both leaf identities in `possible_components`, and use `formal_identity_fallback=mixed_incompatible_sublineages` at their nearest shared parent.
- For `Naive_like_gdT` or `IL17A_gdT`, `decision_trace.identity_branch_gate.rule_id` must be `REQUIRE_GAMMA_DELTA_TCR_ANCHORS` and `passed=true`. A failed gate must prevent either leaf from becoming `stable_id`.
- `IL17A_gdT` remains the canonical identity even when `primary_state=Stress`, producing a display label such as `Stress_IL17A_gdT`; do not collapse the identity-defining type-17 program into `state_list` alone.
- A dominant coherent off-parent contaminant uses `formal_identity_fallback=off_parent_lineage_reassignment`, requires manual review, and has `auto_merge_allowed=false`. Coherent parent plus off-parent programs use `formal_identity_fallback=mixed_parent_off_parent_lineages`, return the nearest shared ancestor, and list both components.
- Cross-species Human-panel transfer requires `cross_species_inference=true` and panel provenance.
- Every non-R0 result requires manual review; minimal evidence cannot receive high confidence.
- `validated_external_candidate` requires at least two independent sources, manual review, and confidence below high until formal promotion. Boundary-defined identities such as DC3 additionally require current-case cell-level or resolving-reclustering evidence.
- `researched_branch_fallback` requires `formal_identity_fallback=branch_identity_no_supported_leaf`, at least two independent sources, manual review, confidence below high, explicit competing-candidate rationale, and no descendant of that branch anywhere in the final table.

The final workbook contains exactly `注释结果`, `详细证据`, and `说明与数据来源`. The main sheet keeps identity, developmental stage, state, quality score, mixed/doublet risk, and concise judgment evidence, without JSON, full paths, blank manual-entry columns, or duplicated mapping sheets. Automatic filters are disabled and row heights are compact. Every `Multi_cell` row and every row tied at the red endpoint of the quality-score scale must apply a static red fill to `中文名称`; this is a visual warning only and must not modify the annotation text. QA records cluster order, label normalization, knowledge-base/core/config versions and hashes, cross-species calls, mixed/doublet blocks, and identity-state separation.
