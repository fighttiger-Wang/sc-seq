# Expert review, retrieval and reproducibility

> 本文件由 SKILL.md 原文逐行下沉（verbatim）；文中 `references/...` 链接均相对 skill 根目录（SKILL.md 所在目录）。

## Expert review and case-driven optimization

Formal annotation is not complete when executable gates pass. Apply
[expert-review-and-optimization.md](expert-review-and-optimization.md)
to every cluster before formal workbook construction. Record the independent
review status, evidence basis, identity boundary, and a concrete case-specific
optimization recommendation. A missing review record blocks delivery. The
final response must summarize the expert review outcome and the highest-value
recommendations, including when no additional optimization is currently needed.

## Retrieval and reproducibility

This skill has an independent calibration counter. Its first five uses after
this skill/core/dictionary revision must verify involved types against current
literature and curated atlases. From use six onward retrieve only for
marker/context/UMAP conflicts or knowledge-base gaps. Record source, retrieval
date, species, tissue, supported program, exclusions, and adoption/rejection
rationale in a reusable evidence sheet.

Run preparation once without research evidence. If it emits
`status=research_required`, immediately use available online retrieval tools to
resolve every request; this is a required task action, not an optional report
note. Write a structured `research_evidence.json` bound to the emitted
`request_sha256`, then rerun preparation with `--research-evidence`. A DOI list,
article titles copied from memory, or a hand-authored `research_status=resolved`
is invalid. Formal workbook construction remains blocked until the research
artifact passes source independence, current-case multi-gene support, exclusion,
and hash checks. If UMAP review later exposes a new unexplained island or
identity conflict, rerun preparation with `--force-research` and a concrete
`--research-reason`; do not reuse an earlier request hash.
