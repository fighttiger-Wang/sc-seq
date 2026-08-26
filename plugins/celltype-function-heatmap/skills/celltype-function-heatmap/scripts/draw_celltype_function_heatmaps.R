#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, encoding = "UTF-8")
if (.Platform$OS.type == "windows") {
  try(Sys.setlocale("LC_CTYPE", "Chinese (Simplified)_China.utf8"), silent = TRUE)
}

required_packages <- c("readxl", "openxlsx", "ggplot2", "patchwork", "yaml", "stringr", "scales")
missing_packages <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing_packages)) {
  stop("Missing R packages: ", paste(missing_packages, collapse = ", "))
}

suppressPackageStartupMessages({
  library(ggplot2)
  library(patchwork)
})

`%||%` <- function(x, y) if (is.null(x)) y else x

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("Usage: Rscript draw_celltype_function_heatmaps.R <parameters.yaml>")

parameter_file <- normalizePath(args[[1]], mustWork = TRUE)
parameter_dir <- dirname(parameter_file)
cfg <- yaml::read_yaml(parameter_file)

is_absolute <- function(path) grepl("^([A-Za-z]:[/\\\\]|/)", path)
resolve_path <- function(path, base) {
  if (is.null(path) || !nzchar(path)) stop("A required path is empty")
  normalized <- if (is_absolute(path)) path else file.path(base, path)
  normalizePath(normalized, winslash = "/", mustWork = FALSE)
}

input_dir <- resolve_path(cfg$input_dir %||% ".", parameter_dir)
output_root <- resolve_path(cfg$output_dir %||% "./output", parameter_dir)
output_dir <- file.path(output_root, "final")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

input_file <- function(key) {
  filename <- cfg[[key]]
  if (is.null(filename)) stop("Missing YAML key: ", key)
  path <- resolve_path(filename, input_dir)
  if (!file.exists(path)) stop("Input file does not exist: ", path)
  path
}

read_expression_matrix <- function(path) {
  x <- read.delim(path, check.names = FALSE, stringsAsFactors = FALSE)
  if (!identical(names(x)[1], "gene")) stop("First matrix column must be named gene: ", path)
  if (anyDuplicated(x$gene)) stop("Duplicated gene symbols in: ", path)
  rownames(x) <- x$gene
  x$gene <- NULL
  m <- as.matrix(x)
  suppressWarnings(storage.mode(m) <- "numeric")
  if (any(!is.finite(m))) stop("Matrix contains non-numeric or non-finite values: ", path)
  m
}

celltype_matrix_path <- input_file("celltype_matrix")
sample_matrix_path <- input_file("celltype_sample_matrix")
gene_groups_path <- input_file("gene_groups")
celltype_colors_path <- input_file("celltype_colors")

celltype_mat <- read_expression_matrix(celltype_matrix_path)
sample_mat <- read_expression_matrix(sample_matrix_path)

gene_sheet <- cfg$gene_groups_sheet %||% 1
color_sheet <- cfg$celltype_colors_sheet %||% 1
gene_tbl <- readxl::read_excel(gene_groups_path, sheet = gene_sheet)
color_tbl <- readxl::read_excel(celltype_colors_path, sheet = color_sheet)

if (ncol(gene_tbl) < 2) stop("Gene-module workbook needs at least two columns")
group_col <- cfg$gene_group_column %||% names(gene_tbl)[1]
gene_col <- cfg$gene_list_column %||% names(gene_tbl)[2]
if (!all(c(group_col, gene_col) %in% names(gene_tbl))) {
  stop("Gene-module columns not found: ", paste(setdiff(c(group_col, gene_col), names(gene_tbl)), collapse = ", "))
}
if (!all(c("Celltype", "Hex_Color") %in% names(color_tbl))) {
  stop("Cell-type color table must contain Celltype and Hex_Color columns")
}

excluded <- as.character(unlist(cfg$exclude_celltypes %||% list(), use.names = FALSE))
celltype_mat <- celltype_mat[, !colnames(celltype_mat) %in% excluded, drop = FALSE]
color_tbl <- color_tbl[!color_tbl$Celltype %in% excluded, , drop = FALSE]
if (!nrow(color_tbl)) stop("No retained cell types after exclusions")
if (anyDuplicated(color_tbl$Celltype)) stop("Duplicated Celltype values in color table")
configured_celltype_order <- as.character(unlist(cfg$celltype_order %||% list(), use.names = FALSE))
if (length(configured_celltype_order)) {
  if (any(!nzchar(configured_celltype_order)) || anyDuplicated(configured_celltype_order)) {
    stop("celltype_order must contain unique non-empty names")
  }
  if (!setequal(configured_celltype_order, color_tbl$Celltype)) {
    stop("celltype_order does not exactly match retained Celltype values in the color table")
  }
  color_tbl <- color_tbl[match(configured_celltype_order, color_tbl$Celltype), , drop = FALSE]
} else if ("Plot_Order" %in% names(color_tbl)) {
  if (anyNA(color_tbl$Plot_Order) || anyDuplicated(color_tbl$Plot_Order)) stop("Plot_Order must be complete and unique")
  color_tbl <- color_tbl[order(color_tbl$Plot_Order), , drop = FALSE]
}
celltype_order <- as.character(color_tbl$Celltype)
if (!setequal(colnames(celltype_mat), celltype_order)) {
  stop("Cell-type matrix columns do not exactly match the retained color table")
}
if (any(!grepl("^#[0-9A-Fa-f]{6}$", color_tbl$Hex_Color))) stop("Hex_Color values must use #RRGGBB format")
celltype_mat <- celltype_mat[, celltype_order, drop = FALSE]
celltype_colors <- setNames(as.character(color_tbl$Hex_Color), celltype_order)

parse_genes <- function(x) {
  genes <- trimws(unlist(strsplit(as.character(x), "[;,，；]+")))
  genes[nzchar(genes)]
}

configured_module_names <- as.character(unlist(cfg$module_names %||% list(), use.names = FALSE))
module_names <- if (length(configured_module_names)) configured_module_names else trimws(as.character(gene_tbl[[group_col]]))
if (length(module_names) != nrow(gene_tbl)) stop("module_names must have one entry per gene-module workbook row")
if (any(!nzchar(module_names)) || anyDuplicated(module_names)) stop("Module names must be non-empty and unique")
requested_by_module <- lapply(gene_tbl[[gene_col]], parse_genes)
if (any(lengths(requested_by_module) == 0)) stop("Every module must contain at least one gene")

gene_aliases <- unlist(cfg$gene_aliases %||% list(), use.names = TRUE)
resolve_genes <- function(genes) {
  hit <- genes %in% names(gene_aliases)
  genes[hit] <- unname(gene_aliases[genes[hit]])
  genes
}
genes_by_module <- lapply(requested_by_module, resolve_genes)
all_genes <- unlist(genes_by_module, use.names = FALSE)
requested_genes <- unlist(requested_by_module, use.names = FALSE)
if (anyDuplicated(all_genes)) stop("Genes repeat across modules after alias resolution")
missing_genes <- unique(c(setdiff(all_genes, rownames(celltype_mat)), setdiff(all_genes, rownames(sample_mat))))
if (length(missing_genes)) stop("Missing genes: ", paste(missing_genes, collapse = ", "))

gene_meta <- do.call(rbind, lapply(seq_along(module_names), function(i) {
  data.frame(
    gene = genes_by_module[[i]],
    requested_gene = requested_by_module[[i]],
    Module = module_names[[i]],
    module_order = i,
    gene_order = seq_along(genes_by_module[[i]]),
    stringsAsFactors = FALSE
  )
}))
gene_meta$Module <- factor(gene_meta$Module, levels = module_names)

sample_keep <- !vapply(colnames(sample_mat), function(column) {
  any(vapply(excluded, function(celltype) startsWith(column, paste0(celltype, "_")), logical(1)))
}, logical(1))
sample_mat <- sample_mat[, sample_keep, drop = FALSE]

parse_sample_columns <- function(columns) {
  candidates <- celltype_order[order(nchar(celltype_order), decreasing = TRUE)]
  do.call(rbind, lapply(columns, function(column) {
    hit <- candidates[startsWith(column, paste0(candidates, "_"))]
    if (length(hit) != 1) stop("Cannot uniquely parse sample-matrix column: ", column)
    data.frame(
      column = column,
      Celltype = hit,
      Sample = substring(column, nchar(hit) + 2),
      stringsAsFactors = FALSE
    )
  }))
}

sample_meta <- parse_sample_columns(colnames(sample_mat))
if (any(!nzchar(sample_meta$Sample))) stop("Sample names must be non-empty")
if (anyDuplicated(sample_meta[c("Sample", "Celltype")])) stop("Duplicated sample-celltype combinations")
sample_order <- unique(sample_meta$Sample)
expected_pairs <- expand.grid(Sample = sample_order, Celltype = celltype_order, stringsAsFactors = FALSE)
observed_keys <- paste(sample_meta$Sample, sample_meta$Celltype, sep = "\r")
expected_keys <- paste(expected_pairs$Sample, expected_pairs$Celltype, sep = "\r")
if (!setequal(observed_keys, expected_keys)) stop("Every sample must contain every retained cell type exactly once")
sample_meta$sample_i <- match(sample_meta$Sample, sample_order)
sample_meta$celltype_i <- match(sample_meta$Celltype, celltype_order)
sample_meta <- sample_meta[order(sample_meta$sample_i, sample_meta$celltype_i), , drop = FALSE]
sample_columns <- sample_meta$column
sample_mat <- sample_mat[, sample_columns, drop = FALSE]

default_sample_palette <- c("#E15759", "#4E79A7", "#F28E2B", "#59A14F")
sample_colors <- setNames(rep(default_sample_palette, length.out = length(sample_order)), sample_order)
if (length(sample_order) > length(default_sample_palette)) {
  sample_colors <- setNames(grDevices::hcl.colors(length(sample_order), "Dark 3"), sample_order)
}
provided_sample_colors <- unlist(cfg$sample_colors %||% list(), use.names = TRUE)
valid_sample_overrides <- intersect(names(provided_sample_colors), sample_order)
sample_colors[valid_sample_overrides] <- provided_sample_colors[valid_sample_overrides]

default_module_palette <- c("#66C2A5", "#FC8D62", "#8DA0CB", "#E78AC3", "#A6D854", "#FFD92F", "#E5C494", "#B3B3B3")
module_colors <- setNames(rep(default_module_palette, length.out = length(module_names)), module_names)
if (length(module_names) > length(default_module_palette)) {
  module_colors <- setNames(grDevices::hcl.colors(length(module_names), "Set 3"), module_names)
}
provided_module_colors <- unlist(cfg$module_colors %||% list(), use.names = TRUE)
valid_module_overrides <- intersect(names(provided_module_colors), module_names)
module_colors[valid_module_overrides] <- provided_module_colors[valid_module_overrides]

plot_cfg <- cfg$plot %||% list()
z_limit <- as.numeric(plot_cfg$z_limit %||% 2.5)
if (!is.finite(z_limit) || z_limit <= 0) stop("plot.z_limit must be a positive number")
dpi <- as.numeric(plot_cfg$dpi %||% 300)
palette_low <- plot_cfg$palette_low %||% "#67A9CF"
palette_mid <- plot_cfg$palette_mid %||% "#F7F7F7"
palette_high <- plot_cfg$palette_high %||% "#D43F79"
font_family <- plot_cfg$font_family %||% ""

module_boundaries <- cumsum(lengths(genes_by_module))
row_gap_positions <- length(all_genes) - module_boundaries[-length(module_boundaries)] + 0.5

long_matrix <- function(mat, columns) {
  m <- mat[all_genes, columns, drop = FALSE]
  d <- expand.grid(gene = rownames(m), column = colnames(m), stringsAsFactors = FALSE)
  d$value <- as.vector(m)
  d <- merge(d, gene_meta[c("gene", "Module", "module_order", "gene_order")], by = "gene", sort = FALSE)
  d$column <- factor(d$column, levels = columns)
  d$gene <- factor(d$gene, levels = rev(all_genes))
  d$Module <- factor(d$Module, levels = module_names)
  d
}

annotation_bar <- function(columns, values, colors, title) {
  d <- data.frame(
    column = factor(columns, levels = columns),
    value = factor(values, levels = names(colors)),
    y = title
  )
  ggplot(d, aes(column, y, fill = value)) +
    geom_tile(color = "white", linewidth = 0.35) +
    scale_fill_manual(values = colors, drop = TRUE, name = title) +
    scale_x_discrete(expand = c(0, 0)) +
    scale_y_discrete(expand = c(0, 0)) +
    labs(x = NULL, y = NULL) +
    theme_minimal(base_size = 9, base_family = font_family) +
    theme(
      panel.grid = element_blank(),
      axis.title = element_blank(),
      axis.text = element_blank(),
      axis.ticks = element_blank(),
      legend.position = "right",
      legend.text = element_text(size = 7),
      legend.title = element_text(size = 8, face = "bold"),
      plot.margin = margin(0, 0, 0, 0)
    )
}

wrap_celltype_label <- function(x, width) {
  wrapped <- stringr::str_wrap(gsub("_", "_ ", x, fixed = TRUE), width = width)
  gsub(" ", "", wrapped, fixed = TRUE)
}

column_label_panel <- function(columns, labels, label_pt, wrap_width, line_spacing) {
  d <- do.call(rbind, lapply(seq_along(columns), function(i) {
    lines <- strsplit(wrap_celltype_label(labels[i], wrap_width), "\n", fixed = TRUE)[[1]]
    n <- length(lines)
    data.frame(
      x = i + (seq_len(n) - (n + 1) / 2) * line_spacing,
      y = 0,
      label = lines,
      stringsAsFactors = FALSE
    )
  }))
  ggplot(d, aes(x, y, label = label)) +
    geom_text(
      angle = 90, hjust = 0, vjust = 0.5,
      size = label_pt / ggplot2::.pt, lineheight = 0.9,
      family = font_family, color = "black"
    ) +
    scale_x_continuous(limits = c(0.5, length(columns) + 0.5), expand = c(0, 0)) +
    scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
    coord_cartesian(clip = "off") +
    theme_void(base_family = font_family) +
    theme(plot.margin = margin(0, 0, 0, 0))
}

heat_panel <- function(mat, columns) {
  d <- long_matrix(mat, columns)
  ggplot(d, aes(column, gene, fill = value)) +
    geom_tile(color = "white", linewidth = 0.3) +
    scale_fill_gradient2(
      low = palette_low, mid = palette_mid, high = palette_high,
      midpoint = 0, limits = c(-z_limit, z_limit), oob = scales::squish,
      breaks = c(-z_limit, -1, 0, 1, z_limit), name = "Expression"
    ) +
    scale_x_discrete(expand = c(0, 0)) +
    scale_y_discrete(expand = c(0, 0)) +
    geom_hline(yintercept = row_gap_positions, color = "white", linewidth = 1.8) +
    labs(x = NULL, y = NULL) +
    theme_minimal(base_size = 10, base_family = font_family) +
    theme(
      panel.grid = element_blank(),
      axis.text = element_blank(),
      axis.ticks = element_blank(),
      legend.position = "right",
      legend.text = element_text(size = 7),
      legend.title = element_text(size = 8, face = "bold"),
      plot.margin = margin(0, 0, 0, 0)
    )
}

gene_annotation_panel <- function() {
  d <- gene_meta
  d$gene <- factor(d$gene, levels = rev(all_genes))
  ggplot(d, aes(x = 0.5, y = gene, fill = Module)) +
    geom_tile(color = NA) +
    geom_hline(yintercept = row_gap_positions, color = "white", linewidth = 1.8) +
    geom_text(
      aes(label = gene), x = 0.04, hjust = 0,
      size = 2.8, fontface = "italic", family = font_family, color = "black"
    ) +
    scale_fill_manual(values = module_colors, drop = FALSE, name = "Module") +
    scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
    scale_y_discrete(expand = c(0, 0)) +
    coord_cartesian(clip = "off") +
    theme_void(base_family = font_family) +
    theme(
      legend.position = "right",
      legend.text = element_text(size = 7),
      legend.title = element_text(size = 8, face = "bold"),
      plot.margin = margin(0, 0, 0, 0)
    )
}

gene_panel_width_cm <- max(vapply(all_genes, function(gene) {
  grid::convertWidth(
    grid::grobWidth(grid::textGrob(
      gene,
      gp = grid::gpar(fontsize = 8, fontface = "italic", fontfamily = font_family)
    )),
    unitTo = "cm", valueOnly = TRUE
  )
}, numeric(1))) + 0.45

compose_heatmap <- function(label_panel, annotation_rows, heat, label_height) {
  widths <- grid::unit(c(1, gene_panel_width_cm), c("null", "cm"))
  plots <- list(label_panel, plot_spacer())
  for (annotation in annotation_rows) plots <- c(plots, list(annotation, plot_spacer()))
  plots <- c(plots, list(heat, gene_annotation_panel()))
  cell_height <- 10 / length(all_genes)
  wrap_plots(
    plotlist = plots,
    ncol = 2,
    widths = widths,
    heights = c(label_height, rep(cell_height, length(annotation_rows)), 10),
    guides = "collect"
  ) & theme(legend.position = "right")
}

label_height <- as.numeric(plot_cfg$label_height %||% 1.7)
all_label_pt <- as.numeric(plot_cfg$all_celltypes_label_pt %||% 9)
sample_label_pt <- as.numeric(plot_cfg$sample_blocks_label_pt %||% 7)
all_wrap <- as.numeric(plot_cfg$all_celltypes_wrap_width %||% 28)
sample_wrap <- as.numeric(plot_cfg$sample_blocks_wrap_width %||% 24)
all_spacing <- as.numeric(plot_cfg$all_celltypes_line_spacing %||% 0.18)
sample_spacing <- as.numeric(plot_cfg$sample_blocks_line_spacing %||% 0.24)

all_labels <- column_label_panel(celltype_order, celltype_order, all_label_pt, all_wrap, all_spacing)
all_bar <- annotation_bar(celltype_order, celltype_order, celltype_colors, "Cell type")
all_plot <- compose_heatmap(all_labels, list(all_bar), heat_panel(celltype_mat, celltype_order), label_height)

sample_labels <- column_label_panel(sample_columns, as.character(sample_meta$Celltype), sample_label_pt, sample_wrap, sample_spacing)
sample_bar <- annotation_bar(sample_columns, as.character(sample_meta$Sample), sample_colors, "Sample")
sample_celltype_bar <- annotation_bar(sample_columns, as.character(sample_meta$Celltype), celltype_colors, "Cell type")
sample_plot <- compose_heatmap(sample_labels, list(sample_bar, sample_celltype_bar), heat_panel(sample_mat, sample_columns), label_height)

all_width <- as.numeric(plot_cfg$all_celltypes_width %||% 16)
sample_width <- as.numeric(plot_cfg$sample_blocks_width %||% 28)
plot_height <- as.numeric(plot_cfg$height %||% 17)

ggsave(file.path(output_dir, "01_all_celltypes.png"), all_plot, width = all_width, height = plot_height, dpi = dpi, bg = "white")
ggsave(file.path(output_dir, "01_all_celltypes.pdf"), all_plot, width = all_width, height = plot_height, device = cairo_pdf, bg = "white")
ggsave(file.path(output_dir, "02_sample_blocks.png"), sample_plot, width = sample_width, height = plot_height, dpi = dpi, bg = "white")
ggsave(file.path(output_dir, "02_sample_blocks.pdf"), sample_plot, width = sample_width, height = plot_height, device = cairo_pdf, bg = "white")

write.table(
  data.frame(gene = all_genes, celltype_mat[all_genes, celltype_order, drop = FALSE], check.names = FALSE),
  file.path(output_dir, "01_all_celltypes.tsv"), sep = "\t", quote = FALSE, row.names = FALSE
)
write.table(
  data.frame(gene = all_genes, sample_mat[all_genes, sample_columns, drop = FALSE], check.names = FALSE),
  file.path(output_dir, "02_sample_blocks.tsv"), sep = "\t", quote = FALSE, row.names = FALSE
)

png_files <- list.files(output_dir, pattern = "\\.png$", full.names = FALSE)
pdf_files <- list.files(output_dir, pattern = "\\.pdf$", full.names = FALSE)
checks <- data.frame(
  check = c(
    "Exactly two PNG heatmaps",
    "Exactly two PDF heatmaps",
    "Cell-type matrix follows color-table order",
    "Sample blocks preserve source encounter order",
    "Every sample repeats the same cell-type order",
    "Genes follow module workbook order",
    "Excluded cell types are absent",
    "All plotted values are finite"
  ),
  passed = c(
    identical(sort(png_files), sort(c("01_all_celltypes.png", "02_sample_blocks.png"))),
    identical(sort(pdf_files), sort(c("01_all_celltypes.pdf", "02_sample_blocks.pdf"))),
    identical(colnames(celltype_mat), celltype_order),
    identical(unique(sample_meta$Sample), sample_order),
    all(vapply(sample_order, function(sample) identical(sample_meta$Celltype[sample_meta$Sample == sample], celltype_order), logical(1))),
    identical(gene_meta$gene, all_genes),
    !any(c(colnames(celltype_mat), sample_meta$Celltype) %in% excluded),
    all(is.finite(celltype_mat[all_genes, , drop = FALSE])) && all(is.finite(sample_mat[all_genes, , drop = FALSE]))
  ),
  stringsAsFactors = FALSE
)

alias_table <- data.frame(
  requested_gene = requested_genes,
  plotted_gene = all_genes,
  alias_applied = requested_genes != all_genes,
  stringsAsFactors = FALSE
)
openxlsx::write.xlsx(
  list(
    Checks = checks,
    Gene_Aliases = alias_table,
    Celltypes = data.frame(order = seq_along(celltype_order), Celltype = celltype_order, Color = unname(celltype_colors)),
    Samples = data.frame(order = seq_along(sample_order), Sample = sample_order, Color = unname(sample_colors)),
    Modules = gene_meta
  ),
  file.path(output_dir, "QA_summary.xlsx"),
  overwrite = TRUE
)

summary_lines <- c(
  "Cell-type function heatmap run completed",
  paste0("Parameter file: ", parameter_file),
  paste0("Output directory: ", output_dir),
  paste0("Retained cell types: ", length(celltype_order)),
  paste0("Samples: ", paste(sample_order, collapse = " -> ")),
  paste0("Genes: ", length(all_genes)),
  paste0("Modules: ", length(module_names)),
  paste0("Excluded cell types: ", if (length(excluded)) paste(excluded, collapse = ", ") else "none"),
  paste0("QA: ", if (all(checks$passed)) "PASS" else "FAIL")
)
writeLines(summary_lines, file.path(output_dir, "run_summary.txt"), useBytes = TRUE)

if (!all(checks$passed)) stop("QA failed; inspect QA_summary.xlsx")
message("Completed: ", output_dir)
