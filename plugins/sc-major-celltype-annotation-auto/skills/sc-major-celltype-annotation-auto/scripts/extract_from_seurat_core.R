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
required <- c("input", "output-dir", "cluster-column")
missing <- required[!required %in% names(opt)]
if (length(missing) > 0) stop("Missing required arguments: ", paste(missing, collapse = ", "))
if (!requireNamespace("Seurat", quietly = TRUE)) stop("R package 'Seurat' is required")
input <- normalizePath(opt$input, mustWork = TRUE)
if (.Platform$OS.type == "windows" && toupper(substr(input, 1, 2)) == "C:") stop("C: input is blocked by workspace policy; provide an E: copy")
output_requested <- normalizePath(dirname(opt[["output-dir"]]), mustWork = TRUE)
if (.Platform$OS.type == "windows" && toupper(substr(output_requested, 1, 2)) != "E:") stop("Output must be on E:")
dir.create(opt[["output-dir"]], recursive = TRUE, showWarnings = FALSE)
output_dir <- normalizePath(opt[["output-dir"]], mustWork = TRUE)
cluster_column <- opt[["cluster-column"]]
object_name <- opt[["object-name"]] %||% ""
assay_requested <- opt$assay %||% "RNA"
slot_requested <- opt$slot %||% "data"
min_pct <- as.numeric(opt[["min-pct"]] %||% "0.1")
logfc_threshold <- as.numeric(opt[["logfc-threshold"]] %||% "0.25")

load_object <- function(path, preferred_name = "") {
  ext <- tolower(tools::file_ext(path))
  if (ext == "rds") return(list(object = readRDS(path), name = basename(path)))
  if (ext == "qs") {
    if (!requireNamespace("qs", quietly = TRUE)) stop("R package 'qs' is required for .qs input")
    return(list(object = qs::qread(path), name = basename(path)))
  }
  env <- new.env(parent = emptyenv()); loaded_names <- load(path, envir = env)
  if (preferred_name != "") {
    if (!exists(preferred_name, envir = env, inherits = FALSE)) stop("Object not found: ", preferred_name)
    obj <- env[[preferred_name]]
    if (!inherits(obj, "Seurat")) stop("Selected object is not a Seurat object: ", preferred_name)
    return(list(object = obj, name = preferred_name))
  }
  candidates <- loaded_names[vapply(loaded_names, function(nm) inherits(env[[nm]], "Seurat"), logical(1))]
  if (length(candidates) == 0) stop("No Seurat object found. Loaded names: ", paste(loaded_names, collapse = ", "))
  if (length(candidates) > 1) stop("Multiple Seurat objects found; rerun with --object-name. Candidates: ", paste(candidates, collapse = ", "))
  list(object = env[[candidates[[1]]]], name = candidates[[1]])
}

loaded <- load_object(input, object_name); obj <- loaded$object
if (!cluster_column %in% colnames(obj@meta.data)) {
  candidates <- grep("cluster|snn_res", colnames(obj@meta.data), value = TRUE, ignore.case = TRUE)
  stop("Cluster column not found: ", cluster_column, ". Candidate columns: ", paste(candidates, collapse = ", "))
}
assay <- if (assay_requested %in% names(obj@assays)) assay_requested else Seurat::DefaultAssay(obj)
Seurat::DefaultAssay(obj) <- assay
groups <- as.character(obj@meta.data[[cluster_column]])
if (anyNA(groups) || any(groups == "")) stop("Cluster column contains missing/empty values")
obj[[cluster_column]] <- factor(groups, levels = unique(groups)); Seurat::Idents(obj) <- cluster_column
avg_list <- suppressMessages(Seurat::AverageExpression(obj, assays = assay, group.by = cluster_column, slot = slot_requested, verbose = FALSE, return.seurat = FALSE))
avg <- as.matrix(avg_list[[assay]]); colnames(avg) <- sub("^g(?=[0-9])", "", colnames(avg), perl = TRUE)
avg_df <- data.frame(GeneName = rownames(avg), avg, check.names = FALSE)
ratio_matrix <- tryCatch(
  Seurat::GetAssayData(obj, assay = assay, slot = "counts"),
  error = function(e) Seurat::GetAssayData(obj, assay = assay, slot = slot_requested)
)
if (!all(colnames(obj) %in% colnames(ratio_matrix))) stop("Assay matrix and metadata cell names do not match")
ratio_matrix <- ratio_matrix[, colnames(obj), drop = FALSE]
group_levels <- unique(groups)
detection <- sapply(group_levels, function(group) {
  cells <- which(groups == group)
  if (length(cells) == 1) as.numeric(ratio_matrix[, cells, drop = TRUE] > 0) else Matrix::rowMeans(ratio_matrix[, cells, drop = FALSE] > 0)
})
if (is.null(dim(detection))) detection <- matrix(detection, ncol = 1)
rownames(detection) <- rownames(ratio_matrix); colnames(detection) <- group_levels
common_genes <- intersect(rownames(avg), rownames(detection))
ratio_rows <- lapply(group_levels, function(group) {
  values <- avg[common_genes, group]
  scaled <- as.numeric(scale(values))
  scaled[is.na(scaled)] <- 0
  data.frame(gene = common_genes, group = group, mean_expr = values,
             expr_ratio = detection[common_genes, group], norm_expr = scaled,
             check.names = FALSE)
})
ratio_df <- do.call(rbind, ratio_rows)
markers <- suppressMessages(Seurat::FindAllMarkers(obj, assay = assay, slot = slot_requested, only.pos = TRUE, min.pct = min_pct, logfc.threshold = logfc_threshold, verbose = FALSE))
if (nrow(markers) == 0) stop("FindAllMarkers returned zero rows")
markers$GeneName <- rownames(markers)
fc_candidates <- intersect(c("avg_log2FC", "avg_logFC"), colnames(markers))
if (length(fc_candidates) == 0) stop("FindAllMarkers output has no avg_log2FC/avg_logFC column")
fc_col <- fc_candidates[[1]]; cluster_sizes <- table(groups)
weighted_other_mean <- function(gene, target) {
  if (!gene %in% rownames(avg)) return(NA_real_)
  other <- setdiff(colnames(avg), as.character(target))
  other <- intersect(other, names(cluster_sizes))
  if (length(other) == 0) return(NA_real_)
  weights <- as.numeric(cluster_sizes[other])
  if (anyNA(weights) || sum(weights) == 0) return(NA_real_)
  sum(avg[gene, other, drop = TRUE] * weights) / sum(weights)
}
target_mean <- mapply(function(gene, cluster) if (gene %in% rownames(avg) && as.character(cluster) %in% colnames(avg)) avg[gene, as.character(cluster)] else NA_real_, markers$GeneName, markers$cluster)
other_mean <- mapply(weighted_other_mean, markers$GeneName, markers$cluster)
marker_df <- data.frame(Target_Cluster = as.character(markers$cluster), GeneID = ifelse(grepl("^ENS[A-Z]*G[0-9]+", markers$GeneName), markers$GeneName, NA_character_), GeneName = markers$GeneName, Target_Cluster_mean = target_mean, Other_Cluster_mean = other_mean, log2FC = markers[[fc_col]], pct.1 = markers$pct.1, pct.2 = markers$pct.2, Pvlaue = markers$p_val, Qvalue = markers$p_val_adj, Description = NA_character_, GO = NA_character_, KEGG = NA_character_, KO_ENTRY = NA_character_, EC = NA_character_, check.names = FALSE)
marker_df <- marker_df[order(match(marker_df$Target_Cluster, unique(groups)), -marker_df$log2FC), ]
avg_tsv <- file.path(output_dir, "cell_avg_exp.tsv"); marker_tsv <- file.path(output_dir, "Markergene_list.tsv")
ratio_tsv <- file.path(output_dir, "avg_expr_result.txt")
write.table(avg_df, avg_tsv, sep = "\t", quote = FALSE, row.names = FALSE, na = "NA")
write.table(marker_df, marker_tsv, sep = "\t", quote = FALSE, row.names = FALSE, na = "NA")
write.table(ratio_df, ratio_tsv, sep = "\t", quote = FALSE, row.names = FALSE, na = "NA")
manifest <- data.frame(key = c("input", "object_name", "assay", "slot", "cluster_column", "cell_count", "gene_count", "cluster_count", "min_pct", "logfc_threshold", "average_tsv", "marker_tsv", "ratio_tsv"), value = c(input, loaded$name, assay, slot_requested, cluster_column, ncol(obj), nrow(avg), ncol(avg), min_pct, logfc_threshold, avg_tsv, marker_tsv, ratio_tsv))
write.table(manifest, file.path(output_dir, "extraction_manifest.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
cat("Created TSV files:\n", avg_tsv, "\n", marker_tsv, "\n", ratio_tsv, "\n", sep = "")
