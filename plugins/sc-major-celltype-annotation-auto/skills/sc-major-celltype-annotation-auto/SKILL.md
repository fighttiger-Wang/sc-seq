---
name: sc-major-celltype-annotation-auto
description: Evidence-first major-celltype annotation for mixed/all-cell single-cell datasets from average-expression plus marker tables or Seurat objects across tissues and species. Use for 大类注释、主要细胞类型注释 and mixed-lineage annotation requiring an approved multi-tissue ontology, exact-species panels or confidence-capped cross-species transfer, per-cluster T/NK resolution, mixed/doublet blocking, identity-state separation, deterministic QA, and compact Excel delivery.
---

# Single-cell major-celltype annotation

Complete the workflow after one invocation. Ask one consolidated question only when mandatory metadata remains unresolved after scoped E-drive discovery.

## 1. Route and confirm context

Read `references/context-and-level-routing.md`. Confirm species, tissue, experimental system, parent population, parent kind, and project vocabulary.

- Use major mode only for genuine mixed/all-cell collections.
- Route known-lineage or fine-subtype work to `$sc-marker-cluster-annotation-auto`.
- Treat project `Markergene_list.xlsx` as observed sample evidence, never as the annotation standard.
- Use `references/cell-annotation-knowledge-base.v2.json` as the approved runtime taxonomy and Marker source.
- Enable `core_multi_tissue` plus tissue modules matching the confirmed tissue.

## 2. Enforce the major boundary

- Set `annotation_level=major`.
- Start with core outputs `T_cell`, `NK_cell`, `B_cell`, `Myeloid_cell`, `Epithelial_cell`, `Endothelial_cell`, `Stromal_cell`, `Erythroid`, and `Megakaryocyte`.
- Permit tissue-module major outputs when enabled, including hepatocyte/cholangiocyte, neural, muscle, marrow progenitor/MSC, mesothelial, and reproductive lineages.
- Map every supported subtype to the nearest enabled major ancestor. Retain finer evidence in audit fields.
- Allow repeated standard labels; `cluster_id` supplies uniqueness. Never add a top-marker prefix merely to distinguish clusters.
- Keep identity, state, disease role, developmental stage, and tissue specialization in separate fields and separate workbook columns.
- Use the short canonical identity alone as the displayed cell-type label. Preserve all states in `state_list` and one `primary_state`; never prefix or suffix the identity with state.
- Treat TAM, CAF, M1/M2, and malignancy as roles/states, not stable base identities.

## 3. Resolve T/NK per cluster

- Resolve each cluster independently from coherent CD3/TCR and NK-specific programs.
- Do not collapse unrelated T and NK clusters because one cluster is unresolved.
- Prefer `T_cell` when CD3/TCR evidence is coherent and NK-like evidence is limited to shared cytotoxic genes.
- Prefer `NK_cell` only with a coherent NK-specific program and weak/absent CD3/TCR evidence.
- When coherent T and NK programs coexist, output `Multi_cell` / `多细胞`, set `mixed_population=true`, `suspected_doublet=true`, `manual_review=true`, and `auto_merge_allowed=false`; list both components and require cell-level review.
- Never use `T_NK_cell` as a dataset-wide fallback.

## 4. Load rules

Read before annotation:

- `references/marker-guidance.md`
- `references/taxonomy-and-naming.md`
- `references/evidence-scoring-policy.md`
- `references/output-schema.md`
- `references/automation-and-permissions.md`
- `references/case-learning-registry.md`
- `references/cell-annotation-knowledge-base.v2.json` for targeted node/panel lookup
- `references/legacy-migration.v2.json` when migrating an old project

Treat the knowledge base, evidence core, configuration, and snapshot hashes as one versioned contract. Do not hand-edit vendored files independently of the maintained shared source.

## 5. Normalize and preflight

Accept paired tables or a Seurat object. Preserve raw inputs. Missing genes are unknown in positive-marker-only mode and zero only in a verified full ratio table.

```bash
python3 scripts/prepare_annotation_auto.py \
  --avg <average.xlsx|tsv|csv> --markers <Markergene_list.xlsx> \
  [--ratios <full-gene-cluster-ratio.tsv>] \
  [--gene-map <source-to-canonical.tsv>] \
  [--cell-evidence <per-cluster-validation.json>] \
  --workspace-root <workspace-root> --output-dir <run-dir> \
  --species <confirmed> --tissue <confirmed> \
  --annotation-level major --parent-population <confirmed> --parent-kind <mixed|lineage|state>
```

The preflight must record knowledge-base/core/config versions, snapshot hashes, active tissue modules, evidence mode, matrix semantics, cluster order, and source paths.

## 6. Annotate

Read `annotation_evidence_digest.json` first and open the full pack only for targeted conflicts.

For every cluster:

1. Treat deterministic scores, node-specific Marker requirements, risk level, provenance, and review action as immutable evidence output.
2. Match the approved species/tissue panel using core, supportive, exclusion, and confounder evidence.
3. Assign the nearest enabled major ancestor supported by a coherent program.
4. Keep the finest supported node in `stable_id`/audit fields even when the displayed major label is broader.
5. Preserve `parent_path`, `tissue_module`, panel species, evidence IDs, and `cross_species_inference`.
6. Prefer an exact-species panel. When none exists, permit Human-panel or nearest-supported-species transfer only with ortholog/program conservation, `cross_species_inference=true`, retained panel provenance, reduced confidence, and manual review.
7. Populate `state_list` and the lineage-specific `primary_state`, while keeping `display_label` equal to the identity.
8. Require `manual_review=true` for every non-R0 risk. Do not assign high confidence in minimal mode.
9. Never output `Cell`. If no candidate is coherent and there is no mixed-population evidence, run targeted ontology/atlas/literature resolution; block formal delivery when no defensible identity can be established.
10. Mark coherent cross-lineage conflicts as `Multi_cell` / `多细胞`, retain concrete identities in `possible_components`, flag mixed/suspected-doublet risk, and block automatic merging.
11. Use `label_basis=canonical_subtype`; do not use marker-prefixed fallback labels in major mode.
12. If the approved knowledge base lacks a plausible identity, generate additional candidates and validate them against coherent positive and competing programs. Use `validated_external_candidate` only with at least two independent sources, reduced confidence, manual review, and later multi-case regression before promotion into the approved standard.

Populate `annotation_records.json` in normalized cluster order.

For every external candidate, retain structured `literature_details` containing title, DOI or PMID, species, tissue, and the supported conclusion. Unstructured citation strings alone do not satisfy the shared automatic-promotion gate.

## 7. Build and deliver

```bash
python3 scripts/build_annotation_workbook.py \
  --records <run>/annotation_records.json \
  --evidence <run>/annotation_evidence_pack.json \
  --workspace-root <workspace-root> \
  --output <run>/大类细胞注释结果.xlsx
```

Require structural QA for schema, order, portable labels, state grammar, provenance fields, confidence caps, mixed/doublet flags, and auto-merge blocking. Copy only the QA-passed final workbook to the unique original E-drive input directory without overwriting an existing file.

After QA passes, the builder must register the de-identified case in the shared E-drive case registry and write `<workbook>.case-registry.json`. A registration failure does not invalidate the workbook, but it must be reported explicitly and case accumulation must not be claimed.

## 8. Completion gate

- Confirm all clusters are present in identical order on result sheets.
- Confirm all labels are approved ontology IDs or enabled tissue-module major outputs.
- Reject `Cell` unconditionally in both major and subcluster output. Permit `Multi_cell` only when `mixed_population=true`, `possible_components` is populated, manual review is required, and automatic merging is blocked.
- Confirm repeated labels have no artificial top-marker prefix.
- Confirm unresolved T/NK clusters are isolated for review and do not alter clear T/NK clusters.
- Confirm `stable_id`, `parent_path`, `tissue_module`, `disease_role`, `state_list`, `primary_state`, panel species, and cross-species provenance are populated.
- Confirm every mixed/suspected-doublet cluster has `auto_merge_allowed=false`.
- Confirm identity labels contain no state prefix and state remains visible in its own column.
- Confirm the workbook contains only `注释结果`, `详细证据`, and `说明与数据来源`, with filters disabled and compact row heights.
- Confirm the final workbook and `.qa.json` record knowledge-base/core/config versions and hashes.
- Confirm the case-registry sidecar is `registered` or `duplicate`; report `failed` explicitly.
