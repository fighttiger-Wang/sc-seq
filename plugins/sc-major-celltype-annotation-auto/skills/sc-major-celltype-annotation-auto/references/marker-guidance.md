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
- Interpret branch anchors relative to the current dataset when verified full ratios exist. A universally low but dataset-maximal CD4, CD8, or gamma-delta signal may support review-level branch evidence; a weak absolute signal that is also weak relative to other clusters must not pass.
- Require TCR plus an NK-like program for NKT; NKG7/GNLY alone are insufficient.
- Require persistent exhaustion evidence; PDCD1/LAG3 alone do not establish Exhausted/Tex.
- In T-subtype audit evidence, require CD4/CD40LG or CD8A/CD8B/CD8B1 branch anchors before assigning branch-specific leaves; shared state programs cannot determine the CD4/CD8 branch.
- Distinguish Tfh from Tph using CXCR5/BCL6 versus CXCL13/PDCD1/MAF and explicit exclusions.
- Compare cDC2 against FCN1/S100A8/VCAN monocyte-derived programs.
- Require a contractile plus ECM program for Myofibroblast.
- Require intestinal developmental context for TA_cell; MKI67/TOP2A alone indicate Cycling.
- Require FOXI1/CFTR evidence and rarity review for Pulmonary_ionocyte.
- Require CNV/mutation/tissue evidence for malignant disease role.

Missing genes in positive-marker-only data are unknown, not zero. Cross-lineage coherent conflicts require mixed/doublet review and `auto_merge_allowed=false`.

The approved panel is a validation standard, not a closed candidate list. When local candidates are noncoherent or biologically incomplete, search curated databases and primary literature for additional candidates. Require at least two independent sources and explicit competing-program checks before using `validated_external_candidate`; do not add it to the permanent knowledge base until multiple historical cases pass regression.
