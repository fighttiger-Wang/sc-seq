---
name: sc-marker-cluster-annotation-auto
description: Accelerated evidence-first subcluster annotation within a known parent population from paired average-expression and marker tables or Seurat objects across tissues and species. Use for 亚群注释、亚型注释、细分细胞类型注释 requiring selective reuse of approved evidence, all-cluster UMAP review, temporary cluster-to-celltype mapping, research-first resolution of broad or conflicting calls, immediate validated-candidate promotion after full registered regression, strict table-wide hierarchy consistency, identity-state separation, mixed/doublet blocking, and compact three-sheet Excel delivery.
---

# Single-cell subcluster annotation

Complete the workflow after one invocation. Ask only for mandatory metadata genuinely absent from the request and scoped E-drive context.

## 1. Confirm scope

- Set `annotation_level=subcluster`.
- Confirm species, tissue, `parent_population`, and `parent_kind`.
- Route true all-cell major annotation to `$sc-major-celltype-annotation-auto`.
- For a lineage parent, treat descendants as the expected annotation branch, but never hide contamination behind a hard filter. When verified average-expression and full detection-ratio data are present, score tissue-relevant off-parent lineage sentinels in parallel.
- For a state-based parent, resolve every coherent lineage independently and preserve the shared state separately.
- Use project `Markergene_list.xlsx` only as observed sample evidence.

## 2. Load the approved standard

Read:

- `references/marker-guidance.md`
- `references/taxonomy-and-naming.md`
- `references/evidence-scoring-policy.md`
- `references/output-schema.md`
- `references/automation-and-permissions.md`
- `references/acceleration-and-umap-workflow.md`
- `references/case-learning-registry.md`
- `references/myeloid-boundary-gates.md` when the parent or a competing candidate is Myeloid
- `references/cell-annotation-knowledge-base.v2.json` only for targeted parent/node/panel and cross-lineage-sentinel lookup
- `references/legacy-migration.v2.json` for old-label conversion

Treat the approved knowledge base as the runtime source of truth. Load global policy, the current parent lineage, and all cross-lineage contamination sentinels; do not load unrelated detailed lineage panels. Reuse stored evidence IDs and sources unless a missing candidate, marker/UMAP conflict, or new evidence triggers research.

## 3. Annotation policy

- Annotate every cluster to the finest reliable identity supported within its parent branch.
- Require consistency only among siblings under the same parent. Different lineages may stop at different depths.
- Allow repeated standard IDs; `cluster_id` provides uniqueness.
- Never add `<top_marker>_` merely to distinguish repeated canonical labels.
- Use a marker-defined fallback only when no approved canonical node is defensible; keep it broad, auditable, and under manual review.
- Do not finalize `branch_identity_no_supported_leaf` on first pass. Treat it as evidence that the approved panel, candidate coverage, or decision strength may be insufficient. Trigger a targeted resolution-search pass before accepting any broad CD4/CD8 branch label.
- Keep identity, state, disease role, developmental stage, and tissue specialization separate in both records and workbook columns.
- For B lineage, use `B_cell > Developing_B > Pro_B/Pre_B/Immature_B/Transitional_B`, `B_cell > Mature_B > Naive_B/Memory_B/GC_B`, and `B_cell > Antibody_secreting_B > Plasmablast/Plasma_cell`.
- Treat `Developing_B`, `Mature_B`, and `Antibody_secreting_B` as structural parents, not final subcluster labels when a supported child exists.
- Never mix a normal ontology ancestor label with any of its descendants in one final subcluster mapping. A genuine incompatible mixture must use `Multi_cell` / `多细胞`, retain explicit components, remain visibly under manual review, and never merge automatically.
- Store B maturity in `developmental_stage`; do not use `Mature_B` as a substitute for `Naive_B`, `Memory_B`, or `GC_B`.
- Keep `Cycling` as state. Render `Cycling_Pro_B`, `Cycling_Pre_B`, or `Cycling_Plasmablast`; never create a stable identity named `Cycling_B`.
- In full-ratio mode, require the configured number of directionally supported core markers for a leaf identity. Do not treat mere detection of half a panel as coherent evidence; broad lineage markers, ambient immunoglobulins, and weak dataset-wide expression cannot establish a subtype.
- Apply absolute exclusion gates at identity boundaries. In particular, high retention of both `MS4A1` and `PAX5` blocks terminal `Plasmablast`/`Plasma_cell` calls even when cycling or isolated secretory genes are present. Require a coherent antibody-secretion/ER program for antibody-secreting identities.
- Arbitrate B-cell boundaries as programs: use `IGHM/IGHD/FCER2A` against a coherent memory program for Naive versus Memory; use `CD24A/CD93/VPREB3/IGHM` plus retained B-lineage identity against terminal plasma markers for Immature versus Plasma; use pre-B receptor/recombination support and mature-B exclusion to distinguish Pre_B from Pro_B and mature B.
- Preserve all detected states in `state_list` and retain the lineage-specific highest-priority state in `primary_state`; keep the displayed cell-type label equal to the identity.
- Do not make `Cycling` the primary state merely because cell-cycle genes are detected. Compare the completeness and relative dominance of S/G2M programs with activation and differentiation programs, then use embedding separation only as supporting evidence. A modest cycling signal in an activated mature or antibody-secreting B cluster may remain secondary.
- When CD8_Tem identity and exhaustion are both supported, output identity `CD8_Tem` and state `Exhausted` in separate columns.
- Require a CD4/CD40LG branch anchor before any CD4 leaf and a CD8A/CD8B/CD8B1 branch anchor before any CD8 leaf in full-ratio mode. Shared exhaustion, naive, memory, activation, or cytotoxic programs cannot determine the CD4/CD8 branch.
- In positive-marker-only mode, treat an unobserved CD4/CD8 branch anchor as unknown and do not formalize a branch-specific leaf; fall back to the confirmed T parent while retaining the weak subtype candidates for review.
- Use generic `Tn` when a coherent naive T program is present but CD4/CD8 branch evidence is not defensible. Use `DNT` when coherent T/Tn evidence coexists with a dataset-relative double-negative phenotype and gamma-delta evidence is insufficient; do not infer `gdT` from weak absolute receptor expression alone.
- Never emit `CD4_Tex` or `CD8_Tex` as a formal `Stable_ID`; they are legacy identity/state boundary labels only. Resolve the identity as `CD4_T`, `CD8_T`, or a supported finer subtype, and record persistent exhaustion only as `State=Exhausted`. If both CD4 and CD8 alpha-beta programs are coherent, return `T_cell`, mark incompatible sublineage mixture, and block automatic merging pending cell-level review.
- In full-ratio mode, require at least two `TRDC/TRGC1/TRGC2` anchors before accepting any `gdT` descendant. Within that verified branch, use `Naive_like_gdT` for a coherent `TCF7/LEF1/SELL/CCR7` program and `IL17A_gdT` for a coherent `IL17A/IL23R/RORC/RORA` program. `IL17A_gdT` is an identity-state boundary node in the gamma-delta branch, not `CD4_Th17` and not a generic state attached to unresolved `gdT`.
- Treat M1/M2, TAM, CAF, and malignancy as state/role fields.
- Require a coherent persistent program for Exhausted; PDCD1/LAG3 alone are insufficient.
- Retain Tfh and Tph as distinct nodes with explicit competing-program checks.
- Require TCR plus an NK-like program for NKT; cytotoxic genes alone are insufficient.
- In full-ratio mode, require at least two `CD3D/CD3E/CD3G/TRAC` anchors at detection ratio >=0.10 before accepting T or NKT. Weak aggregate TCR background cannot convert a strong NK cluster into NKT.
- If the expected parent program is weak and a coherent off-parent program clearly dominates, formally reassign the cluster with `formal_identity_fallback=off_parent_lineage_reassignment`, require manual review, and block automatic merging until subset provenance is verified.
- If coherent expected-parent and off-parent programs coexist, return `Multi_cell` / `多细胞` with `formal_identity_fallback=multi_cell_annotation`, mark mixed/suspected-doublet risk, list the concrete components, and block automatic merging. Never return `Cell` or a generic ontology ancestor.
- Check cDC2 against monocyte-derived programs explicitly.
- For Myeloid boundaries, require the program gates in `references/myeloid-boundary-gates.md`. Never let isolated `CSF3R`, `FCGR3B`, `XCR1`, `HLA-DRA`, or `CD74` override the complete competing program.
- `Immature_neutrophil` requires a coherent early/secondary granule program; incomplete mature-neutrophil receptors are not sufficient positive evidence.
- Treat aggregate APC + cDC2-like + monocyte evidence as a DC3 boundary candidate. Literature may nominate DC3 but cannot prove same-cell coexpression. When the aggregate programs are jointly coherent, deliver a conservative likely-mixed `Myeloid_cell` common-parent fallback with `mixed_population=true`, `suspected_doublet=false`, `manual_review=true`, and `auto_merge_allowed=false`; do not force DC3 or require RData merely to complete the annotation. Use cell-level validation or resolving reclustering only to refine the components and distinguish separate subpopulations from same-cell coexpression/doublets.
- Call Myofibroblast only with a coherent contractile plus ECM program.
- Call TA_cell only with intestinal lineage/developmental evidence and store Cycling separately.

## 4. Mixed/doublet policy

- When two coherent incompatible lineage programs coexist, output `Multi_cell` / `多细胞`, set `mixed_population=true`, `suspected_doublet=true`, `manual_review=true`, and `auto_merge_allowed=false`.
- Apply the same block to mutually exclusive sublineages inside one broad lineage. In particular, never directly finalize `CD4_Th17` or `IL17A_gdT` when full detection ratios support a CD4 alpha-beta program and at least two gamma-delta TCR anchors (`TRDC/TRGC1/TRGC2`) with near-scoring candidates. Set `possible_components=CD4_Th17;IL17A_gdT`, output `Multi_cell`, and require cell-level coexpression review or reclustering.
- Do not use detection proportions alone to claim that competing programs occupy the same cells or to confirm doublets. Aggregate evidence may support a conservative likely-mixed cluster call when multiple coherent incompatible programs coexist, but it must retain the common-parent fallback, manual review, explicit possible components, and blocked automatic merging.
- Do not automatically merge that cluster with either normal subtype.
- Use cell-level coexpression/doublet evidence to distinguish true doublets from unresolved mixed subpopulations.
- For T/NK, resolve each cluster independently; never trigger dataset-wide label collapse.

## 5. Normalize and preflight

Accept paired Excel files or a Seurat object. Preserve raw inputs and full marker order. Missing genes are unknown in positive-marker-only mode and zero only in a verified full ratio table.

```bash
python3 scripts/prepare_annotation.py \
  --avg <cell_avg_exp.xlsx> --markers <Markergene_list.xlsx> \
  [--ratios <full-gene-cluster-ratio.tsv>] \
  [--gene-map <source-to-canonical.tsv>] \
  [--cell-evidence <per-cluster-validation.json>] \
  [--umap <umap.png>] \
  --workspace-root <workspace-root> --output-dir <run-dir> \
  --species <species> --tissue <tissue> \
  --annotation-level subcluster --parent-population <parent> \
  --parent-kind <auto|lineage|state|mixed|unknown>
```

The preflight must record knowledge-base/core/config versions, active tissue modules, panel provenance, evidence mode, source paths, and normalized cluster order.
In a confirmed lineage subcluster run, retain coherent descendants outside their canonical tissue scope as review candidates instead of silently deleting them. Record `tissue_scope_match=false`, force manual review, and verify sample provenance.

## 6. Annotate compact evidence

Read `annotation_evidence_digest.json` first. For every cluster:

1. Treat deterministic scores, node-specific requirements, risk, provenance, and review action as immutable.
2. Match approved core/supportive markers and check exclusion/confounder programs.
3. Walk from the parent toward leaves and stop at the finest coherent node. When the deterministic result stops at `CD4_T` or `CD8_T` with `branch_identity_no_supported_leaf`, do not finalize it yet; enter the mandatory resolution-search pass below.
4. Populate `stable_id`, `parent_path`, `tissue_module`, panel species, evidence IDs, and `cross_species_inference`.
5. Populate `developmental_stage`, ontology node kind, canonical tissue scope, and tissue-context review fields.
6. Prefer an exact-species panel. When none exists, permit Human-panel or nearest-supported-species transfer only with ortholog/program conservation, `cross_species_inference=true`, retained provenance, reduced confidence, and manual review.
7. Populate `state_list` and `primary_state`, while keeping `display_label` equal to the identity.
8. Record up to three candidates, supporting/conflicting evidence, confidence, rationale, and a specific review action.
9. Require `manual_review=true` for non-R0 risks and tissue-context mismatches; cap minimal or tissue-mismatched evidence below high confidence.
10. If no candidate is coherent under a confirmed lineage parent, keep the confirmed parent only as an interim audit result; do not use it to bypass final table-wide hierarchy consistency.
11. Mark coherent incompatible programs as mixed/suspected-doublet and block automatic merging.
12. Audit off-parent programs whenever full ratios exist; distinguish a dominant contaminant from a true mixed cluster instead of forcing every cluster into the declared parent lineage.
13. Treat the approved knowledge base as the validation baseline, not a closed candidate box. If it lacks a plausible subtype, generate and research additional candidates. Use `validated_external_candidate` with at least two independent sources, reduced confidence, and manual review. Every external or manual identity override must also list at least two explicit supporting markers, retain the final identity in `candidate_labels`, and provide structured `override_validation` with a current-case method, evidence IDs, the supported identity, and the competing identity exclusion. It cannot bypass failed branch/program/absolute-negative gates, mixed/off-parent conflicts, or an incoherent ranked candidate. Boundary-defined identities additionally require sample-level or cell-level validation appropriate to the boundary. Promote only after current-case biological validation and all registered historical regressions pass; software regression alone cannot validate biology.
14. When a UMAP or equivalent embedding is available, review every cluster and write the structured audit described in `references/acceleration-and-umap-workflow.md`. Use topology as supporting evidence. Marker/UMAP conflict triggers integrated reassessment and may update marker standards or add a new subtype; neither source automatically overrides the other.
15. Audit every repeated final identity across the whole embedding. Disconnected same-label islands require concrete state, sample, or trajectory evidence; otherwise mark a conflict and complete research/reclassification before formal delivery. Never create an all-concordant audit independently of the final labels.
16. A disconnected repeated identity always has `auto_merge_allowed=false`. It may retain the same provisional identity after explanation, but automatic merging requires separate downstream manual adjudication.

Populate `annotation_records.json` in normalized cluster order.

For every external candidate, retain structured `literature_details` containing title, DOI or PMID, species, tissue, and the supported conclusion. Unstructured citation strings alone do not satisfy the shared automatic-promotion gate.

Treat deterministic unresolved output as a request for more evidence, not permission to choose an arbitrary leaf. UMAP review must challenge the proposed identity independently: an external/researched label with no same-label nearest neighbor cannot be marked plain `concordant` unless resolved current-case quantitative, cell-level, reclustering, reference, sample, or trajectory evidence is retained.

## 7. Mandatory resolution-search pass

Run this pass before workbook construction whenever any cluster has `branch_identity_no_supported_leaf`, `confirmed_parent`, or another evidence-limited ancestor result.

1. Re-score all approved descendants using the full evidence pack, including low-ranked positive markers, explicit negatives, dataset-relative anchors, tissue context, and competing programs.
2. Check whether a generic parent panel narrowly outscored a coherent child. Prefer the supported child when the configured descendant-projection rule passes; never let broader marker coverage alone suppress a coherent leaf.
3. Search curated cell ontologies, reference atlases, review articles, and primary literature for subtype candidates missing from the approved knowledge base. Use at least two independent sources and retain URLs/DOIs, retrieval date, species, tissue, defining program, and exclusions.
4. Use `validated_external_candidate` when an external identity is defensible. Use `researched_branch_fallback` only after the two-source search finds no reliable leaf, and only when that broad ancestor does not coexist with any normal descendant in the final table.
5. If a broad ancestor would coexist with a descendant and no defensible leaf can be resolved, stop delivery. Request cell-level coexpression, additional marker plots, or reclustering; do not lower only that cluster's annotation depth.
6. Treat recurring unresolved patterns as standard-coverage failures. Add validated candidates or adjust projection rules only after regression across historical cases, then version and republish the shared evidence core.

## 8. Build and deliver

Before formal publication/regression completes, build the temporary two-column mapping when requested:

```bash
python3 scripts/build_interim_mapping.py \
  --records <run>/annotation_records.json --evidence <run>/annotation_evidence_pack.json \
  [--umap-audit <run>/umap_review.json] \
  --workspace-root <workspace-root> --output <run>/temporary_cluster_mapping.tsv
```

If UMAP was supplied, the temporary mapping requires all-cluster review. Without UMAP, the temporary mapping is allowed but formal delivery remains blocked.

```bash
python3 scripts/build_annotation_workbook.py \
  --records <run>/annotation_records.json \
  --evidence <run>/annotation_evidence_pack.json \
  --umap-audit <run>/umap_review.json \
  --workspace-root <workspace-root> \
  --output <run>/<parent_population>_亚群注释结果.xlsx
```

The production builder must automatically copy the QA-passed workbook to the unique common directory of the original average-expression and marker inputs and write `<workbook>.delivery.json`. Do not finish with only a workspace path. Test/regression output directories are the only delivery exception.

Require deterministic QA for schema, labels, order, evidence provenance, state grammar, confidence caps, mixed/doublet flags, and auto-merge blocking. Copy only the final QA-passed workbook to the unique original E-drive input directory.

After QA passes, the builder must register the de-identified case in the shared E-drive case registry and write `<workbook>.case-registry.json`. A registration failure does not invalidate the workbook, but it must be reported explicitly and case accumulation must not be claimed.

## 9. Completion gate

- Confirm every label is the finest defensible approved or validated-external node after the mandatory resolution-search pass.
- Confirm repeated canonical labels remain identical and unprefixed.
- Confirm sibling consistency within each parent without forcing unrelated branches to equal depth.
- Confirm no normal final stable ID is an ancestor of another final stable ID in the same subcluster table; audit-only blocked mixed-parent fallbacks are the sole exception.
- Confirm every `branch_identity_no_supported_leaf` or `confirmed_parent` result either resolved to a leaf/external identity or caused delivery to stop. A researched broad fallback is allowed only when no descendant from that branch remains in the final table and its two-source audit is complete.
- Treat `delivery to stop` as an unfinished/blocked workflow, never as successful completion. Do not end the task with a temporary parent mapping when the user requested completed subcluster annotation; continue resolution using approved absolute-program gates, competing exclusions, and targeted research, or explicitly request the missing cell-level evidence.
- Confirm B-lineage `developmental_stage` and identity agree, including Immature/Transitional versus Naive/Memory and Plasmablast versus Plasma_cell.
- Confirm `stable_id`, `parent_path`, `tissue_module`, `disease_role`, `state_list`, `primary_state`, panel species, and cross-species provenance are populated.
- Reject semantic duplication: `stable_id` must not be `CD4_Tex`/`CD8_Tex`, and no final label may match `Exhausted_*_Tex`.
- Confirm display labels contain identity only and the state remains in a separate column.
- Confirm every CD4/CD8 leaf satisfies its recorded branch-anchor gate, and every coherent CD4-versus-CD8 mixed conflict is labeled `Multi_cell` with both components retained and automatic merging blocked.
- Confirm every `gdT` descendant satisfies the gamma-delta TCR gate; distinguish naive-like and type-17 programs when supported, and never infer `IL17A_gdT` from an IL17 program without gamma-delta anchors.
- Confirm generic `Tn` and `DNT` remain available when CD4/CD8 or gamma-delta branch evidence is insufficient, using dataset-relative anchors and negative conflicts rather than fixed absolute thresholds alone.
- Confirm every mixed/suspected-doublet cluster is labeled `Multi_cell` / `多细胞`, has populated `possible_components`, and has `auto_merge_allowed=false`.
- Reject `Cell` unconditionally as a final major or subcluster label. A non-mixed unresolved cluster must continue targeted resolution or stop formal delivery.
- Confirm every full-ratio run records the expected parent, off-parent candidate, reassignment/conflict status, and blocks automatic merging for both off-parent reassignments and parent/off-parent mixtures.
- Confirm an off-parent call has a coherent set of directionally supported anchors; a single shared marker plus weak keratin/background coverage cannot establish epithelial contamination or doublet risk.
- Confirm UMAP topology was used only as a low-margin consistency check, with identity and state decisions still grounded in marker programs and exclusion evidence.
- Confirm every cluster has a structured UMAP review and every marker/UMAP conflict has completed or reused research evidence. If UMAP is absent, permit only the temporary two-column mapping and block the formal workbook.
- Confirm a sample-specific marker/UMAP conflict was not marked resolved from literature alone. Require cell-level coexpression, sample metadata, trajectory metrics, reference mapping, or quantitative-QC evidence.
- Confirm every repeated final identity has a cross-island topology audit. A disconnected same-label cluster may remain concordant only with concrete state/sample/trajectory evidence; an unexplained disconnected island must be a resolved conflict before delivery.
- Confirm workbook QA records knowledge-base/core/config versions and hashes.
- Confirm every `Multi_cell` row and every row tied at the red endpoint of the quality-score scale has a static red fill on `中文名称`, so the warning remains visible in WPS without recalculation.
- Confirm the case-registry sidecar is `registered` or `duplicate`; report `failed` explicitly.
- Confirm `<workbook>.delivery.json` has `status=copied`, its destination is the unique original E-drive input directory, and the destination SHA-256 equals the workspace workbook. A workspace-only production workbook is not delivered.
- Confirm the workbook contains only `注释结果`, `详细证据`, and `说明与数据来源`, with filters disabled and compact row heights.
