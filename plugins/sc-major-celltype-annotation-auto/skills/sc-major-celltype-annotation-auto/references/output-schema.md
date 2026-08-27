# Output schema

Every annotation record contains:

| Group | Fields |
|---|---|
| Identity | `cluster_id`, `celltype_cn`, `celltype_en`, `stable_id`, `broad_type`, `fine_type`, `parent_path`, `tissue_module` |
| State/role | `state`, `state_list`, `primary_state`, `disease_role`, `display_label` |
| Species/provenance | `target_species`, `panel_species`, `cross_species_inference`, `marker_panel_evidence_ids`, `marker_panel_evidence_gate` |
| Evidence | `supporting_markers`, `conflicting_markers`, `candidate_labels`, `rationale`, `primary_evidence_major_label`, `formal_identity_fallback`, deterministic scores and decision trace |
| Risk | `mixed_or_doublet`, `mixed_population`, `suspected_doublet`, `mixture_type`, `possible_components`, `auto_merge_allowed`, `manual_review`, `review_action` |
| Naming audit | `label_basis`, `canonical_subtype`, `top_marker_gene`, `literature_source`, `naming_grammar`, `contextually_excluded_naming_markers` |

Rules:

- `stable_id` is the finest approved identity supported by the cluster.
- `Cell` is forbidden as a final label in every annotation mode. A coherent mixed/multiplet cluster uses `stable_id=Multi_cell`, Chinese name `多细胞`, populated `possible_components`, manual review, and `auto_merge_allowed=false`. A noncoherent non-mixed cluster must enter targeted research and block formal delivery if unresolved.
- Major mode may display its nearest enabled major ancestor; subcluster mode displays the finest defensible within-parent identity.
- `display_label` equals the identity. Store state separately in `state`, preserve all detected states in `state_list`, and retain one `primary_state` for prioritization.
- Repeated canonical labels remain identical; cluster ID provides uniqueness.
- A coherent incompatible lineage conflict requires `mixed_population=true`, `suspected_doublet=true`, `manual_review=true`, and `auto_merge_allowed=false`.
- Cross-species Human-panel transfer requires `cross_species_inference=true` and panel provenance.
- Every non-R0 result requires manual review; minimal evidence cannot receive high confidence.
- `validated_external_candidate` requires at least two independent sources, manual review, and confidence below high until formal promotion.

The final workbook contains exactly `注释结果`, `详细证据`, and `说明与数据来源`. The main sheet shows identity, developmental stage, state, quality score, mixed/doublet risk, and concise judgment evidence without JSON or full paths. Automatic filters are disabled, rows are compact, and no blank manual-entry columns are created. QA records cluster order, label normalization, knowledge-base/core/config versions and hashes, active tissue modules, cross-species calls, mixed/doublet blocks, and identity-state separation.
