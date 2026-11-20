# Decision logic and boundary behavior

> 本文件由 SKILL.md 原文逐行下沉（verbatim）；文中 `references/...` 链接均相对 skill 根目录（SKILL.md 所在目录）。

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
   [identity arbitration contract](identity-arbitration-contract.md).
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
   A registered specialization panel may add a conditional `下位亚类` only
   after its base identity program passes. For example, a coherent endothelial
   tip/angiogenic program may be retained as `Tip_endothelial` beneath a
   capillary identity. It is not forbidden, but it must not replace the base
   lineage, be inferred from UMAP alone, or be promoted from a state marker.
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
[open-world-research-workflow.md](open-world-research-workflow.md).
The ontology result may remain visible only as an explicitly unbound fallback.
Do not bind it formally until the exact `research_requests.json` is resolved.
Use a validated external candidate only with two independent sources and
current-case supporting markers; do not silently choose an arbitrary ancestor.
When research would replace the pre-research identity, require a current-case
competitor comparison with the prior identity, multi-gene support for the new
candidate, and explicit competing-program exclusion evidence; literature
plausibility alone cannot authorize a replacement.
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
[identity arbitration policy](identity-arbitration-policy.v1.json)
after candidate generation. Absolute, branch, exclusion, and boundary gates
establish eligibility only. State/development programs are evaluated after
identity competition, and UMAP is an audit after marker-supported arbitration;
neither may create or rescue an identity program.
