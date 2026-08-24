#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(Seurat)
  library(ggplot2)
  library(dplyr)
  library(patchwork)
})

if (.Platform$OS.type == "windows") {
  invisible(suppressWarnings(try(Sys.setlocale("LC_CTYPE", "Chinese"), silent = TRUE)))
}

parse_args <- function(x) {
  out <- list()
  i <- 1L
  while (i <= length(x)) {
    key <- sub("^--", "", x[[i]])
    if (i == length(x)) stop("Missing value for --", key)
    out[[key]] <- x[[i + 1L]]
    i <- i + 2L
  }
  out
}

csv_values <- function(x) {
  if (is.null(x) || !nzchar(x)) return(character())
  trimws(strsplit(x, ",", fixed = TRUE)[[1]])
}

arg_or <- function(args, name, default) {
  value <- args[[name]]
  if (is.null(value) || !nzchar(value)) default else value
}

require_packages <- function(packages) {
  missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing)) stop("Missing R packages: ", paste(missing, collapse = ", "))
}

read_seurat <- function(path, object_name = "") {
  if (!file.exists(path)) stop("Seurat input not found: ", path)
  ext <- tolower(tools::file_ext(path))
  if (ext == "rds") {
    object <- readRDS(path)
  } else if (ext %in% c("rda", "rdata")) {
    env <- new.env(parent = emptyenv())
    loaded <- load(path, envir = env)
    if (nzchar(object_name)) {
      if (!object_name %in% loaded) stop("Object not found in RData: ", object_name)
      object <- env[[object_name]]
    } else {
      candidates <- loaded[vapply(loaded, function(x) inherits(env[[x]], "Seurat"), logical(1))]
      if (length(candidates) != 1L) {
        stop("Expected exactly one Seurat object; provide --object-name. Found: ",
             paste(candidates, collapse = ", "))
      }
      object <- env[[candidates[[1]]]]
    }
  } else {
    stop("Unsupported Seurat file extension: ", ext)
  }
  if (!inherits(object, "Seurat")) stop("Loaded object is not a Seurat object")
  object
}

read_markers <- function(path, sheet = "") {
  if (!file.exists(path)) stop("Marker table not found: ", path)
  ext <- tolower(tools::file_ext(path))
  if (ext == "csv") {
    data <- read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)
  } else if (ext %in% c("xlsx", "xls")) {
    require_packages("readxl")
    data <- if (nzchar(sheet)) {
      as.data.frame(readxl::read_excel(path, sheet = sheet))
    } else {
      as.data.frame(readxl::read_excel(path, sheet = 1))
    }
  } else {
    stop("Unsupported marker-table extension: ", ext)
  }
  if (!all(c("cluster", "gene") %in% colnames(data))) {
    stop("Marker table must contain columns: cluster, gene")
  }
  data$cluster <- as.character(data$cluster)
  data$gene <- as.character(data$gene)
  data
}

p_to_star <- function(p) {
  ifelse(p < 1e-4, "****",
    ifelse(p < 1e-3, "***",
      ifelse(p < 1e-2, "**", ifelse(p < 0.05, "*", "ns"))))
}

base_png <- function(filename, width, height, units, res, bg, ...) {
  grDevices::png(filename = filename, width = width, height = height,
                 units = units, res = res, bg = bg)
}

make_palette <- function(n) {
  base <- c(
    "#D66D75", "#D88735", "#C5A13B", "#91AA48", "#56A66E",
    "#35A497", "#369DB2", "#4D8FC3", "#657AC3", "#7E6CBA",
    "#9864B2", "#B260A7", "#CA659B", "#DB708B", "#DF7D78"
  )
  if (n <= length(base)) base[seq_len(n)] else grDevices::colorRampPalette(base)(n)
}

args <- parse_args(commandArgs(trailingOnly = TRUE))
required_args <- c("seurat", "markers", "output", "cluster-column", "violin-genes")
missing_args <- required_args[!required_args %in% names(args)]
if (length(missing_args)) stop("Missing arguments: ", paste(missing_args, collapse = ", "))

require_packages(c("Seurat", "ggplot2", "dplyr", "patchwork", "scales"))

seurat_path <- args$seurat
marker_path <- args$markers
output_dir <- args$output
cluster_column <- args$`cluster-column`
celltype_column <- arg_or(args, "celltype-column", "")
object_name <- arg_or(args, "object-name", "")
marker_sheet <- arg_or(args, "marker-sheet", "")
assay <- arg_or(args, "assay", "RNA")
reference_celltype <- arg_or(args, "reference-celltype", "")
violin_genes <- csv_values(args$`violin-genes`)
top_signature_n <- as.integer(arg_or(args, "top-signature-genes", "30"))
label_genes_per_type <- as.integer(arg_or(args, "label-genes-per-type", "2"))
max_cells_per_type <- as.integer(arg_or(args, "max-cells-per-type", "40"))
z_limit <- as.numeric(arg_or(args, "z-limit", "2"))
seed <- as.integer(arg_or(args, "seed", "20260722"))

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
set.seed(seed)

obj <- read_seurat(seurat_path, object_name)
if (!assay %in% Assays(obj)) stop("Assay not found: ", assay)
DefaultAssay(obj) <- assay
if (!cluster_column %in% colnames(obj[[]])) stop("Cluster column not found: ", cluster_column)

markers <- read_markers(marker_path, marker_sheet)
if ("p_val_adj" %in% colnames(markers)) markers <- markers[markers$p_val_adj < 0.05, , drop = FALSE]
fc_column <- intersect(c("avg_log2FC", "avg_logFC"), colnames(markers))
if (length(fc_column)) markers <- markers[markers[[fc_column[[1]]]] > 0, , drop = FALSE]
markers <- markers[markers$gene %in% rownames(obj) & nzchar(markers$cluster), , drop = FALSE]
if (!nrow(markers)) stop("No usable positive marker genes remain after filtering")
if (length(fc_column)) {
  markers <- markers[order(markers$cluster, -markers[[fc_column[[1]]]]), , drop = FALSE]
}

mapping_mode <- "provided"
if (nzchar(celltype_column)) {
  if (!celltype_column %in% colnames(obj[[]])) stop("Cell-type column not found: ", celltype_column)
  obj$skill_celltype <- as.character(obj[[celltype_column, drop = TRUE]])
} else {
  mapping_mode <- "inferred"
  signature_table <- markers |>
    group_by(cluster) |>
    slice_head(n = top_signature_n) |>
    ungroup()
  signature_genes <- unique(signature_table$gene)
  avg <- AverageExpression(
    obj, assays = assay, features = signature_genes,
    group.by = cluster_column, layer = "data", verbose = FALSE
  )[[assay]]
  avg <- log1p(avg)
  gene_z <- t(scale(t(avg)))
  gene_z[!is.finite(gene_z)] <- 0
  candidate_types <- unique(signature_table$cluster)
  scores <- sapply(candidate_types, function(cell_type) {
    genes <- intersect(signature_table$gene[signature_table$cluster == cell_type], rownames(gene_z))
    colMeans(gene_z[genes, , drop = FALSE])
  })
  rownames(scores) <- colnames(gene_z)
  predicted <- apply(scores, 1, function(x) candidate_types[which.max(x)])
  mapping <- data.frame(cluster = rownames(scores), celltype = unname(predicted),
                        score = apply(scores, 1, max), stringsAsFactors = FALSE)
  map_vector <- setNames(mapping$celltype, mapping$cluster)
  obj$skill_celltype <- unname(map_vector[as.character(obj[[cluster_column, drop = TRUE]])])
  write.csv(mapping, file.path(output_dir, "celltype_mapping.csv"), row.names = FALSE)
}

if (anyNA(obj$skill_celltype) || any(!nzchar(obj$skill_celltype))) {
  stop("Cell-type assignment contains missing or empty values")
}

marker_type_order <- unique(markers$cluster)
observed_types <- unique(obj$skill_celltype)
type_order <- c(intersect(marker_type_order, observed_types), setdiff(observed_types, marker_type_order))
obj$skill_celltype <- factor(obj$skill_celltype, levels = type_order)
Idents(obj) <- "skill_celltype"
palette <- setNames(make_palette(length(type_order)), type_order)

heatmap_markers <- markers[markers$cluster %in% type_order, , drop = FALSE]
heatmap_genes <- unique(heatmap_markers$gene)
label_genes <- heatmap_markers |>
  group_by(cluster) |>
  slice_head(n = label_genes_per_type) |>
  ungroup() |>
  pull(gene) |>
  unique()

cells_by_type <- split(colnames(obj), obj$skill_celltype)
sampled_cells <- unlist(lapply(cells_by_type, function(cells) {
  sample(cells, min(length(cells), max_cells_per_type))
}), use.names = FALSE)
sampled_cells <- sampled_cells[!is.na(sampled_cells)]
if (!length(sampled_cells)) stop("No cells available for heatmap")

sampled_expression <- GetAssayData(obj, assay = assay, layer = "data")[
  heatmap_genes, sampled_cells, drop = FALSE
]
sampled_expression <- as.matrix(sampled_expression)
scaled <- t(scale(t(sampled_expression)))
scaled[!is.finite(scaled)] <- 0
scaled <- pmax(pmin(scaled, z_limit), -z_limit)

type_vector <- as.character(obj$skill_celltype[sampled_cells])
cell_rank <- ave(seq_along(sampled_cells), type_vector, FUN = seq_along)
type_rank <- match(type_vector, type_order)
ord <- order(type_rank, cell_rank)
sampled_cells <- sampled_cells[ord]
type_vector <- type_vector[ord]
scaled <- scaled[, sampled_cells, drop = FALSE]

heat_df <- as.data.frame(as.table(t(scaled)), stringsAsFactors = FALSE)
colnames(heat_df) <- c("cell", "gene", "z")
heat_df$cell_index <- match(heat_df$cell, sampled_cells)
heat_df$gene_index <- match(heat_df$gene, heatmap_genes)

label_df <- data.frame(gene = label_genes,
                       gene_position = match(label_genes, heatmap_genes),
                       stringsAsFactors = FALSE) |>
  arrange(gene_position)
label_df$label_position <- seq(1, length(heatmap_genes), length.out = nrow(label_df))
label_df$line_end_y <- -0.035 * length(sampled_cells)
label_df$text_y <- -0.05 * length(sampled_cells)

type_bounds <- data.frame(cell_type = type_vector, cell_index = seq_along(type_vector)) |>
  group_by(cell_type) |>
  summarise(y = mean(range(cell_index)), ymin = min(cell_index) - 0.5,
            ymax = max(cell_index) + 0.5, .groups = "drop")
type_bounds$cell_type <- factor(type_bounds$cell_type, levels = type_order)
type_bounds <- arrange(type_bounds, cell_type)
block_df <- type_bounds |>
  mutate(ymin_draw = ymin + 0.75 / 2, ymax_draw = ymax - 0.75 / 2)

p_annotation <- ggplot(block_df) +
  geom_rect(aes(xmin = 0.5, xmax = 1.5, ymin = ymin_draw, ymax = ymax_draw,
                fill = cell_type), color = "white", linewidth = 0.18) +
  scale_fill_manual(values = palette, drop = FALSE) +
  scale_y_continuous(limits = c(0.5, length(sampled_cells) + 0.5),
                     breaks = type_bounds$y, labels = type_bounds$cell_type,
                     expand = c(0, 0)) +
  scale_x_continuous(limits = c(0.5, 1.5), expand = c(0, 0)) +
  labs(x = NULL, y = NULL) +
  theme_void(base_size = 9) +
  theme(axis.text.y = element_text(color = "#333333", hjust = 1),
        axis.text.y.left = element_text(margin = margin(r = 4)),
        legend.position = "none", plot.margin = margin(0, 0, 0, 0))

p_heat <- ggplot(heat_df, aes(gene_index, cell_index, fill = z)) +
  geom_raster() +
  geom_hline(data = type_bounds[-nrow(type_bounds), , drop = FALSE],
             aes(yintercept = ymax), linewidth = 0.25, color = "white") +
  geom_segment(data = label_df,
               aes(x = gene_position, xend = label_position, y = 0.5, yend = line_end_y),
               inherit.aes = FALSE, linewidth = 0.25, color = "#555555") +
  geom_text(data = label_df, aes(x = label_position, y = text_y, label = gene),
            inherit.aes = FALSE, angle = 70, hjust = 1, vjust = 0.5,
            size = 2.4, color = "#222222") +
  scale_fill_gradient2(low = "#3B4CC0", mid = "#F3E9D6", high = "#B40426",
                       midpoint = 0, limits = c(-z_limit, z_limit),
                       oob = scales::squish, guide = "none") +
  scale_y_continuous(expand = c(0, 0)) +
  scale_x_continuous(expand = c(0, 0), breaks = NULL) +
  coord_cartesian(ylim = c(0.5, length(sampled_cells) + 0.5), clip = "off") +
  labs(x = NULL, y = NULL) +
  theme_classic(base_size = 9) +
  theme(axis.text = element_blank(), axis.ticks = element_blank(),
        axis.line = element_blank(), plot.margin = margin(0, 0, 72, 0))

legend_data <- data.frame(x = seq(-z_limit, z_limit, length.out = 400), y = 1)
tile_width <- (2 * z_limit) / nrow(legend_data) * 1.05
p_legend <- ggplot(legend_data, aes(x, y, fill = x)) +
  geom_tile(width = tile_width, height = 0.22) +
  scale_fill_gradient2(low = "#3B4CC0", mid = "#F3E9D6", high = "#B40426",
                       midpoint = 0, limits = c(-z_limit, z_limit), guide = "none") +
  scale_x_continuous(breaks = seq(-z_limit, z_limit, by = 1), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0.84, 1.16), expand = c(0, 0)) +
  labs(title = "Expression", x = NULL, y = NULL) +
  theme_void(base_size = 8) +
  theme(plot.title = element_text(hjust = 0, size = 8, margin = margin(b = 2)),
        axis.text.x = element_text(color = "#222222", size = 7, margin = margin(t = 2)),
        axis.ticks.x = element_line(color = "#333333", linewidth = 0.25),
        axis.ticks.length.x = grid::unit(1.5, "mm"),
        plot.margin = margin(0, 3, 0, 3))

top_row <- p_annotation + p_heat + plot_layout(widths = c(0.32, 14))
legend_row <- p_legend + plot_spacer() + plot_layout(widths = c(1.9, 12.4))
p_final_heatmap <- top_row / legend_row +
  plot_layout(heights = c(14.4, 1.35)) +
  plot_annotation(title = "C  Feature-gene heatmap",
                  subtitle = paste0(length(heatmap_genes),
                                    " marker genes plotted; representative genes labeled"))

ggsave(file.path(output_dir, "feature_gene_heatmap.png"), p_final_heatmap,
       width = 15, height = 8.9, dpi = 320, bg = "white", device = base_png)
ggsave(file.path(output_dir, "feature_gene_heatmap.pdf"), p_final_heatmap,
       width = 15, height = 8.9, device = cairo_pdf)

missing_violin <- setdiff(violin_genes, rownames(obj))
if (length(missing_violin)) stop("Selected genes absent from object: ", paste(missing_violin, collapse = ", "))
expression <- FetchData(obj, vars = c(violin_genes, "skill_celltype"))
colnames(expression)[ncol(expression)] <- "cell_type"

if (!nzchar(reference_celltype) || !reference_celltype %in% type_order) {
  group_means <- aggregate(expression[violin_genes], list(cell_type = expression$cell_type), mean)
  reference_celltype <- as.character(group_means$cell_type[which.max(rowMeans(group_means[violin_genes]))])
}

statistics <- lapply(violin_genes, function(gene) {
  x <- expression[[gene]][expression$cell_type == reference_celltype]
  y <- expression[[gene]][expression$cell_type != reference_celltype]
  p <- suppressWarnings(wilcox.test(x, y, exact = FALSE)$p.value)
  data.frame(gene = gene, p_value = p)
}) |>
  bind_rows() |>
  mutate(p_adj = p.adjust(p_value, method = "BH"), star = p_to_star(p_adj))
write.csv(statistics, file.path(output_dir, "violin_statistics.csv"), row.names = FALSE)

violin_plots <- lapply(violin_genes, function(gene) {
  dat <- data.frame(expression = expression[[gene]], cell_type = expression$cell_type)
  ymax <- max(dat$expression, na.rm = TRUE)
  ggplot(dat, aes(cell_type, expression, fill = cell_type)) +
    geom_violin(scale = "width", trim = TRUE, linewidth = 0.25, color = "#333333") +
    annotate("text", x = match(reference_celltype, type_order), y = ymax * 1.08 + 0.05,
             label = statistics$star[statistics$gene == gene], fontface = "bold", size = 4) +
    scale_fill_manual(values = palette, drop = FALSE) +
    scale_x_discrete(drop = FALSE) +
    scale_y_continuous(expand = expansion(mult = c(0.02, 0.18))) +
    labs(title = gene, x = NULL, y = "Expression") +
    theme_classic(base_size = 9) +
    theme(legend.position = "none",
          plot.title = element_text(hjust = 0.5, face = "italic"),
          axis.text.x = element_text(angle = 55, hjust = 1, vjust = 1, size = 7))
})

p_final_violin <- wrap_plots(violin_plots, ncol = 2) +
  plot_annotation(title = "D  Selected genes across cell types",
                  subtitle = paste0("Wilcoxon: ", reference_celltype,
                                    " vs all other cells; BH-adjusted"))

ggsave(file.path(output_dir, "selected_gene_violin.png"), p_final_violin,
       width = 13, height = 10, dpi = 320, bg = "white", device = base_png)
ggsave(file.path(output_dir, "selected_gene_violin.pdf"), p_final_violin,
       width = 13, height = 10, device = cairo_pdf)

summary_lines <- c(
  paste0("Seurat input: ", seurat_path),
  paste0("Marker input: ", marker_path),
  paste0("Cells: ", ncol(obj)), paste0("Genes: ", nrow(obj)),
  paste0("Cell types: ", length(type_order)), paste0("Annotation mode: ", mapping_mode),
  paste0("Heatmap marker genes: ", length(heatmap_genes)),
  paste0("Sampled heatmap cells: ", length(sampled_cells)),
  paste0("Violin genes: ", paste(violin_genes, collapse = ",")),
  paste0("Reference cell type: ", reference_celltype),
  paste0("R: ", R.version.string), paste0("Seurat: ", as.character(packageVersion("Seurat")))
)
writeLines(summary_lines, file.path(output_dir, "run_summary.txt"))
message("Completed: ", normalizePath(output_dir, winslash = "/", mustWork = FALSE))
