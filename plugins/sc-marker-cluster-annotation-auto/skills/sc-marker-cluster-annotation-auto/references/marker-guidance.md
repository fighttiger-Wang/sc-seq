# Marker guidance

Treat the approved Marker panel as the rule and project Marker tables as observations.

For each candidate node:

1. Check node-specific core-marker requirements.
2. Add supportive evidence.
3. Check exclusion markers and competing programs.
4. Review confounders and tissue context.
5. Fall back to the nearest reliable parent when the leaf rule is not satisfied.

Do not infer identity from one famous marker when the panel requires a program. In particular:

- Require coherent CD3/TCR evidence for T lineage and NK-specific anchors for NK.
- Require TCR plus an NK-like program and at least one cytotoxic anchor (`GNLY/GZMB/PRF1/FGFBP2`) for NKT; shared NKG7 or ZBTB16 alone is insufficient.
- Exclude a coherent gamma-delta receptor branch before accepting NKT. In Human full-ratio data, `TRDC/TRGC1/TRGC2` supported relative to the dataset outweigh shared `KLRD1/NKG7/XCL1` for this boundary; NKT must pass its dedicated TCR-plus-NK absolute program gate.
- In verified full-ratio data, require at least two `CD3D/CD3E/CD3G/TRAC` anchors at >=0.10 for a coherent T program. Low-level TCR background below this gate does not support T or NKT. Strong `NCR1/NKG7/KLRD1/FCER1G/TYROBP` with a failed T gate supports NK contamination.
- Require persistent exhaustion evidence; PDCD1/LAG3 alone do not establish Exhausted/Tex.
- Determine CD4 versus CD8 from branch anchors, not from the shared functional program: require CD4/CD40LG for CD4 descendants and CD8A/CD8B/CD8B1 for CD8 descendants in full-ratio evidence.
- Evaluate CD4, CD8, and gamma-delta anchors against both conservative absolute floors and their dataset-wide maxima. This prevents a low-depth but relatively specific branch program from being erased, while rejecting signals that are weak both absolutely and relative to other clusters.
- Use `Tn` for a coherent naive T program without defensible CD4/CD8 branch assignment. Use `DNT` when T/Tn evidence is coherent, CD4/CD8 anchors are absent by dataset-relative negative checks, and gamma-delta receptor evidence is insufficient.
- Treat exhaustion as an orthogonal state, never as the formal CD4/CD8 identity. Use `CD4_T`, `CD8_T`, or a supported finer identity leaf and add `State=Exhausted`; `CD4_Tex` and `CD8_Tex` are legacy-only migration labels. Treat simultaneous coherent CD4 and CD8 programs as an incompatible-sublineage mixture requiring parent fallback and cell-level review.
- Require at least two `TRDC/TRGC1/TRGC2` anchors at >=0.10 before accepting a gamma-delta descendant, and compare their complete-program prevalence against `TRAC/TRBC1/TRBC2`. A dominant alpha-beta program blocks gamma-delta leaves even when one or two gamma-delta transcripts are enriched; the reverse rule blocks CD4/CD8 leaves when gamma-delta dominates. If both are coherent but neither dominates, retain a boundary review and request cell-level/paired-TCR evidence. Only after branch arbitration, separate `Naive_like_gdT` (`TCF7/LEF1/SELL/CCR7`) from `IL17A_gdT` (`IL17A/IL23R/RORC/RORA`).
- Because the generic `gdT` panel contains broader receptor markers, prefer a more specific child only when its branch-defining gate passes, at least three identity anchors are supported, and explicit exclusions do not favor generic `gdT`. Record the biological precedence trace; otherwise retain `gdT` and state the missing leaf evidence.
- Distinguish Tfh from Tph using CXCR5/BCL6 versus CXCL13/PDCD1/MAF and explicit exclusions.
- Compare cDC2 against FCN1/S100A8/VCAN monocyte-derived programs.
- Require a complete Myeloid boundary program, not isolated anchors: neutrophil calls need commitment plus mature, early-granule, or activated-neutrophil support; DC3 calls need the registered APC, DC-specific, and competitive monocyte-specific programs. Cell-level validation refines purity or mixed-component claims but is not required to make the best-fit DC3 identity judgment.
- Require a contractile plus ECM program for Myofibroblast.
- Require intestinal developmental context for TA_cell; MKI67/TOP2A alone indicate Cycling.
- Require FOXI1/CFTR evidence and rarity review for Pulmonary_ionocyte.
- Require CNV/mutation/tissue evidence for malignant disease role.

Separate state programs from identity across every lineage. `CD83/ITGAX` indicate APC/DC-like activation, `PDCD1/LAG3` exhaustion, `MKI67/TOP2A` cycling, and shared cytotoxic genes activation/cytotoxicity; none can establish DC, exhausted-T, proliferating-cell, NK/NKT, or another identity without its coherent lineage program. `JCHAIN` alone likewise cannot establish plasma identity without the terminal secretion program.

Missing genes in positive-marker-only data are unknown, not zero. Cross-lineage coherent conflicts require mixed/doublet review and `auto_merge_allowed=false`.

The approved panel is a validation standard, not a closed candidate list. When a plausible subtype is absent or local candidates are noncoherent, search curated databases and primary literature. Require at least two independent sources, two explicit supporting markers, final-identity inclusion in `candidate_labels`, structured current-case `override_validation`, and explicit competing-program checks before using `validated_external_candidate`. Literature validates candidate biology but cannot substitute for sample-level or cell-level validation of a boundary-defined identity; promote only after biological validation and multi-case historical regression.

Background expression is a dataset-wide problem, not a lineage-specific exception. A secondary identity program may support a mixed/off-parent call only when it clears the common competing-program gate: a coherent identity-anchor set, multiple dataset-relative strong anchors, explicit exclusions, and a genuinely distinct ontology branch. Broad ancestors such as `NK_cell` support a coherent descendant such as `CD56dim_NK`; they are not independent rivals or mixture components. Apply this rule equally to TCR, cytotoxic, myeloid, epithelial, endothelial, stromal, and other programs.

Do not accept a generic CD4/CD8 branch solely because it contains more shared markers than every child. Re-open the sibling set, review weak-but-consistent Markers and exclusions, apply branch gates, and search for missing memory/effector or tissue-specialized identities. If evidence remains incomplete, retain the most defensible same-level identity with an explicit evidence gap and validation route.

A declared subcluster parent is a prior, not a hard filter. With full average-expression and detection-ratio evidence, audit tissue-relevant off-parent programs through explicit identity gates. Reassign a dominant coherent contaminant under review; if expected-parent and off-parent programs coexist without dominance, use `Multi_cell` with concrete components and block automatic merging.

Within T lineage, alpha-beta and gamma-delta receptor branches are incompatible sibling programs rather than an ordinary subtype boundary. First test dominance using complete receptor programs. One dominant program blocks the rival branch; only coherent non-dominant dual programs are flagged for boundary/mixed-population review. For an IL17-producing cluster, do not choose `CD4_Th17` versus `IL17A_gdT` from aggregate percentages alone; inspect cell-level receptor/branch coexpression and use paired TCR evidence when needed.

For B development:

- Require RAG/pre-B-receptor evidence for Pro_B or Pre_B; immunoglobulin expression alone is insufficient.
- Distinguish Immature_B from Pre_B by surface-IgM maturation with reduced active recombination.
- At the Pre_B-to-Immature_B boundary, compare recombination genes to their dataset maxima. Low residual `RAG1/RAG2/VPREB1/IGLL1` does not by itself retain Pre_B when `IGHM/CD24/CD38/TCL1A/VPREB3`, B-lineage retention, and an immature-supportive marker such as `ROR1/FCRL1` form a coherent program. Dataset-dominant multi-gene recombination still blocks Immature_B.
- Distinguish Transitional_B from Naive_B using a coherent CD24/CD38 or mouse CD24A/CD93 plus IGHM-to-IGHD transition program; one shared mature-B marker is insufficient.
- Treat Mature_B and Antibody_secreting_B as structural parents, not competing leaf labels.
- For mouse, recognize `VPREB1A`, `CD24A`, and `FCER2A` as valid species-specific symbols.
