# Annotation logic reconstruction specification

Status: design baseline for the 2026-09-01 reconstruction.

This file is the authoritative continuity snapshot for the redesign of
`sc-major-celltype-annotation-auto` and `sc-marker-cluster-annotation-auto`.
Previous uncommitted rules are historical reference only and must not be
silently merged into this baseline.

## User contract

- Major and subcluster are separate entry points and never mix levels within a
  result table.
- Required inputs: species, tissue/organ, average-expression file, marker
  workbook, detection ratio, and a UMAP PNG with cluster IDs/legend.
- Core deliverable: `cluster -> celltype_label` for plotting, plus evidence,
  UMAP audit, abnormality flags, characteristic genes, and biological rationale.
- Keep the most likely主体细胞类型 for debris, low-quality, background,
  abnormal-state, or suspected doublet clusters; mark the annotation cell red.
- Do not automatically modify or filter the dataset. Report the annotation and
  the suggested handling only.
- Results are Excel workbooks copied to the supplied E-drive input directory;
  filenames use the major/subcluster mode and completion timestamp.

## Evidence model

The input file `gene, group, mean_expr, expr_ratio, norm_expr` is the primary
quantitative source. `expr_ratio` is detection ratio. The marker workbook uses
`Target_Cluster`, `GeneName`, `Target_Cluster_mean`, `Other_Cluster_mean`,
`log2FC`, `pct.1`, and `pct.2`; `pct.1/pct.2` are target/background prevalence.

Evidence is integrated, not summed blindly:

1. global dataset background and ubiquitous programs;
2. current major/parent identity program;
3. subtype or tissue-specialization program;
4. exclusion and competing-lineage programs;
5. mean expression plus prevalence/coverage;
6. UMAP global topology and repeated-label island audit;
7. literature/atlas confirmation when calibration or conflict rules trigger.

`norm_expr` is derived/secondary evidence and must not be double-counted.
Detection ratio supports prevalence, not same-cell coexpression. UMAP supports
global consistency, not a hard identity gate.

## Abnormality interpretation

Identity is separate from interpretation. A cluster may have multiple flags:
`low_quality`, `background_interference`, `abnormal_state`, `debris`,
`suspected_doublet`, or `mixed_population`. `doublet/debris` must list concrete
components. Background requires dataset-relative evidence; a ubiquitous signal
is not an independent competing lineage. Red cells identify any cluster that
should not be plotted as an ordinary pure type.

## Retrieval calibration

Each skill has its own counter. The first five completed uses after this spec
or the shared evidence core changes must perform online literature and atlas
verification for the involved cell types. From use six onward, retrieve only
for marker/context/UMAP conflict, unsupported candidates, or knowledge-base
coverage gaps. Store source title, DOI/PMID or URL, species, tissue, retrieval
date, supported program, exclusions, and adoption/rejection rationale.

## Naming

Use the versioned naming dictionary. Short, established abbreviations are
allowed (`gdT`, `Tn`, migratory DC abbreviation where unambiguous); short common
names such as B cell and T cell remain unshortened. One canonical plotting label
per identity, with aliases and forbidden variants recorded separately.

## Reproducibility

Every run records the skill version, core version, naming-dictionary version,
retrieval-calibration counter, source hashes, cluster order, context, evidence
mode, UMAP audit, and final decision rationale. A knowledge-base or rule update
resets that skill's five-use calibration counter.

## Runtime completion additions

- Accept the standard long-format `avg_expr_result.txt` directly; its
  `expr_ratio` is auto-reused as the full detection-ratio input.
- The production workbook includes a reusable `细胞类型与文献` sheet in
  addition to the result, detailed-evidence, and source sheets.
- Default runtime publication is synchronized to this reconstruction version;
  old published knowledge is not silently selected.
