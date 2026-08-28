# Deterministic annotation evidence policy

Use the versioned shared evidence core as the scoring authority. The model may interpret biological context but must not alter script scores, thresholds, evidence mode, T/NK provisional calls, risk level, or required review.

## Evidence modes

- `minimal`: average expression plus positive marker table. Use marker `pct.1/pct.2` where available. Missing genes are unknown. Cap confidence below `high`.
- `ratio_enhanced`: verified full gene-by-cluster ratio table. Missing genes in the verified table may be treated as zero. Evaluate low-ranked, negative, and competing-lineage genes.
- `cell_validated`: ratio evidence plus per-cluster cell-level validation JSON. Only this mode may promote cluster-level suspicion to a doublet candidate.

## Annotation-depth projection

- In `subcluster` mode, retain subtype evidence and review coherent same-lineage rivals.
- In a confirmed lineage subcluster run, retain coherent descendants outside their canonical tissue scope as review candidates instead of silently excluding them. Set `tissue_scope_match=false` and force at least `R1_REVIEW_RETAIN`.
- Treat `branch_identity_no_supported_leaf` as a resolution-search trigger, not an immediately publishable endpoint. Before accepting a broad CD4/CD8 branch identity, re-evaluate every approved child, search curated databases and primary literature for missing subtype candidates, and perform explicit competing-program checks. Record at least two independent sources for any researched fallback or knowledge-base-external identity.
- Enforce final table-wide hierarchy consistency. If any normal descendant of a branch is retained, an evidence-limited ancestor from that branch cannot remain in the final mapping. Refine the ancestor through the resolution-search pass; if it still cannot be resolved, stop delivery and request cell-level evidence or reclustering instead of silently lowering annotation depth.
- A confirmed lineage parent is a strong prior, not a hard candidate filter. With verified full-gene average expression and detection ratios, score tissue-relevant off-parent lineage sentinels in parallel. If the parent program is weak and a coherent off-parent program clearly dominates, formally reassign the cluster with `formal_identity_fallback=off_parent_lineage_reassignment`, require manual review, and block automatic merging until subset provenance is verified.
- If coherent expected-parent and off-parent programs coexist, return `stable_id=Multi_cell` with `formal_identity_fallback=multi_cell_annotation`, set `mixed_population=true`, list the concrete identities in `possible_components`, and set `auto_merge_allowed=false`; never return `Cell` or a generic ontology ancestor. Use cell-level coexpression or reclustering to distinguish a mixed cluster from doublets.
- In full-ratio mode, leaf coherence requires the configured number of directionally supported core markers. Raw detection coverage alone is not coherent evidence. In sparse positive-marker-only mode, coverage may remain a conservative fallback because missing genes are unknown.
- For Myeloid boundaries, apply program-level gates before ranking can finalize a leaf. `CSF3R/FCGR3B` without a mature, early-granule, or activated-neutrophil program cannot override a coherent `CD14/FCN1/VCAN/LST1/TYROBP` monocyte program. `Immature_neutrophil` requires positive granule-development evidence, not merely weak mature receptors.
- Treat a narrowly sub-threshold `FCGR3B` signal as a review candidate rather than a negative identity conclusion when `CSF3R` passes, at least two of `PI3/SLPI/CXCL8` pass, and the coherent monocyte program is absent. This borderline rule never auto-finalizes a neutrophil leaf: it triggers structured quantitative-QC/UMAP review and an auditable override if a leaf is retained.
- `CD83` and `ITGAX/CD11c` are activation/APC-like evidence, not DC identity anchors. A DC leaf still requires its complete identity program: `CLEC9A/XCR1/WDFY4/CADM1` for cDC1, `CD1C/CLEC10A/FCER1A` for cDC2, or `CCR7/FSCN1/LAMP3` for migratory DC.
- An APC-high cluster with both `CD1C/CLEC10A/FCER1A` and `CD14/FCN1/VCAN/FCGR3A/LST1` is a DC3 boundary candidate. Cluster-level ratios and literature do not establish same-cell coexpression. Without cell-level validation, return a likely-mixed common-parent fallback, set `mixed_population=true`, `suspected_doublet=false`, require manual review, and block automatic merging; formal delivery is allowed because the result does not overclaim DC3. Cell-level validation remains necessary only for a DC3 call or for distinguishing mixture from doublets.
- Apply configured absolute-negative gates before accepting a leaf. This protects within-lineage identity boundaries where exclusion genes may be common across the dataset and therefore fail a relative-specificity test, such as retained `MS4A1/PAX5` against terminal plasma differentiation.
- Off-parent candidates require a coherent set of directionally supported anchors. Shared `EPCAM` or a single keratin plus weak background coverage cannot establish epithelial mixture risk.
- In `major` mode, project evidence panels into the major vocabulary before computing the rival margin. Do not create a review solely because two supported subtype panels map to the same major label.
- Keep the underlying panel identity, projected major identity, runner-up, competing major lineage, and decision trace together in the audit output.
- Determine provisional T/NK status from coherent CD3/TCR evidence and an NK program containing an NK-specific anchor. Select the final table-wide T/NK vocabulary only after every cluster has a provisional status.
- Require at least two `CD3D/CD3E/CD3G/TRAC` anchors at detection ratio >=0.10 for a coherent T program in full-ratio mode. Low-level aggregate TCR contamination below this program gate cannot support T or NKT. NKT additionally requires an NK-specific program; strong `NCR1/NKG7/KLRD1/FCER1G/TYROBP` with weak CD3/TCR supports NK contamination instead.
- In full-ratio T-subcluster runs, require CD4/CD40LG evidence for CD4 descendants and CD8A/CD8B/CD8B1 evidence for CD8 descendants. Combine conservative absolute floors with each gene's dataset-wide maximum. Exhaustion, naive, memory, or cytotoxic programs do not determine the CD4/CD8 branch by themselves.
- A coherent naive T program may resolve to generic `Tn` when CD4/CD8 branch evidence is absent or conflicting. A dataset-relative double-negative phenotype may resolve `Tn` to `DNT` only when coherent T evidence is retained and gamma-delta evidence is not sufficient.
- If coherent CD4 and CD8 alpha-beta programs coexist, return `Multi_cell`, retain both identities in `possible_components`, set mixed/suspected-doublet review, and block automatic merging until cell-level coexpression or reclustering resolves the components.

## Scoring and risk

Combine fixed conservative floors with per-gene median/MAD specificity. Compute core-marker coverage, positive differential support, explicit negative conflicts, rival evidence, score margin, and state programs separately from identity.

Exhaustion is a state-only program. Do not emit deprecated `CD4_Tex` or `CD8_Tex` identity/state boundary nodes. Resolve `CD4_T`, `CD8_T`, or a supported finer identity and keep the display label equal to the identity; state remains separate. Semantic duplicates such as `Exhausted_CD4_Tex` are invalid and must fail QA.

- `R0_ACCEPT`: coherent primary identity, sufficient margin, no coherent competing program.
- `R1_REVIEW_RETAIN`: incomplete evidence, insufficient margin, or state/QC dominance. Retain provisionally and review plots.
- `R2_RECLUSTER_OR_DOUBLET_REVIEW`: coherent incompatible programs in cluster-level evidence. Inspect single-cell coexpression; recluster if programs occupy separate cells.
- `R2_IDENTITY_BOUNDARY_REVIEW`: coherent programs define a known identity boundary, but aggregate evidence cannot determine whether the signature is intrinsic or a mixed cluster. Do not imply confirmed doublets; require boundary-specific cell-level validation or reclustering.
- `R3_DOUBLET_CANDIDATE`: supplied cell-level evidence reports a high doublet call/fraction. Review per-sample calls before removal.

Every non-R0 result requires `manual_review=true`. Never call ambient RNA, mixed clusters, or doublets confirmed from cluster-level averages or ratios.

Treat mutually exclusive T-cell receptor branches as a mixed-population risk even though they share the same broad T lineage. In full detection-ratio mode, coherent CD4/CD8 alpha-beta identity together with at least two gamma-delta TCR anchors (`TRDC/TRGC1/TRGC2`) and a near-scoring `gdT` candidate requires `R2_RECLUSTER_OR_DOUBLET_REVIEW`, `stable_id=Multi_cell`, `mixed_population=true`, and `auto_merge_allowed=false`. Retain both leaf candidates in `possible_components`. Cluster-level proportions flag this risk but do not establish whether the programs occur in separate cells or doublets.

`Cell` is never an allowed final label in major or subcluster mode. A genuinely mixed/multiplet cluster uses `Multi_cell`; a noncoherent cluster without mixed evidence must enter targeted resolution research and block formal delivery if no defensible identity can be established.

Reject final subcluster tables that mix an ontology ancestor with one of its descendants. The only audit-only exceptions are blocked mixed-parent fallbacks with `mixed_population=true` and `auto_merge_allowed=false`; an evidence-limited CD4/CD8 branch is not an exception. Keep developmental stage separate from identity, and keep Cycling as state even when the display label is `Cycling_<Identity>`.

## Cell-level validation and provenance

Accept a JSON object keyed by cluster with fields such as `doublet_call`, `doublet_fraction`, `method`, and `per_sample`. Run doublet detection per sample from raw counts and chemistry/loading-specific expectations. Prefer scDblFinder or Scrublet; use SoupX with empty droplets and DecontX with cluster-aware cell matrices. Record method, version, input scope, and provenance.

Use Cell Ontology for hierarchy and Ensembl Compara for ortholog mappings. Cache retrieved resources on E: and record URL, retrieval date, version, and SHA-256. Do not let unvalidated web text directly modify the deterministic config.

Open online retrieval whenever local evidence is insufficient for a leaf, a plausible subtype is absent from the approved knowledge base, cross-species support is incomplete, or a broad ancestor would otherwise coexist with a descendant. A knowledge-base-external identity requires at least two independent sources, `validated_external_candidate`, manual review, and confidence below high. Literature establishes biological plausibility, not sample-specific coexpression or topology. Boundary-defined external identities additionally require current-case cell/sample evidence. A broad researched fallback requires `researched_branch_fallback`, the same two-source audit, and table-wide hierarchy consistency. Promote external identities only after biological validation plus historical multi-case regression.

Methodological references include Heumos et al. 2023 (`10.1038/s41576-023-00586-w`), Ianevski et al. 2022 (`10.1038/s41467-022-28803-w`), Zhang et al. 2019 (`10.1038/s41592-019-0529-1`), Xi and Li 2021 (`10.1016/j.cels.2020.11.008`), Germain et al. 2021 (`10.12688/f1000research.73600.2`), Young and Behjati 2020 (`10.1093/gigascience/giaa151`), and Yang et al. 2020 (`10.1186/s13059-020-1950-6`).
