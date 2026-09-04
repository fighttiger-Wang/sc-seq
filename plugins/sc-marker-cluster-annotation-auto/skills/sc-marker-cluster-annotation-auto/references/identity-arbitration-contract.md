# Subcluster identity arbitration contract

Use this contract when two or more sibling identity programs can pass their
individual marker gates. A gate establishes eligibility; it never grants an
automatic final-label priority.

The decision order is fixed:

1. generate same-level candidates;
2. evaluate each candidate's identity eligibility;
3. compare the complete competing identity programs;
4. resolve left-dominant, right-dominant, registered-boundary, or unresolved;
5. evaluate development and state without changing identity;
6. audit UMAP consistency without creating an identity;
7. bind the final label only to an eligible candidate.

The machine-readable policy is
[`identity-arbitration-policy.v1.json`](identity-arbitration-policy.v1.json).
Each rule declares two program profiles, their eligible same-level labels,
dominance requirements, and an optional registered boundary identity. The
engine is label-agnostic and reusable for arbitrary candidate pairs.

Absolute-program, boundary, branch, and exclusion gates belong to the
eligibility stage. Compare dataset-relative program completeness before raw
prevalence: raw means from different gene panels are not inherently
commensurate. If one relative identity program is complete and the other is
partial, the complete side dominates. If both are complete, retain a joint
boundary as unresolved unless the rule defines a biologically valid boundary
identity. Only when relative completeness does not distinguish the sides may
prevalence use both a relative difference and an absolute margin.

Rules may bind a dominant side to its own eligible sibling or, for an
asymmetric transition identity, to a registered boundary identity while the
opposite program remains coherent. This behavior must be declared in policy;
the engine never infers it from a label name.

Cycling, interferon response, stress, antigen presentation, activation, and
other state programs never select a side. UMAP may reject or retain a
provisional identity only through an already-supported candidate-program
audit; it cannot rescue a candidate whose identity program is missing.
