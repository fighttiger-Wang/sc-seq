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

`Immature_neutrophil` specifically requires an early or secondary granule program. “Incomplete mature receptors” is not positive evidence of immaturity.

## DC versus monocyte

`HLA-DRA`, `CD74`, and other MHC-II genes establish antigen presentation, not DC identity. Require a DC-specific program:

- cDC1: at least two coherent anchors among `CLEC9A`, `XCR1`, `WDFY4`, `CADM1`, with monocyte exclusions checked.
- cDC2: coherent `CD1C/CLEC10A/FCER1A` support, with `FCN1/CD14/VCAN/S100A8` competition explicitly assessed.
- migratory DC: coherent `CCR7/FSCN1/LAMP3` maturation program.

## DC3 boundary

A cluster-level combination of:

- APC program: `HLA-DRA/HLA-DPA1/HLA-DPB1/CD74`;
- DC-specific program: at least two of `CD1C/CLEC10A/FCER1A`;
- monocyte program: at least three of `CD14/FCN1/VCAN/FCGR3A/LST1`;

is a `DC3` boundary candidate, not proof of DC3. Aggregate ratios cannot determine whether the programs coexist within the same cells or occupy separate cells.

Literature may nominate DC3 and define the expected program, but aggregate evidence cannot prove a homogeneous DC3 population or same-cell coexpression. Without cell-level evidence, prefer a conservative likely-mixed `Myeloid_cell` fallback with `possible_components=cDC2_or_DC3_like;Monocyte`, require manual review, and block automatic merging. This mixed fallback may be formally delivered because it does not overclaim DC3 or doublets.

Cell-level coexpression or resolving reclustering is optional refinement: use it to separate true mixed subpopulations from same-cell boundary biology or doublets. Do not promote DC3 into the shared standard without that validation.

## UMAP use

Topology supports but never substitutes for the program gates. A Myeloid label that conflicts with its nearest UMAP neighborhood remains unresolved until cluster-specific cell, sample, trajectory, reference-mapping, or quantitative-QC evidence explains the conflict. Literature alone cannot resolve sample-specific topology.
