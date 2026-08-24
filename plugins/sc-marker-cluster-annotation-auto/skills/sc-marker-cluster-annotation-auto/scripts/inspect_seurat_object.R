#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
parse_args <- function(x) {
  out <- list(); i <- 1
  while (i <= length(x)) {
    if (!startsWith(x[[i]], "--") || i == length(x)) stop("Invalid arguments near: ", x[[i]])
    out[[sub("^--", "", x[[i]])]] <- x[[i + 1]]; i <- i + 2
  }
  out
}
`%||%` <- function(x, y) if (is.null(x) || length(x) == 0 || is.na(x) || identical(x, "")) y else x

opt <- parse_args(args)
if (!"input" %in% names(opt)) stop("Missing required argument: input")
input <- normalizePath(opt$input, mustWork = TRUE)
if (.Platform$OS.type == "windows" && toupper(substr(input, 1, 2)) != "E:") stop("Input must be on E:")
preferred <- opt[["object-name"]] %||% ""

ext <- tolower(tools::file_ext(input))
if (ext == "rds") {
  obj <- readRDS(input); object_name <- basename(input)
} else if (ext == "qs") {
  if (!requireNamespace("qs", quietly = TRUE)) stop("R package 'qs' is required for .qs input")
  obj <- qs::qread(input); object_name <- basename(input)
} else {
  env <- new.env(parent = emptyenv())
  loaded <- load(input, envir = env)
  candidates <- loaded[vapply(loaded, function(nm) inherits(env[[nm]], "Seurat"), logical(1))]
  if (preferred != "") {
    if (!preferred %in% candidates) stop("Selected Seurat object not found: ", preferred)
    candidates <- preferred
  }
  if (length(candidates) == 0) stop("No Seurat object found. Loaded names: ", paste(loaded, collapse = ", "))
  if (length(candidates) > 1) stop("Multiple Seurat objects found. Candidates: ", paste(candidates, collapse = ", "))
  object_name <- candidates[[1]]
  obj <- env[[object_name]]
}
if (!inherits(obj, "Seurat")) stop("Selected object is not a Seurat object")

meta <- obj@meta.data
columns <- colnames(meta)
conventional <- unique(c(
  intersect("seurat_clusters", columns),
  grep("cluster|snn_res", columns, value = TRUE, ignore.case = TRUE)
))
cat("OBJECT\t", object_name, "\n", sep = "")
cat("CELLS\t", ncol(obj), "\n", sep = "")
cat("GENES\t", nrow(obj), "\n", sep = "")
cat("ASSAYS\t", paste(names(obj@assays), collapse = ","), "\n", sep = "")
if (length(conventional) == 0) {
  cat("CANDIDATES\t\n", sep = "")
} else {
  for (column in conventional) {
    values <- as.character(meta[[column]])
    valid <- values[!is.na(values) & values != ""]
    levels_preview <- paste(utils::head(unique(valid), 20), collapse = ",")
    cat("CANDIDATE\t", column, "\t", length(unique(valid)),
        "\t", sum(is.na(values) | values == ""), "\t", levels_preview, "\n", sep = "")
  }
}