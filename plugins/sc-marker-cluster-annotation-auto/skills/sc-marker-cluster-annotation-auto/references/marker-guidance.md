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
- Require TCR plus an NK-like program for NKT; NKG7/GNLY alone are insufficient.
- In verified full-ratio data, require at least two `CD3D/CD3E/CD3G/TRAC` anchors at >=0.10 for a coherent T program. Low-level TCR background below this gate does not support T or NKT. Strong `NCR1/NKG7/KLRD1/FCER1G/TYROBP` with a failed T gate supports NK contamination.
- Require persistent exhaustion evidence; PDCD1/LAG3 alone do not establish Exhausted/Tex.
- Determine CD4 versus CD8 from branch anchors, not from the shared functional program: require CD4/CD40LG for CD4 descendants and CD8A/CD8B/CD8B1 for CD8 descendants in full-ratio evidence.
- Evaluate CD4, CD8, and gamma-delta anchors against both conservative absolute floors and their dataset-wide maxima. This prevents a low-depth but relatively specific branch program from being erased, while rejecting signals that are weak both absolutely and relative to other clusters.
- Use `Tn` for a coherent naive T program without defensible CD4/CD8 branch assignment. Use `DNT` when T/Tn evidence is coherent, CD4/CD8 anchors are absent by dataset-relative negative checks, and gamma-delta receptor evidence is insufficient.
- Treat exhaustion as an orthogonal state, never as the formal CD4/CD8 identity. Use `CD4_T`, `CD8_T`, or a supported finer identity leaf and add `State=Exhausted`; `CD4_Tex` and `CD8_Tex` are legacy-only migration labels. Treat simultaneous coherent CD4 and CD8 programs as an incompatible-sublineage mixture requiring parent fallback and cell-level review.
- Require at least two `TRDC/TRGC1/TRGC2` anchors at >=0.10 before accepting a gamma-delta descendant. After this branch gate passes, separate `Naive_like_gdT` (`TCF7/LEF1/SELL/CCR7`, supported by `KLF2/IL7R/BCL2/SATB1`) from `IL17A_gdT` (`IL17A/IL23R/RORC/RORA`, with mouse support such as `ZBTB16/SCART1/CCR6/IL17F/IL1R1`). An IL17/type-17 program without gamma-delta anchors cannot establish `IL17A_gdT`.
- Because the generic `gdT` panel can score slightly above a more specific child by containing broader receptor markers, apply the approved descendant projection only when the child is formally coherent, has at least three reviewed core markers, and reaches at least 80% of the `gdT` score. Record `decision_trace.descendant_projection`; otherwise retain `gdT`.
- Distinguish Tfh from Tph using CXCR5/BCL6 versus CXCL13/PDCD1/MAF and explicit exclusions.
- Compare cDC2 against FCN1/S100A8/VCAN monocyte-derived programs.
- Require a complete Myeloid boundary program, not isolated anchors: neutrophil calls need commitment plus mature, early-granule, or activated-neutrophil support; DC3 candidates need APC, DC-specific, and monocyte programs plus cell-level boundary validation.
- Require a contractile plus ECM program for Myofibroblast.
- Require intestinal developmental context for TA_cell; MKI67/TOP2A alone indicate Cycling.
- Require FOXI1/CFTR evidence and rarity review for Pulmonary_ionocyte.
- Require CNV/mutation/tissue evidence for malignant disease role.

Missing genes in positive-marker-only data are unknown, not zero. Cross-lineage coherent conflicts require mixed/doublet review and `auto_merge_allowed=false`.

The approved panel is a validation standard, not a closed candidate list. When a plausible subtype is absent or local candidates are noncoherent, search curated databases and primary literature. Require at least two independent sources and explicit competing-program checks before using `validated_external_candidate`. Literature validates candidate biology but cannot substitute for sample-level or cell-level validation of a boundary-defined identity; promote only after biological validation and multi-case historical regression.

Do not accept a generic CD4/CD8 branch solely because its broader panel out-scores every child. When `branch_identity_no_supported_leaf` appears, re-open the candidate set, review low-ranked markers and negatives, apply configured descendant projection, and search for missing memory/effector or tissue-specialized identities. A researched branch fallback requires two independent sources documenting why no finer identity is defensible and cannot coexist with a normal descendant in the final table.

A declared subcluster parent is a prior, not a hard filter. With full average-expression and detection-ratio evidence, score tissue-relevant off-parent programs. Reassign a dominant coherent contaminant under review; if expected-parent and off-parent programs coexist, return their shared ancestor and block automatic merging.

Within T lineage, alpha-beta and gamma-delta receptor branches are also incompatible sibling programs rather than an ordinary subtype boundary. In verified full-ratio data, a coherent CD4/CD8 program plus at least two detected gamma-delta TCR anchors (`TRDC`, `TRGC1`, `TRGC2`) and a near-scoring gamma-delta candidate must be flagged for mixed-population/reclustering review. For an IL17-producing cluster, do not choose `CD4_Th17` versus `IL17A_gdT` from aggregate percentages alone; inspect cell-level `CD4/CD40LG` against `TRDC/TRGC1/TRGC2` together with `IL17A/RORC/CCR6`. When the gamma-delta anchors are coherent and CD4 alpha-beta anchors are absent, `IL17A_gdT` is the appropriate branch-specific identity, not `CD4_Th17`.

For B development:

- Require RAG/pre-B-receptor evidence for Pro_B or Pre_B; immunoglobulin expression alone is insufficient.
- Distinguish Immature_B from Pre_B by surface-IgM maturation with reduced active recombination.
- At the Pre_B-to-Immature_B boundary, compare recombination genes to their dataset maxima. Low residual `RAG1/RAG2/VPREB1/IGLL1` does not by itself retain Pre_B when `IGHM/CD24/CD38/TCL1A/VPREB3`, B-lineage retention, and an immature-supportive marker such as `ROR1/FCRL1` form a coherent program. Dataset-dominant multi-gene recombination still blocks Immature_B.
- Distinguish Transitional_B from Naive_B using a coherent CD24/CD38 or mouse CD24A/CD93 plus IGHM-to-IGHD transition program; one shared mature-B marker is insufficient.
- Treat Mature_B and Antibody_secreting_B as structural parents, not competing leaf labels.
- For mouse, recognize `VPREB1A`, `CD24A`, and `FCER2A` as valid species-specific symbols.
