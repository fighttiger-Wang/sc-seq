# Open-world research workflow

Use this workflow when preparation creates `research_requests.json` or when a
later all-cluster UMAP review exposes a new conflict.

## Trigger policy

The executable research stage is required for any of these conditions:

- the current skill/core/knowledge revision is still within its first five
  calibration uses;
- no registered candidate has a complete identity program;
- the selected fallback is outside the current organ/tissue prior;
- no candidate is eligible for automatic binding under the parent and tissue
  soft priors;
- complete competing programs remain unresolved;
- a coherent off-parent program is present;
- an expert explicitly escalates a biological concern;
- UMAP review identifies an unexplained disconnected same-label island or a
  marker/topology identity conflict.

Organ and tissue fields are soft priors. Nonmatching candidates remain visible
for audit and research, but are not automatically bound. Disease and
developmental context must be evaluated separately from organ scope.

## Two-pass execution

1. Run `prepare_annotation.py` normally. Never supply a prior label artifact in
   blind mode.
2. When the command reports `research_required`, read
   `research_requests.json`. Search online by species, tissue/organ,
   disease/development context, coherent current-case genes, sibling identities,
   and explicit exclusions.
3. Create `research_evidence.json` using the exact request hash and the schema
   below. Include adopted and rejected alternatives where relevant.
4. Rerun the same preparation command with `--research-evidence`. Any changed
   input or trigger creates a different hash and invalidates stale research.
5. Build records and the UMAP audit only from the resolved evidence pack.
6. Formal workbook QA verifies the research artifact hash and updates the
   calibration counter only after the workbook passes.

If UMAP creates a new research need after step 4, rerun preparation with
`--force-research --research-reason '<concrete concern>'`, conduct the additional
retrieval, and bind the new request hash.

## Research evidence schema

```json
{
  "schema_version": "1.0.0",
  "request_sha256": "exact value from research_requests.json",
  "resolutions": {
    "0": {
      "status": "resolved",
      "query": "mouse aorta multi-gene program sibling exclusion",
      "retrieval_date": "YYYY-MM-DD",
      "candidate_label": "Canonical_or_new_ASCII_label",
      "label_basis": "researched_registered_candidate",
      "current_case_support_markers": ["GENE1", "GENE2"],
      "exclusions": ["competing identity exclusion"],
      "adoption_or_rejection_rationale": "Why this candidate is admitted and alternatives are rejected.",
      "sources": [
        {
          "title": "Source title",
          "doi_or_pmid_or_url": "DOI:... or PMID:...",
          "retrieval_date": "YYYY-MM-DD",
          "species": "Mouse",
          "tissue": "Aorta",
          "supported_program": "coherent multi-gene identity program",
          "exclusions": "what this source does not establish",
          "adoption_or_rejection_reason": "how it is used in this case"
        },
        {
          "title": "Independent source title",
          "doi_or_pmid_or_url": "PMID:...",
          "retrieval_date": "YYYY-MM-DD",
          "species": "Mouse or cross-species atlas",
          "tissue": "Aorta or justified comparator",
          "supported_program": "program support",
          "exclusions": "confounders",
          "adoption_or_rejection_reason": "case-specific use"
        }
      ]
    }
  }
}
```

For repeated use across many clusters, sources may instead be stored once in a
top-level `source_library` object and referenced by each resolution through a
`source_ids` array. The validator expands and checks the same required fields;
missing library entries are invalid.

Use `label_basis=researched_registered_candidate` when the selected identity is
already among the emitted ontology candidates. Use
`label_basis=validated_external_candidate` when research introduces a new
identity. External candidates still require at least two current-case markers
present in the evidence, two independent sources, and explicit sibling
exclusions. Literature or UMAP alone cannot create the label.

## Formal blocking rules

Formal delivery fails when any required cluster has one of these defects:

- missing or stale `request_sha256`;
- fewer than two independent source identifiers;
- missing query, retrieval date, supported program, or adoption/rejection
  rationale;
- fewer than two supporting genes present in the current case;
- an external label presented as a registered candidate, or vice versa;
- record identity or `label_basis` differing from the admitted research result;
- UMAP `research_status` or `research_artifact_sha256` differing from the
  evidence pack;
- research remains pending or only a DOI list was supplied.
