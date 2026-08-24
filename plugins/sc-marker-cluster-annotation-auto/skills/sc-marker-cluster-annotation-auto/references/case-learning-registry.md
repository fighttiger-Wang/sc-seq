# Shared annotation case learning

Use the account-independent registry at `<shared-workspace-root>\.sc-annotation-knowledge`. Resolve `<shared-workspace-root>` from `CODEX_SHARED_WORKSPACE_ROOT`; when running from the source marketplace, it is the parent directory of `local-marketplace`.

## Registration gate

- Register only a final workbook whose `.qa.json` has `status=pass`.
- The subcluster skill is eligible from version `0.4.1`; this skill version writes its exact version into the registry call.
- One identity counts at most once per independent dataset. Re-clustering, re-annotation, repeated clusters, or revised workbooks from the same dataset strengthen the stored observation but do not add independent-case count.
- Store a de-identified evidence snapshot, hashes, species, tissue, parent, markers, exclusions, candidates, confidence, and literature metadata. Do not copy full expression matrices or customer names into the registry.
- Mixed/doublet, state, role, and ontology-root fallback records may be stored but cannot promote a stable identity.

## Literature metadata

For every knowledge-base-external candidate, populate `literature_details` with at least `title`, `doi` or `pmid`, `species`, `tissue`, and the supported conclusion. Plain DOI/PMID strings are retained but do not satisfy the automatic-promotion metadata gate.

For automatic Marker-panel learning, set `marker_observation_complete=true` only when `evaluated_markers` records the full evaluated positive/negative panel rather than a selected display list. Incomplete display-marker lists may accumulate as case evidence but must not automatically downweight existing rules.

## Completion behavior

The workbook builder writes `<workbook>.case-registry.json` after QA. Registration failure must not delete or block the validated workbook, but the task is incomplete until the failure is reported explicitly. Do not claim case accumulation when the sidecar status is `failed`.

Read `<shared-marketplace-root>\shared\sc-annotation-case-registry\policy.v1.json` when auditing thresholds or promotion behavior. Resolve `<shared-marketplace-root>` from `CODEX_SHARED_MARKETPLACE_ROOT` or from the marketplace containing `skill-pack.json`.
