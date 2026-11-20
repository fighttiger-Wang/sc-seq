# Blind test protocol

> 本文件由 SKILL.md 原文逐行下沉（verbatim）；文中 `references/...` 链接均相对 skill 根目录（SKILL.md 所在目录）。

For a blind test, invoke the preparation entry point with `--blind-test`.
Do not pass a prior annotation workbook, old records, old UMAP audit,
cluster-specific exclusions, or marker exclusions. The only label-bearing
artifact allowed in the blind run is the ontology's candidate-program
vocabulary. The model-facing digest redacts the qualitative core's
`stable_id`, `suggested_identity`, `primary_program`, major label, derived
rationale, and recommended action. Treat those fields in the internal evidence
pack as audit bindings, never as the annotation answer. First write an
independent provisional label from the current-case multi-gene programs and
the candidate audits; then perform a separate all-cluster UMAP review. UMAP
review must be read from the supplied image and must not be generated from the
core decision or from the provisional label. Final workbook construction is
allowed only after the independent records, UMAP audit, and internal evidence
binding all pass validation.
