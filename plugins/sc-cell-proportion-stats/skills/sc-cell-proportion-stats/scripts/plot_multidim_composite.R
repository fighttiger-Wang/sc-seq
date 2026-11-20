#!/usr/bin/env Rscript
# ==============================================================================
# Script: plot_multidim_composite.R
# Skill: 23-单细胞细胞比例统计与显著性分析
# Description: Multi-Dimensional Cell Proportion Composite Visualization.
#   Implements Cancer Cell / Nature style three-panel composite architecture:
#     - Top: Stacked barplot of cell counts across samples/groups
#     - Center: Dotplot of cell proportion (size = proportion, color = cell type)
#     - Right: Horizontal barplot of total cell counts per cell type
#   Assembled with aplot into a cohesive publication figure.
# ==============================================================================

suppressPackageStartupMessages({
  library(optparse)
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(aplot)
  library(RColorBrewer)
})

option_list <- list(
  make_option(c("-i", "--input"), type = "character", default = NULL,
              help = "Path to metadata RDS or annotated dataframe [required]", metavar = "file"),
  make_option(c("-o", "--output"), type = "character", default = "./cell_proportion_analysis/plots",
              help = "Output directory for plots [default: %default]", metavar = "dir"),
  make_option(c("-c", "--celltype_col"), type = "character", default = "cell_type_fine",
              help = "Metadata column name for cell types [default: %default]"),
  make_option(c("-p", "--prefix"), type = "character", default = "Fine",
              help = "Prefix for output plot files [default: %default]"),
  make_option(c("-g", "--group_order"), type = "character", default = NULL,
              help = "Comma-separated group ordering"),
  make_option(c("-s", "--sample_order"), type = "character", default = NULL,
              help = "Comma-separated sample ordering")
)

opt_parser <- OptionParser(option_list = option_list)
opt <- parse_args(opt_parser)

if (is.null(opt$input)) {
  print_help(opt_parser)
  stop("Missing required argument: --input", call. = FALSE)
}

dir.create(opt$output, recursive = TRUE, showWarnings = FALSE)

cat("[1/4] Loading metadata from:", opt$input, "\n")
meta <- readRDS(opt$input)

type_col <- opt$celltype_col
if (!type_col %in% colnames(meta)) {
  stop("Column '", type_col, "' not found in metadata.")
}

if (!is.null(opt$group_order)) {
  group_order <- strsplit(opt$group_order, ",")[[1]]
} else {
  group_order <- unique(meta$group[!is.na(meta$group)])
}

if (!is.null(opt$sample_order)) {
  sample_order <- strsplit(opt$sample_order, ",")[[1]]
} else {
  sample_order <- unique(meta$sample[!is.na(meta$sample)])
}

nature_palette <- c(
  "#915aa5", "#eede82", "#FFA500", "#0c4f8c", "#4b86c5",
  "#6dccdc", "#ee7723", "#f37f72", "#90c73d", "#146533",
  "#6ac6a8", "#d95f02", "#7570b3", "#e7298a", "#66a61e"
)

df_sub <- meta[!is.na(meta[[type_col]]) & !is.na(meta$group), ]

# Order cell types by total cell count
celltype_order <- df_sub %>%
  group_by(cell_class = .data[[type_col]]) %>%
  summarise(total_n = n(), .groups = "drop") %>%
  arrange(total_n) %>%
  pull(cell_class)

n_types <- length(celltype_order)
colors_to_use <- rep(nature_palette, length.out = n_types)
names(colors_to_use) <- celltype_order

# ------------------------------------------------------------------------------
# 1. GROUP-LEVEL COMPOSITE PLOT
# ------------------------------------------------------------------------------
cat("[2/4] Generating Group-level Composite Plot...\n")

df_group <- df_sub %>%
  group_by(group, cell_class = .data[[type_col]]) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(group) %>%
  mutate(percentage = n / sum(n)) %>%
  ungroup()

df_group$group <- factor(df_group$group, levels = group_order)
df_group$cell_class <- factor(df_group$cell_class, levels = celltype_order)

celltype_sum <- df_sub %>%
  group_by(cell_class = .data[[type_col]]) %>%
  summarise(total_n = n(), .groups = "drop")
celltype_sum$cell_class <- factor(celltype_sum$cell_class, levels = celltype_order)

# Center Dot Plot
p_dot_grp <- ggplot(df_group, aes(x = group, y = cell_class, size = percentage, color = cell_class)) +
  geom_point(alpha = 0.85) +
  scale_size_continuous(
    range = c(2.5, 11),
    breaks = c(0.01, 0.05, 0.10, 0.25, 0.50, 0.75),
    labels = function(x) paste0(x * 100, "%"),
    name = "Cell proportion"
  ) +
  scale_color_manual(values = colors_to_use, name = "Cell type") +
  theme_classic(base_size = 12) +
  theme(
    axis.text.x = element_text(face = "bold", color = "black", size = 11),
    axis.text.y = element_text(face = "bold", color = "black", size = 11),
    axis.title = element_blank(),
    panel.grid.major = element_line(color = "#F0F0F0", linewidth = 0.5),
    legend.position = "right"
  )

# Top Stacked Barplot
p_top_grp <- ggplot(df_group, aes(x = group, y = n, fill = cell_class)) +
  geom_bar(stat = "identity", position = "stack", width = 0.65, alpha = 0.9) +
  scale_fill_manual(values = colors_to_use, guide = "none") +
  scale_y_continuous(labels = label_comma(), expand = expansion(mult = c(0, 0.05))) +
  labs(y = "Number of cells") +
  theme_classic(base_size = 11) +
  theme(
    axis.title.x = element_blank(),
    axis.text.x = element_blank(),
    axis.ticks.x = element_blank(),
    axis.line.x = element_blank(),
    axis.title.y = element_text(face = "bold", size = 10),
    axis.text.y = element_text(color = "black", size = 9)
  )

# Right Horizontal Barplot
p_right_grp <- ggplot(celltype_sum, aes(x = cell_class, y = total_n, fill = cell_class)) +
  geom_bar(stat = "identity", width = 0.65, alpha = 0.9) +
  scale_fill_manual(values = colors_to_use, guide = "none") +
  scale_y_continuous(labels = label_comma(), expand = expansion(mult = c(0, 0.1))) +
  labs(y = "Number of cells") +
  coord_flip() +
  theme_classic(base_size = 11) +
  theme(
    axis.title.y = element_blank(),
    axis.text.y = element_blank(),
    axis.ticks.y = element_blank(),
    axis.line.y = element_blank(),
    axis.title.x = element_text(face = "bold", size = 10),
    axis.text.x = element_text(color = "black", size = 9)
  )

# Assemble
p_comp_grp <- p_dot_grp %>%
  insert_top(p_top_grp, height = 0.35) %>%
  insert_right(p_right_grp, width = 0.35)

pdf_grp <- file.path(opt$output, paste0("Cell_Proportion_", opt$prefix, "_multidim_composite_by_group.pdf"))
png_grp <- file.path(opt$output, paste0("Cell_Proportion_", opt$prefix, "_multidim_composite_by_group.png"))
ggsave(pdf_grp, p_comp_grp, width = 9.5, height = 8.5)
ggsave(png_grp, p_comp_grp, width = 9.5, height = 8.5, dpi = 300)
cat("Group-level composite plot saved:\n  -", pdf_grp, "\n  -", png_grp, "\n")

# ------------------------------------------------------------------------------
# 2. SAMPLE-LEVEL COMPOSITE PLOT
# ------------------------------------------------------------------------------
cat("[3/4] Generating Sample-level Composite Plot...\n")

df_sample <- df_sub %>%
  group_by(sample, cell_class = .data[[type_col]]) %>%
  summarise(n = n(), .groups = "drop") %>%
  group_by(sample) %>%
  mutate(percentage = n / sum(n)) %>%
  ungroup()

df_sample$sample <- factor(df_sample$sample, levels = sample_order)
df_sample$cell_class <- factor(df_sample$cell_class, levels = celltype_order)

p_dot_smp <- ggplot(df_sample, aes(x = sample, y = cell_class, size = percentage, color = cell_class)) +
  geom_point(alpha = 0.85) +
  scale_size_continuous(
    range = c(2, 9),
    breaks = c(0.01, 0.05, 0.10, 0.25, 0.50, 0.75),
    labels = function(x) paste0(x * 100, "%"),
    name = "Cell proportion"
  ) +
  scale_color_manual(values = colors_to_use, name = "Cell type") +
  theme_classic(base_size = 12) +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, face = "bold", color = "black", size = 10),
    axis.text.y = element_text(face = "bold", color = "black", size = 11),
    axis.title = element_blank(),
    panel.grid.major = element_line(color = "#F0F0F0", linewidth = 0.5),
    legend.position = "right"
  )

p_top_smp <- ggplot(df_sample, aes(x = sample, y = n, fill = cell_class)) +
  geom_bar(stat = "identity", position = "stack", width = 0.65, alpha = 0.9) +
  scale_fill_manual(values = colors_to_use, guide = "none") +
  scale_y_continuous(labels = label_comma(), expand = expansion(mult = c(0, 0.05))) +
  labs(y = "Number of cells") +
  theme_classic(base_size = 11) +
  theme(
    axis.title.x = element_blank(),
    axis.text.x = element_blank(),
    axis.ticks.x = element_blank(),
    axis.line.x = element_blank(),
    axis.title.y = element_text(face = "bold", size = 10),
    axis.text.y = element_text(color = "black", size = 9)
  )

p_comp_smp <- p_dot_smp %>%
  insert_top(p_top_smp, height = 0.35) %>%
  insert_right(p_right_grp, width = 0.35)

pdf_smp <- file.path(opt$output, paste0("Cell_Proportion_", opt$prefix, "_multidim_composite_by_sample.pdf"))
png_smp <- file.path(opt$output, paste0("Cell_Proportion_", opt$prefix, "_multidim_composite_by_sample.png"))
ggsave(pdf_smp, p_comp_smp, width = 12.0, height = 8.5)
ggsave(png_smp, p_comp_smp, width = 12.0, height = 8.5, dpi = 300)
cat("Sample-level composite plot saved:\n  -", pdf_smp, "\n  -", png_smp, "\n")

cat("[4/4] Multi-dimensional composite pipeline completed successfully!\n")
