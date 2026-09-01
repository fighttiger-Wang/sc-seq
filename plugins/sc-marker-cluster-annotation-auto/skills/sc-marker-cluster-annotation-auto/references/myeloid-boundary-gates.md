# Myeloid identity-boundary gates

Read this reference for Myeloid subcluster annotation when neutrophil, monocyte, macrophage, cDC2, or DC3 programs compete.

## Neutrophil versus monocyte

Do not call a neutrophil or an immature-neutrophil subtype from `CSF3R` or `FCGR3B` alone. In full-ratio mode require:

1. neutrophil commitment (`CSF3R` plus `FCGR3B`); and
2. at least one coherent downstream program:
   - mature receptors/granules: `FCGR3B`, `CXCR2`, `PGLYRP1`, `LTF`, `CAMP`, `CD177`;
   - early granules: `MPO`, `ELANE`, `PRTN3`, `AZU1`, `DEFA1/3/4`, `MS4A3`, `CEBPE`;
   - activated inflammatory neutrophil: retained `FCGR3B` plus at least two of `PI3`, `SLPI`, `CXCL8`.

A coherent `CD14/FCN1/VCAN/LST1/TYROBP` program with no downstream neutrophil program blocks a neutrophil call even when `CSF3R` is high. Reclassify provisionally to the best-supported monocyte node, require cell-level review, and set `auto_merge_allowed=false`.

When `CSF3R` passes, `FCGR3B` is narrowly below its conservative floor but remains at least 75% of that floor, at least two of `PI3/SLPI/CXCL8` pass, and the coherent monocyte program is absent, retain Neutrophil only as an `R1_REVIEW_RETAIN` borderline candidate. Require targeted quantitative-QC/UMAP review, manual review, and `auto_merge_allowed=false`; do not force a monocyte leaf merely because one commitment marker missed a hard cutoff by a narrow margin.

`Immature_neutrophil` specifically requires an early or secondary granule program. “Incomplete mature receptors” is not positive evidence of immaturity.

## DC versus monocyte

`HLA-DRA`, `CD74`, and other MHC-II genes establish antigen presentation, not DC identity. Require a DC-specific program:

`CD83`, `ITGAX/CD11c`, and `RELB` indicate APC/DC-like activation and may populate `state_list=DC_like`; they are not DC identity anchors by themselves.

- cDC1: at least two coherent anchors among `CLEC9A`, `XCR1`, `WDFY4`, `CADM1`, with monocyte exclusions checked.
- cDC2: coherent `CD1C/CLEC10A/FCER1A` support, with `FCN1/CD14/VCAN/S100A8` competition explicitly assessed.
- migratory DC: coherent `CCR7/FSCN1/LAMP3` maturation program.

## DC3 boundary

A cluster-level combination of:

- APC program: `HLA-DRA/HLA-DPA1/HLA-DPB1/CD74`;
- DC-specific program: at least two of `CD1C/CLEC10A/FCER1A`;
- monocyte-specific program: at least three of `CD14/FCN1/VCAN/FCGR3A`, or two anchors whose complete-program mean is sufficiently high and competitive with the cDC2 program;

is a `DC3` boundary candidate. This registered combination supports `DC3` as the best-fit terminal identity, while aggregate ratios still cannot determine whether the cluster is pure or whether all programs coexist within the same cells.

`LST1` and `TYROBP` are pan-myeloid support and must not be counted as independent monocyte-specific anchors. When all three cDC2 anchors pass, the cDC2 program mean is at least 1.5-fold higher with an absolute margin of at least 0.20, and no more than two monocyte-specific anchors pass, retain `cDC2` as `R1_REVIEW_RETAIN`, require manual review, and block automatic merging without labeling the cluster `Multi_cell`.

When all three programs pass, use `stable_id=DC3`, `formal_identity_fallback=dc3_boundary_best_fit`, `mixed_population=false`, `suspected_doublet=false`, require manual review, and block automatic merging. Do not escape to `Myeloid_cell` or label `Multi_cell` merely because DC3 combines dendritic and monocyte-like features.

Cell-level coexpression or resolving reclustering is optional refinement: use it to test cluster purity, separate true mixed subpopulations from intrinsic DC3 boundary biology, and assess doublets. If cell-level evidence demonstrates distinct component populations, replace the aggregate DC3 judgment with the appropriate `Multi_cell` or resolved reclustered identities.

## UMAP use

Topology supports but never substitutes for the program gates. A Myeloid label that conflicts with its nearest UMAP neighborhood remains unresolved until cluster-specific cell, sample, trajectory, reference-mapping, or quantitative-QC evidence explains the conflict. Literature alone cannot resolve sample-specific topology.
