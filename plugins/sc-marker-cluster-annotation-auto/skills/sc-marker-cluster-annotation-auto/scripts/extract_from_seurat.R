#!/usr/bin/env Rscript

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
script_path <- if (length(script_arg) == 1) sub("^--file=", "", script_arg) else "extract_from_seurat.R"
script_dir <- dirname(normalizePath(script_path))
source(file.path(script_dir, "extract_from_seurat_core.R"), chdir = TRUE)

python_candidates <- unique(Filter(nzchar, c(Sys.getenv("CODEX_PYTHON", unset = ""), Sys.which("python"), Sys.which("python3"))))
python_candidates <- python_candidates[file.exists(python_candidates)]
if (length(python_candidates) == 0) {
  stop("TSV extraction succeeded, but no Python runtime was found. Pass the loader-provided runtime through CODEX_PYTHON and rerun.")
}
converter <- file.path(script_dir, "tsv_to_annotation_xlsx.py")
status <- system2(python_candidates[[1]], args = c(shQuote(converter), "--avg-tsv", shQuote(avg_tsv), "--markers-tsv", shQuote(marker_tsv), "--output-dir", shQuote(output_dir)))
if (!identical(status, 0L)) stop("Python XLSX conversion failed with status: ", status)
