# Taxonomy and naming

Use the approved stable IDs and parent relationships in `cell-annotation-knowledge-base.v2.json`.

- Species share one ontology and use exact-species Marker panels where available. If no exact panel exists, use documented cross-species transfer with ortholog/program conservation, an explicit evidence-gap statement, and manual validation advice.
- Select the finest reliable node for `stable_id`; major mode displays the nearest enabled major ancestor, while subcluster mode displays the finest reliable within-parent node.
- Enable `core_multi_tissue` and tissue modules matching the confirmed tissue.
- Allow different branches to stop at different depths. Require consistency only among siblings under the same parent.
- Allow repeated standard IDs. Never add top-marker prefixes solely for uniqueness.
- Store identity, state, disease role, developmental stage, and tissue specialization separately.
- Store all states in `state_list` and select one lineage-specific `primary_state`. Keep the displayed cell-type label equal to the short canonical identity; state is shown only in its own column.
- Use standard English stable ID, standard Chinese name, and aliases. Keep final identifiers portable with Chinese characters, ASCII letters, digits, and `_`.
- Treat M1/M2, TAM, CAF, malignancy, angiogenic, inflammatory, and related context programs as state/role unless the approved node explicitly defines a stable identity.
- Never use dataset-wide `T_NK_cell`. Resolve T/NK per cluster and mark unresolved coherent conflicts as mixed/suspected-doublet with automatic merging blocked.
- Permit formal cross-species labels only with panel species, target species, evidence IDs, and `cross_species_inference=true` recorded.
- Prefer concise conventional identifiers such as `Tn`, `CD4_Tn`, `CD8_Tcm`, and `CD8_Tem`; avoid long prose labels and special-symbol decoration.

Use `legacy-migration.v2.json` for old-project remapping.
