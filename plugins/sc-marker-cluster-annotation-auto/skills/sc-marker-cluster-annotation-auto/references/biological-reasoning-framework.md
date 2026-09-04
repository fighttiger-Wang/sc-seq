# Biological reasoning framework for difficult annotation boundaries

Use this framework whenever marker evidence is weak, noisy, shared, contradictory, or topology-discordant. It is a decision order, not an invitation to intuit a label.

## 1. Evidence hierarchy

Evaluate evidence in this order:

1. Identity-defining structures and lineage machinery: receptor chains, recombination machinery, structural proteins, lineage-restricted transcriptional machinery, or equivalent hard biological invariants.
2. Branch discriminators and explicit exclusions: compare mutually exclusive sibling programs directly.
3. Differentiation programs: naive, memory, effector, developmental, secretory, or maturation programs.
4. State/QC programs: cycling, stress, interferon, activation, exhaustion, dissociation, ambient RNA, and technical quality.
5. Topology and reference context: UMAP neighborhoods, trajectories, sample distribution, and reference mapping support or challenge a call but do not create identity by themselves.

A lower tier cannot override a coherent higher-tier competing program. Shared cytotoxic, activation, or housekeeping genes cannot determine lineage when receptor/structural evidence points elsewhere.

## 2. Four separate quantitative questions

Never collapse these into one score:

- Detection prevalence: what fraction of cells in the cluster detects each program? This is the main aggregate measure of which identity program is dominant.
- Differential enrichment: is the program enriched against other clusters, with effect size, pct.1/pct.2, and adjusted significance considered together?
- Expression magnitude: how much transcript is present among the cluster average? A rare high-expression subpopulation can raise this without representing the majority.
- Dataset-relative specificity: is the signal exceptional in this dataset or merely background shared across many clusters?

An identity call requires coherent multi-gene support across the relevant questions. A single high log-fold-change gene or a single high average-expression gene cannot outweigh broader prevalence of the competing program.

## 3. Mutually exclusive program arbitration

Before scoring leaves, define each high-risk boundary as two or more versioned sibling programs with positive anchors, biological exclusions, dominance thresholds, citations, and regression cases.

Passing an absolute, branch, exclusion, or boundary gate makes a candidate
eligible; it does not make that candidate the winner. Final identity selection
must occur in a separate competing-program arbitration stage.

For each side:

1. Confirm multi-gene coherence above conservative detection floors.
2. Compare dataset-relative program completeness before raw prevalence. Means
   from different gene panels are not automatically commensurate.
3. Require both a relative dominance ratio and an absolute prevalence margin before declaring one branch dominant.
4. If one program dominates, block leaves from the rival branch even if individual rival genes are enriched.
5. If both programs are coherent and neither dominates, retain a boundary conflict unless a registered boundary-defined identity explicitly requires the joint program. In that case, assign that terminal identity with an explicit evidence gap and blocked merging; do not claim purity or doublets from aggregate data.
6. If neither program is coherent, stop at the nearest defensible parent and trigger targeted resolution.

The first implemented invariants are alpha-beta versus gamma-delta TCR and TCR-defined T versus NK identity. The same pattern must be used for other recurrent boundaries, including epithelial versus immune contamination, neutrophil versus monocyte, and lineage identity versus state programs.

## 4. Evidence upgrade ladder

Escalate only as far as the boundary requires:

1. Cluster-level prevalence plus marker differential evidence.
2. Cell-level coexpression and within-cluster distribution.
3. Resolving reclustering or reference mapping when programs occupy separable subpopulations.
4. Boundary-specific orthogonal evidence: paired scTCR-seq for TCR identity, protein/ADT for surface-defined branches, CNV/genotype for malignancy, spatial neighborhood only for spatial claims.

Cluster aggregates cannot prove that two programs occur in the same cells. A rare dual-receptor population is a testable exception requiring cell-level/paired receptor evidence, not a reason to ignore the conventional competing-branch rule.

## 5. Literature discipline

Before adding or changing a high-risk boundary, use at minimum:

- one consensus nomenclature, ontology, or authoritative review defining the identity;
- one primary study relevant to the tissue/species when available;
- one method source defining what the assay can and cannot resolve.

Literature defines biological plausibility and the invariant; current-sample evidence determines the annotation. A paper cannot resolve sample-specific coexpression, mixture, or topology. Store citations with the versioned rule and register a positive case, a true-rival case, and an ambiguous case before release.

## 6. T-cell receptor example

- Alpha-beta program: `TRAC/TRBC1/TRBC2`, interpreted with CD4 or CD8 branch anchors.
- Gamma-delta program: `TRDC/TRGC1/TRGC2`.
- A gamma-delta label requires its own coherent program and must lose when the alpha-beta program exceeds the configured dominance ratio and absolute margin.
- A CD4/CD8 alpha-beta label is likewise blocked when the gamma-delta program dominates.
- When both programs are close, retain a T-cell boundary review and request cell-level coexpression or paired scTCR evidence.
- Naive/memory/cytotoxic programs are evaluated only after receptor branch arbitration.

For any cluster where alpha-beta and gamma-delta receptor signals are both detected, compare the complete receptor programs before assigning a leaf. A dominant alpha-beta program blocks gamma-delta descendants; a dominant gamma-delta program blocks conventional CD4/CD8 descendants. If the receptor programs are incomplete or near-balanced, retain the nearest supported identity and explicitly request cell-level or paired-receptor validation. A topology-separated island may strengthen a compatible unconventional-T interpretation, but it cannot rescue a missing identity program by itself.

## 7. Release gate

A new biological boundary rule is releasable only when:

- the invariant and exclusions are written explicitly;
- the decision trace records both competing program profiles and the resolution;
- dominant-left, dominant-right, and unresolved-dual regression cases pass;
- historical registered regressions remain green;
- skill documentation and output schema expose the new audit fields;
- the shared core is synchronized to every consuming annotation skill.
