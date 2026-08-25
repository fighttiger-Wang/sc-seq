# Pseudotime and trajectory interpretation

Use this reference for Monocle, Slingshot, PAGA, DPT, RNA-velocity-informed trajectories, branch analysis, and pseudotime-associated genes.

## Required checks

- Identify the method, cells included, root selection, dimensional representation, topology, branch or terminal-state definition, and group overlay.
- Confirm whether direction came from a user-selected root, biological prior, time course, RNA velocity, or another independent constraint.
- Verify that compared groups occupy the trajectory with adequate cell and sample representation.
- Separate trajectory inference from dynamic-gene testing and from true lineage tracing.

## Interpretation principles

- Pseudotime is an inferred ordering, not chronological time.
- A branch is a modelled state divergence, not proof of irreversible cell fate.
- Group accumulation at later pseudotime may reflect state preference, sampling, survival, or abundance, not faster progression.
- Dynamic genes describe association with the inferred ordering; they do not establish drivers.
- Root choice and topology uncertainty must be visible when they influence the narrative.

## Scientific storyline

Describe:

1. the inferred start and terminal/branch states;
2. which cell identities or groups occupy each region;
3. coordinated gene or pathway changes along the ordering;
4. branch-specific programs when statistically supported;
5. how the trajectory relates to disease, treatment, or differentiation hypotheses;
6. alternative orderings and needed validation.

Use cautious verbs such as `过渡`, `趋向`, `关联`, and `提示`. Reserve `分化为`, `来源于`, or `命运决定` for designs with independent lineage evidence.
