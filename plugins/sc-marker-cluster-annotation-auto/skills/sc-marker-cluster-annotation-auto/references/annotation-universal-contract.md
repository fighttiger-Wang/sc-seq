# Universal annotation contract

This contract is shared by major-celltype and subcluster annotation. The two
skills use different candidate vocabularies, but they must use the same
biological reasoning and workbook contract.

## Biological decision model

Annotation is a qualitative expert decision, not a score optimization task.
Never create or use an aggregate quality score, confidence grade, candidate
score, weighted sum, score margin, or ranked-candidate table.

For every cluster, evaluate the following items separately and record each
applicable gate as `通过`, `不通过`, `未确定`, or `不适用`:

1. identity-anchor program;
2. broader parent-lineage program;
3. sibling/competing identity programs;
4. explicit exclusion or incompatible programs;
5. tissue-relevant off-parent programs;
6. developmental and state programs;
7. UMAP neighborhood, continuity, repeated-label islands, and marker/topology
   agreement;
8. mixed-population, doublet, ambient-background, debris, and low-quality
   explanations.

Raw measurements remain evidence attached to individual genes. Preserve
available `mean_expr`, `expr_ratio`, `log2FC`, `pct.1`, and `pct.2`; use `NA`
when a value is absent and never infer zero unless a verified complete matrix
explicitly supports that interpretation. Do not collapse these measurements
into one number.

Identity anchors and coherent multi-gene programs have priority. A single
marker, one high average, a shared pan-lineage gene, or one state marker cannot
define identity. Evaluate positive and negative evidence together and keep
identity, development, state, abnormality, and handling as separate concepts.

Every cluster receives a gate-reviewed plotting decision. In subcluster work,
incomplete evidence triggers further sibling comparison, exclusion review, and
targeted literature research; it does not force a fine-grained subtype. A
parent-level, unresolved, provisional, manual-review, merge, or recluster
decision is valid when the expert plotting standard is not reached.

## UMAP and mixed populations

Review every cluster on the complete UMAP. UMAP is mandatory consistency
evidence but never a standalone classifier. A disconnected repeated label,
boundary position, or marker/topology conflict requires an explicit audit.

Cluster-level averages may show competing programs but cannot prove same-cell
co-expression or doublets. Retain a clearly dominant identity. Use
`Multi_cell` only when no coherent program is dominant or supplied cell-level
evidence confirms multiple component populations. Never automatically delete,
filter, merge, or modify cells.

## Stable workbook contract

The final Excel workbook contains exactly these sheets in this order:

1. `绘图列表`
2. `注释结果`
3. `详细证据`
4. `细胞类型与文献`
5. `说明与数据来源`

`绘图列表` contains exactly `Cluster` and `Celltype_EN`. `注释结果`,
`详细证据`, and `绘图列表` contain every cluster, use exact cluster-ID joins,
and share numeric ascending order followed by natural alphanumeric order.
Repeated labels are allowed. `Celltype_EN` must match `[A-Za-z0-9_]+` and must
not be decorated with cluster IDs or marker prefixes. In subcluster work it
must preserve a supported leaf, but a final mapping must not co-display that
leaf with any ontology ancestor. Different independent branches may remain at
different depths; an ancestor-descendant conflict must be resolved with
same-level evidence, an approved residual leaf, or a blocked/recluster outcome.
Neutral context, state, program, disease-role, and topology qualifiers remain
in dedicated fields and must not be concatenated into `Celltype_EN`. A
shortened professional name is permitted only when it is a recognized
naming-dictionary abbreviation and receives explicit expert naming approval.

The result sheet contains no score or confidence field. The evidence sheet has
one row per cluster and includes the final identity, parent context, primary and
competing programs, supporting/conflicting/missing markers, qualitative gates,
off-parent audit, state/development evidence, UMAP audit, mixed/doublet
interpretation, rationale, gaps, handling, identity resolution, boundary/purity
status, review status, downstream eligibility, sibling consistency status, and
current-case discriminator evidence IDs.

Marker evidence is rendered as, for example:

```text
FGFBP2(mean=4.67, ratio=70.20%, log2FC=1.74, pct.1=70.20%, pct.2=14.30%)
```

`细胞类型与文献` contains exactly `细胞类型`, `文献`, `经典鉴定 Marker`,
and `本次鉴定使用的 Marker`. One cell type x one reference is one row, cells
are not merged, every final type has at least one source, and links are
clickable. `说明与数据来源` contains `项目 | 内容`, displays filenames only,
and records context, modes, metric definitions, versions, run time,
constraints, sorting/red-fill rules, limitations, and the no-auto-modification
declaration.

Use fixed widths and fixed row heights. Disable wrapping, shrink-to-fit, and
autofilters so long text stays intact but is visually clipped and remains
available in the formula bar. Freeze the first row in every sheet; additionally
freeze the first three columns in `注释结果` and `详细证据`, and the first column
in `细胞类型与文献`.

Apply a static red background to the plotting label in `绘图列表/Celltype_EN`
and, when present, the evidence label in `注释结果/中文名称` when a cluster
carries a coherent significant state program, `Multi_cell`, suspected doublet,
low-quality/debris/background interference, or lineage/off-parent boundary.
The fill is a visual warning only: it must not alter the machine-readable
`Celltype_EN` value, and plotting scripts must continue to consume the clean
label text. One isolated state marker does not trigger red fill. A conditional
label can remain UMAP-usable while being ineligible for quantitative downstream
analysis; store that handling decision in structured fields rather than in the
label text.

Expert review status is evidence-derived, never cluster-ID-derived. `passed`
is invalid when a mandatory identity gate is failed or unknown, when a material
off-parent/boundary/background/mixed flag is present, when a material evidence
gap remains, or when a marker/UMAP conflict is unresolved. The builder must
reject such contradictions instead of silently downgrading or accepting them.

Keep `identity`, `identity_resolution`, `boundary_status`, `review_status`, and
`downstream_eligible` as separate decisions. A parent-level fallback is allowed
only when the specific identity gate fails or is unknown; UMAP adjacency and
visual uniformity do not justify a fallback. A conditional specific label may
remain in the plotting map, but it is not downstream-eligible by default.

For same-parent sibling clusters, consistency constrains the resolution and
review level rather than forcing biological label equality. A different final
identity for similar neighboring clusters requires current-case discriminator
evidence; otherwise retain the same conservative resolution/review level and
make the unresolved comparison explicit.
