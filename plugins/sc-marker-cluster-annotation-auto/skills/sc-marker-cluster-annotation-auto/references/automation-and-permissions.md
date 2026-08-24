# Automation, paths, and failure recovery

Read this reference before running the paired-Excel or Seurat route.

## E-drive policy

- Confirm the current working directory and workspace root are on `E:` before writing.
- Read inputs from `E:` only. If an input is on `C:`, stop and request an E-drive copy or explicit authorization.
- Put outputs, logs, manifests, caches, previews, and tests inside the E-drive workspace, normally `outputs/<unique-run-name>/`.
- Treat loader-provided runtimes as read-only dependencies. Never use their parent directories as work/output locations.
- Never create `node_modules` symlinks, Windows junctions, or other reparse points inside the workspace/output tree. They can break sandbox refresh and file/image inspection even after removal.
- Inspect Seurat metadata with `scripts/inspect_seurat_object.py`, which performs no writes. Never discover cluster columns by deliberately failing an extraction with a fake column name.
- Never copy or patch bundled skill scripts inside an analysis run directory. Deep generated paths and inaccessible temporary subtrees can trigger Windows sandbox refresh/permission failures.

## Encoding and R paths

- Write JSON, Markdown, YAML, TSV, and scripts as UTF-8 without BOM unless a consumer requires BOM.
- In Windows PowerShell, read text with `Get-Content -Encoding UTF8`; the legacy default can consume a quote after a Chinese multibyte sequence and make valid JSON appear malformed.
- Parse generated JSON with Python `encoding="utf-8"` when possible.
- Launch Seurat extraction through `scripts/run_seurat_extraction.py`. It sets `LC_ALL` and `LANG` to `Chinese (Simplified)_China.utf8`, which is required for this Windows R runtime to receive Chinese E-drive paths correctly.

## Source versus cache

- Never edit `plugins/cache/...` as the maintained source. Cache edits disappear on reinstall.
- Update the personal plugin source, validate it, update its cachebuster, then reinstall.
- Keep exactly one active source. Do not add a same-named bare skill.

## Recovery rules

- If `openpyxl` sees an empty/malformed average-expression sheet, use the bundled OOXML fallback read-only and record `average_reader=ooxml_fallback`.
- Accept common average-expression gene-header aliases GeneName, Gene, features, feature, and Cluster; normalize in memory and never rewrite the source solely for A1.
- If cluster columns and marker cluster IDs differ, stop before annotation.
- If an output workbook exists, create a new run directory or require explicit `--force`; never silently overwrite.
- Deterministic structural QA is the standard completion gate; record visual_qa=not_required_deterministic_builder.
- Do not discover or probe renderers during the standard route. Render only for custom styling/content or a structural/layout anomaly.
- If R corrupts a Chinese path, rerun through `run_seurat_extraction.py`; do not copy data to C: or create a junction.
- If an essential command is blocked by sandbox/network policy, request the minimum scoped approval. Do not redirect work to C:.
- If a bundled script has a reproducible defect, stop the run and repair the maintained E-drive plugin source separately; do not create an ad-hoc patched script under `outputs/`.

## One-command preflight

Run `scripts/prepare_annotation.py` with confirmed metadata. It validates paths, determines whether the parent is lineage- or state-based, validates paired files, and creates:

- annotation_evidence_digest.json: model-facing marker/signature/QC summary used first.
- annotation_evidence_pack.json: full audit evidence used only for targeted conflicts, including raw_top_marker, naming_top_marker, and exclusions.
- annotation_records.template.json`: required output fields in cluster order.
- `annotation_run_manifest.json`: metadata, paths, reader route, and policy decisions.

The evidence pack excludes the full 20k-gene expression matrix to reduce context and improve speed/reliability.

When a unique `avg_expr_result.txt`, `expression_ratio.tsv`, or `detection_ratio.tsv` exists beside paired inputs, pass it with `--ratios`. Keep ratio, gene-map, cell-evidence, and custom-config inputs on E:. Never copy those intermediates to the delivery directory. Seurat extraction writes `avg_expr_result.txt` automatically from per-cluster detection in the assay count layer when available.




## Automatic delivery

- Default the final workbook destination to the common parent directory of original paired Excel inputs.
- For Seurat input, default to the original object directory.
- Do not ask when one unique existing E-drive directory is inferable.
- Ask only when paths are lost/unavailable, source parents conflict, or the inferred location is not on E:.
- Sandbox write approval is a permission step, not a reason to request a different destination.
