# Taxonomy and naming

Use the approved stable IDs and parent relationships in `cell-annotation-knowledge-base.v2.json`.

- Species share one ontology and use exact-species Marker panels where available. If no exact panel exists, use documented cross-species transfer with ortholog/program conservation, reduced confidence, and manual review.
- Select the finest reliable node for `stable_id`; major mode displays the nearest enabled major ancestor, while subcluster mode displays the finest reliable within-parent node.
- Enable `core_multi_tissue` and tissue modules matching the confirmed tissue.
- Allow different branches to stop at different depths. Require consistency only among siblings under the same parent.
- Allow repeated standard IDs. Never add top-marker prefixes solely for uniqueness.
- Store identity, state, disease role, developmental stage, and tissue specialization separately.
- B lineage hierarchy is fixed as `Developing_B > Pro_B/Pre_B/Immature_B/Transitional_B`, `Mature_B > Naive_B/Memory_B/GC_B`, and `Antibody_secreting_B > Plasmablast/Plasma_cell`, all below `B_cell`.
- `Developing_B`, `Mature_B`, and `Antibody_secreting_B` are structural parents. Do not mix them with their descendants in one final subcluster mapping.
- `Naive_B` is a mature B identity, not a synonym for all `Mature_B`. `Pre_B`, `Immature_B`, and `Transitional_B` are distinct developmental stages.
- Keep Cycling separate from identity even when the display label is `Cycling_<Identity>`.
- Store all states in `state_list` and select one lineage-specific `primary_state`. Keep the displayed cell-type label equal to the short canonical identity; state appears only in its own column.
- Treat `Naive_like_gdT` and `IL17A_gdT` as approved gamma-delta descendants with `node_kind=identity_state_boundary`. Their defining developmental/effector program is part of the subtype boundary, while orthogonal programs such as Stress, IFN, Cycling, or Exhausted remain in `state_list` and may supply the displayed prefix.
- `CD4_Tex` and `CD8_Tex` are deprecated legacy boundary nodes, not selectable identities. Encode the branch or supported subtype in `stable_id` and exhaustion in `primary_state/state_list`; the workbook shows `CD4_T` or `CD8_Tem` in the identity column and `Exhausted` in the state column.
- A coherent `CD4_T` or `CD8_T` branch without a sufficiently supported finer leaf is an interim evidence-limited result (`formal_identity_fallback=branch_identity_no_supported_leaf`) that triggers targeted subtype research. It is not a normal final identity when any descendant of that branch appears in the same table. After a documented two-source search, retain it only as `researched_branch_fallback` when the entire final branch remains at that depth; otherwise stop delivery and request more evidence.
- Never rename `IL17A_gdT` to `CD4_Th17`: both may share `IL17A/RORC/CCR6`, but their receptor branches are distinguished by gamma-delta TCR anchors versus CD4 alpha-beta anchors.
- Use concise conventional IDs such as `Tn`, `DNT`, `CD4_Tn`, `CD8_Tcm`, and `CD8_Tem`. Avoid long prose names and decorative brackets or special symbols.
- Use standard English stable ID, standard Chinese name, and aliases. Keep final identifiers portable with Chinese characters, ASCII letters, digits, and `_`.
- Treat M1/M2, TAM, CAF, malignancy, angiogenic, inflammatory, and related context programs as state/role unless the approved node explicitly defines a stable identity.
- Never use dataset-wide `T_NK_cell`. Resolve T/NK per cluster and mark unresolved coherent conflicts as mixed/suspected-doublet with automatic merging blocked.
- Permit formal cross-species labels only with panel species, target species, evidence IDs, and `cross_species_inference=true` recorded.

Use `legacy-migration.v2.json` for old-project remapping.
