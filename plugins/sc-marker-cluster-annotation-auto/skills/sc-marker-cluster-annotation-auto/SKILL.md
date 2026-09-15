---
name: sc-marker-cluster-annotation-auto
description: Expert-style subcluster annotation within a declared parent population using average expression, detection ratio, marker statistics, UMAP topology, tissue/species context, and versioned literature verification.
---

# Subcluster annotation

Before making any annotation decision, apply the bundled [universal annotation contract](references/annotation-universal-contract.md). This versioned copy is included in the plugin so an installed cache does not depend on a marketplace checkout outside its package. This skill adds the parent-restricted sibling-level rules below; it does not replace the shared evidence, UMAP, naming, or workbook QA requirements.

Use this skill only when the supplied dataset is already restricted to one
parent population. Review every cluster at the most specific level supported
by its current evidence, but do not force a fine-grained label when the expert
plotting standard is not reached. Parent-level, unresolved, provisional,
manual-review, merge, or recluster outcomes are valid formal decisions when
the evidence cannot support a defensible subtype.

When the current evidence resolves some clusters to a registered leaf while
other clusters remain at that leaf's parent, preserve the supported leaf only
when its expert plotting verdict is `allow_specific_label`. Otherwise retain a
conservative parent or unresolved label and record the evidence gap. Mixed
parent/descendant labels are acceptable when they truthfully represent
different evidence resolution. Keep `下位亚类` for qualified comparisons or
additional refinements, not as a place to hide a supported identity from the
UMAP. States, programs, and disease roles remain separate fields and must not
be concatenated into `Celltype_EN`.

## Inputs

Require species, tissue/organ, parent population, average-expression input,
marker workbook, and a UMAP PNG with readable cluster IDs and legend. The
expression file has `gene`, `group`, `mean_expr`, `expr_ratio`, and `norm_expr`;
`expr_ratio` is detection ratio. Marker statistics may include
`Target_Cluster_mean`, `Other_Cluster_mean`, `log2FC`, `pct.1`, and `pct.2`.
Preserve parent scope and cluster IDs. Final output sorts numeric cluster IDs from small to large, then uses natural alphanumeric order for mixed IDs.

## Decision logic

For every cluster:

1. Establish the parent program without using it to hide contamination. Build a
   dataset-wide background profile and downweight signals present across most
   clusters, tissue-wide ambient programs, and housekeeping/QC genes.
2. Compare sibling candidates as complete programs: identity anchors first,
   explicit sibling exclusions second, differentiation programs third, and
   state/QC programs last. UMAP is supporting evidence. For high-risk
   unconventional-T boundaries, run the configured absolute program gate
   before leaf selection: NKT requires TCR plus distinct NK-receptor and
   cytotoxic programs; MAIT requires a coherent T program, alpha-beta branch
   support, and multiple MAIT-associated markers; DNT tolerates non-dominant
   receptor background but not a dominant competing CD4/CD8 or gamma-delta
   program.
   When multiple sibling programs pass, read the
   [identity arbitration contract](references/identity-arbitration-contract.md).
   Eligibility gates never grant automatic final-label priority: compare the
   complete competing programs and explicitly resolve one-sided dominance, a
   registered boundary identity, or an unresolved boundary before binding the
   label.
3. Jointly interpret `mean_expr`, `expr_ratio`, `log2FC`, `pct.1`, and `pct.2`.
   High expression in a few cells is not a broadly supported program; a modest
   signal across most cells may be meaningful. `norm_expr` must not be counted
   twice.
4. Audit tissue-relevant off-parent programs. A globally elevated epithelial
   program is background; a locally enriched multi-gene, high-prevalence program
   may indicate contamination, reassignment, or a mixed boundary. One shared
   marker is never enough for a doublet call.
5. Review every cluster on the full UMAP and audit repeated labels: neighboring
   types, continuous trajectories, disconnected same-label islands, isolated
   cycling/state islands, and marker/UMAP conflicts. Record an explicit identity
   action. A conflict may reject a provisional label only when integrated
   Marker and topology review selects an already-supported same-level candidate;
   UMAP alone cannot create or overwrite an identity.
   Formal delivery must bind the records to the output of
   `qualitative_evidence_core`: do not hand-author `evidence.json`,
    `records.json`, and `umap_audit.json` by copying a proposed label into all
    three files. A UMAP reassignment is valid only for a documented
    marker/UMAP conflict and only to a candidate present in the core's
    candidate-program audits.
    Formal UMAP delivery additionally requires an independently generated
    image/coordinate geometry artifact bound to the supplied UMAP SHA-256.
    `reviewed=true` and prose topology fields are declarations, not geometry
    evidence.
6. Resolve primary identity, then separately assign any
   `low_quality`, `background_interference`, `abnormal_state`, `debris`,
   `suspected_doublet`, or `mixed_population` flags. Flags may coexist.
7. If competing programs are complete and near-balanced, use `Multi_cell` with
   concrete components and red warning formatting. If one program dominates,
   retain its identity and explain the secondary signal as background,
   contamination, or state, and record the unresolved evidence explicitly.
8. Before formal workbook construction, require the expert plotting and naming
   gate. `allow_specific_label` is required for a specific subtype. Parent,
   unresolved, provisional, manual-review, merge, or recluster outcomes must
   be represented by structured verdict and handling fields; do not encode
   them by inventing a longer `Celltype_EN` string. An approved abbreviation
   requires a canonical full name and explicit expert naming approval.

## Boundary behavior

Never let a single receptor chain, a single shared marker, or a state marker
create a subtype. `SLC4A10`, `ZBTB16`, `TRDC`, and cytotoxic genes must be
interpreted as components of a complete program and against cross-cluster
background; aggregate expression cannot establish same-cell coexpression.

Do not infer subtype from a shared state program alone. Cycling, exhaustion,
interferon response, cytotoxicity, antigen presentation, and stress remain
states unless a coherent identity program supports a subtype. For every lineage
boundary record both candidate programs, prevalence, relative dominance,
exclusions, and the decision. If the knowledge base lacks a defensible leaf,
enter the executable open-world research stage described in
[open-world-research-workflow.md](references/open-world-research-workflow.md).
The ontology result may remain visible only as an explicitly unbound fallback.
Do not bind it formally until the exact `research_requests.json` is resolved.
Use a validated external candidate only with two independent sources and
current-case supporting markers; do not silently choose an arbitrary ancestor.
External research is also bounded by the source's semantic claim. Classify each
source as `identity`, `identity_like`, `state`, `program`, or
`lineage_identity`, preserve its verbatim qualifying wording, and bind no label
above the conservative level jointly supported by all sources. A `-like`,
`resembles`, or `similar to` statement cannot become the unqualified identity;
a state or program cannot become a literature-established stable identity; and
a lineage-derived label requires current-case lineage evidence, not aggregate
cluster expression. When the literature supports only a state/program, retain a
same-level neutral contextual identity and place the qualified comparison and
state in `下位亚类` and `细胞状态` rather than narrowing the ontology vocabulary.

Apply the versioned
[identity arbitration policy](references/identity-arbitration-policy.v1.json)
after candidate generation. Absolute, branch, exclusion, and boundary gates
establish eligibility only. State/development programs are evaluated after
identity competition, and UMAP is an audit after marker-supported arbitration;
neither may create or rescue an identity program.

## Output

Produce a cluster-level `cluster -> celltype_label` mapping usable for UMAP.
Keep the most likely主体细胞类型 even for impurity, low quality, abnormal,
debris, or suspected doublet clusters. Put abnormality, components,
characteristic genes, UMAP judgment, explanation, literature, and handling
recommendation in separate fields. Do not create confidence or score fields.
For a subcluster deliverable, `Celltype_EN` is the expert-approved identity
plotting label. It may contain a supported parent or descendant identity, but
only the structured expert verdict can authorize a specific subtype. Keep
state, program, disease role, and UMAP topology in dedicated evidence fields.
Never manufacture a state-qualified or Marker-derived plotting name. Use a
shortened professional name only when the naming dictionary and expert review
explicitly approve the abbreviation.
The UMAP mapping must remain machine-readable even when the biological call is
conditional: keep `Celltype_EN` as a clean canonical plotting label and put
`passed/conditional`, boundary, off-parent, background, and validation handling
in separate fields. A red fill in `绘图列表/Celltype_EN` is a visual warning only;
it must never change the cell value or be required by a plotting script. The
same clean `Celltype_EN` value must be present in `注释结果` for exact cluster
joins. A conditional label may therefore be usable for UMAP while being marked
manual-review-only for quantitative downstream analysis.
The `注释结果` sheet may additionally contain an optional `下位亚类` field
before `细胞谱系`: populate it only when a lower-level subtype is supported in
the current case, leave it blank otherwise, and never use it to alter the
existing identity, UMAP, state, or red-fill logic.
When a UMAP image is supplied, generate the independent geometry artifact with
`scripts/umap_image_facts.py` before formal construction and pass it to the
builder as `--umap-facts`. If the artifact is absent, stale, or bound to a
different image, formal workbook construction must stop.
Mark the annotation cell red when
the cluster should not be interpreted as a normal pure type; do not replace the
plotting label with `Doublet` or `Debris`.

Do not derive expert status, red warnings, or off-parent handling from cluster
IDs or a manually maintained cluster list. Derive them from the bound evidence
record and reject formal delivery when `passed` contradicts a failed/unknown
identity gate, a material boundary/off-parent/background flag, an unresolved
evidence gap, or a marker/UMAP conflict.

Use the versioned naming dictionary. Established unambiguous abbreviations such
as `gdT` and `Tn` are allowed; short common labels such as B cell and T cell
remain full. One biological identity has one canonical spelling; display
qualifiers such as `_provisional` are standardized evidence-level disclosures,
and `_state_` labels are standardized identity-plus-state displays; neither is
a new ontology identity.

## Expert review and case-driven optimization

Formal annotation is not complete when executable gates pass. Apply
[expert-review-and-optimization.md](references/expert-review-and-optimization.md)
to every cluster before formal workbook construction. Record the independent
review status, evidence basis, identity boundary, and a concrete case-specific
optimization recommendation. A missing review record blocks delivery. The
final response must summarize the expert review outcome and the highest-value
recommendations, including when no additional optimization is currently needed.

## Retrieval and reproducibility

This skill has an independent calibration counter. Its first five uses after
this skill/core/dictionary revision must verify involved types against current
literature and curated atlases. From use six onward retrieve only for
marker/context/UMAP conflicts or knowledge-base gaps. Record source, retrieval
date, species, tissue, supported program, exclusions, and adoption/rejection
rationale in a reusable evidence sheet.

Run preparation once without research evidence. If it emits
`status=research_required`, immediately use available online retrieval tools to
resolve every request; this is a required task action, not an optional report
note. Write a structured `research_evidence.json` bound to the emitted
`request_sha256`, then rerun preparation with `--research-evidence`. A DOI list,
article titles copied from memory, or a hand-authored `research_status=resolved`
is invalid. Formal workbook construction remains blocked until the research
artifact passes source independence, current-case multi-gene support, exclusion,
and hash checks. If UMAP review later exposes a new unexplained island or
identity conflict, rerun preparation with `--force-research` and a concrete
`--research-reason`; do not reuse an earlier request hash.

Record versions, hashes, counter, source paths, cluster order, parent context,
and the full UMAP audit. Formal delivery requires the fixed five-sheet workbook,
an independently generated `--umap-facts` artifact whose image hash matches the
supplied UMAP, and a hash-matching passing QA sidecar in the workspace build
location; legacy
four-sheet output is invalid. Deliver only the timestamped Excel workbook to
the supplied E-drive input directory and keep QA JSON sidecars in the workspace
unless the user explicitly asks for them. Do not automatically edit or filter
the underlying object.

Workbook formatting is part of the delivery contract. Use Cambria 11 as the
workbook font. Save content-fit column widths/row heights for `绘图列表`, for
frozen columns A:C in `注释结果`, for frozen columns A:C in `详细证据`, and for
frozen column A in `细胞类型与文献`; keep long text columns at fixed widths with
wrapping and shrink-to-fit disabled. In `细胞类型与文献`, the visible hyperlink
text in `文献` must show DOI/PMID identifiers when available, not the article
title, while preserving the clickable link.

For a blind test, invoke the preparation entry point with `--blind-test`.
Do not pass a prior annotation workbook, old records, old UMAP audit,
cluster-specific exclusions, or marker exclusions. The only label-bearing
artifact allowed in the blind run is the ontology's candidate-program
vocabulary. The model-facing digest redacts the qualitative core's
`stable_id`, `suggested_identity`, `primary_program`, major label, derived
rationale, and recommended action. Treat those fields in the internal evidence
pack as audit bindings, never as the annotation answer. First write an
independent provisional label from the current-case multi-gene programs and
the candidate audits; then perform a separate all-cluster UMAP review. UMAP
review must be read from the supplied image and must not be generated from the
core decision or from the provisional label. Final workbook construction is
allowed only after the independent records, UMAP audit, and internal evidence
binding all pass validation.

## Release handoff

When the user explicitly approves publication, defer the complete release to
the one-review marketplace workflow: increment the technical package version,
synchronize display and marketplace metadata, run registered regressions,
commit and push a `codex/` branch, create the PR, wait for CI, merge the exact
head SHA, verify stable `main`, establish a clean stable runtime registration,
and verify the real cache directories, manifests, and file hashes. Do not edit
an installed cache as source. The combined authorization may cover all of
these steps; do not insert a second routine merge or installation review.
After installation, report only `restart-required`. Declare the slash skill
active only when a restarted/new task is observed loading the expected
versioned `SKILL.md` cache path.

Never output generic `Cell`, mix ancestors and descendants, infer same-cell
coexpression from aggregate data, silently discard off-parent clusters, or
claim confirmed doublet from aggregate-only evidence.
