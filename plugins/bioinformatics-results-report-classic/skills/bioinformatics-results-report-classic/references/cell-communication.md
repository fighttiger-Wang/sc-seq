# Cell communication interpretation

Use this reference for CellChat, NicheNet, MultiNicheNet, CellPhoneDB, ligand-receptor, pathway communication, and sender-receiver results.

## Required checks

- Identify the method, database, species mapping, group comparison, sender and receiver definitions, and metric semantics.
- Confirm whether group comparisons used matched cell types and whether minimum-cell filters were applied.
- Check whether abundance differences could inflate the number or aggregate strength of inferred interactions.
- Distinguish expression-based ligand-receptor compatibility from spatial contact and functional signaling.

## Interpretation unit

Build each main claim as:

`sender cell → ligand/receptor or signaling pathway → receiver cell → plausible response`

Tie the claim to the supplied communication metric and, when available, ligand expression, receptor expression, target-gene evidence, or pathway contribution. Prioritize interactions that recur across complementary outputs rather than the largest network graphic alone.

## Boundaries

- These methods infer communication potential; they do not directly observe molecular binding, secretion, spatial proximity, or causality.
- More predicted edges can reflect more cells, broader expression, database coverage, or threshold choices.
- A pathway-level label may aggregate several ligand-receptor pairs with different biological meanings.
- NicheNet target support strengthens a ligand hypothesis but still does not prove the sender caused the receiver program.

## Reporting shape

Start with global network remodeling only if the metric is comparable between groups. Then present a few biologically coherent sender-receiver axes, alternative explanations, and validation options such as spatial colocalization, protein assays, perturbation, or receptor blockade.
