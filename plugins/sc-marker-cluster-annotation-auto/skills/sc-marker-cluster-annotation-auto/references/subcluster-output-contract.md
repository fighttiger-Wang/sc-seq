# Output contract and naming

> 本文件由 SKILL.md 原文逐行下沉（verbatim）；文中 `references/...` 链接均相对 skill 根目录（SKILL.md 所在目录）。

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

Keep four decisions separate: `identity` (the biological label),
`identity_resolution` (`specific`, `parent_level`, `unresolved`, or
`provisional`), `boundary_status` (`none`, `off_parent`, `mixed`,
`contamination_suspected`, or `technical_quality`), and downstream
`review_status`/`downstream_eligible`. A parent-level label is a fallback only
when the specific identity gate fails or remains unknown; UMAP adjacency or a
request for visual uniformity cannot trigger parent fallback. A conditional
specific label may remain usable for UMAP, but it is not eligible for
quantitative downstream use by default.

For sibling clusters, consistency constrains resolution and review handling,
not biological label equality. If similarly placed siblings have no decisive
case-level discriminator, keep the same resolution and review level. If their
final identities differ, record `discriminator_evidence_ids`; never copy one
cluster's label to another solely because their UMAP regions are adjacent.

Use the versioned naming dictionary. Established unambiguous abbreviations such
as `gdT` and `Tn` are allowed; short common labels such as B cell and T cell
remain full. One biological identity has one canonical spelling; display
qualifiers such as `_provisional` are standardized evidence-level disclosures,
and `_state_` labels are standardized identity-plus-state displays; neither is
a new ontology identity.
