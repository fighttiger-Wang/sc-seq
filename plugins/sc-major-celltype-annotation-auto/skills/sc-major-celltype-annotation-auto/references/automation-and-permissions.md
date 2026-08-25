# Automation, paths, permissions, and recovery

Read this reference before paired-table or Seurat execution.

## E-drive policy

- Confirm the working directory and workspace root are on `E:` before writing.
- Read task inputs from `E:` only. For a C-drive input, stop and request an E-drive copy or explicit authorization.
- Keep intermediates, normalized tables, logs, manifests, caches, previews, and tests in `outputs/<unique-run-name>/`.
- Copy only the QA-passed final `.xlsx` to the uniquely inferred original E-drive input directory.
- Invocation supplies final-delivery intent. If the destination is outside the sandbox, request scoped filesystem permission directly; do not ask the user to repeat or reconfirm the path.
- Treat runtimes as read-only dependencies. Never create junctions, symlinks, or reparse points in the workspace/output tree.

## Approved E-drive runtime

- Resolve a real Python executable before invoking any bundled script.
- Prefer the bundled Codex Python discovered from `CODEX_HOME` or the current user's Codex runtime cache when it exists; verify it with `Test-Path` and a short `sys.executable` check.
- Treat a `WindowsApps` Python entry as a possible alias, not as a usable runtime. Do not install or download a replacement during the workflow.
- Keep the resolved executable in a task-local variable and use it consistently for preflight, workbook building, QA, and delivery.

## Scoped project-context discovery

- Before metadata inference, inspect the common input directory and at most two E-drive parent levels for directly relevant study-background files, sample-group workbooks, annotation maps, and cited papers.
- Do not recursively inventory unrelated trees.
- Record context-source paths and distinguish tissue from experimental-system words such as organoid or cell line.
- Run the annotation-level gate before preflight; a known-lineage subtype task routes to the subcluster skill.

## Question budget

- Default to zero questions.
- Infer species and tissue from explicit text, scoped project context, nearest/deepest path tokens, then data evidence. Generic experimental-system tokens are not tissue names.
- Infer `All_cells/mixed` for table-wide inputs.
- Resolve conventional Seurat cluster columns with the hierarchy in `SKILL.md`.
- Infer delivery from the common original input directory.
- Ask at most one consolidated question only when a material ambiguity remains or the action would be unsafe.

## Encoding and table handling

- Write JSON, Markdown, YAML, TSV, and scripts as UTF-8 without BOM unless required.
- Read text with UTF-8 explicitly.
- Accept average-expression `.xlsx`, `.tsv`, and `.csv`; normalize delimited text inside `prepare_annotation_auto.py` and continue in the same command.
- Use `scripts/run_seurat_extraction.py` for Chinese E-drive paths and UTF-8-safe R execution.

## One-command preflight

`scripts/prepare_annotation_auto.py` validates paths and metadata, normalizes text averages when required, invokes deterministic preflight, and creates:

- `annotation_evidence_digest.json`
- `annotation_evidence_pack.json`
- `annotation_records.template.json`
- `annotation_run_manifest.json`

It accepts optional `--ratios`, `--gene-map`, `--cell-evidence`, and `--evidence-config`. For Seurat extraction, pass the generated `avg_expr_result.txt` as `--ratios` so full detection coverage is used.

Require exact cluster agreement before annotation.

## Automatic delivery

- Default the final filename to the original input directory name plus 大类注释结果.xlsx; for example, 大鼠-小肠大类注释结果.xlsx.
- Call scripts/copy_final_workbook.py without --destination when the common original directory is unique. Use --output-name only for an explicit user-confirmed filename.

- Default paired inputs to their common original directory; default Seurat to the object directory.
- Do not ask when one unique E-drive directory is inferable.
- Never overwrite. If the destination exists, use `<stem>_2.xlsx`, then `_3`, and so on.
- Require SHA-256 equality after copying and report exactly one copied workbook.

## Recovery

- Use the OOXML fallback if openpyxl sees an empty or malformed average-expression workbook.
- Normalize accepted gene headers in memory; never rewrite a source solely for A1.
- Stop on cluster-set mismatch.
- Create a new run directory instead of overwriting analysis outputs.
- Require deterministic structural QA for every build. Render only when custom styling or a structural anomaly requires it; otherwise record the compact standardized layout in QA.
- If an essential command is sandbox-blocked, request the minimum scoped approval and remain on E:.
- Repair reproducible script defects in the maintained plugin source, never in cache or an analysis run.
