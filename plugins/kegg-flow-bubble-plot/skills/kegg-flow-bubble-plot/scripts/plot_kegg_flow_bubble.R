#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript plot_kegg_flow_bubble.R <input.tsv> <output_dir> [top_n=6] [max_genes=20] [title] [prefix]")
}

input_file <- args[1]
output_dir <- args[2]
top_n <- if (length(args) >= 3) as.integer(args[3]) else 6L
max_genes <- if (length(args) >= 4) as.integer(args[4]) else 20L
plot_title <- if (length(args) >= 5) args[5] else "KEGG Flow-Bubble Plot"
prefix <- if (length(args) >= 6) args[6] else "kegg_flow_bubble"

if (!file.exists(input_file)) stop("Input file does not exist: ", input_file)
if (!is.finite(top_n) || top_n < 1) stop("top_n must be a positive integer")
if (!is.finite(max_genes) || max_genes < 1) stop("max_genes must be a positive integer")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

raw <- read.delim(input_file, check.names = FALSE, stringsAsFactors = FALSE,
                  quote = "", comment.char = "")
required <- c("Pathway_Name", "IDs", "S", "TS", "Q.value")
missing_cols <- setdiff(required, colnames(raw))
if (length(missing_cols)) stop("Missing required columns: ", paste(missing_cols, collapse = ", "))

dat <- raw %>%
  mutate(Q.value = as.numeric(Q.value), S = as.numeric(S), TS = as.numeric(TS),
         GeneRatio = S / TS,
         neglog10FDR = -log10(pmax(Q.value, .Machine$double.xmin))) %>%
  filter(is.finite(Q.value), is.finite(GeneRatio), S > 0, TS > 0,
         !is.na(Pathway_Name), nzchar(Pathway_Name)) %>%
  arrange(Q.value, desc(GeneRatio)) %>%
  slice_head(n = top_n)
if (!nrow(dat)) stop("No valid pathways remain after filtering")

split_ids <- function(z) {
  z <- trimws(unlist(strsplit(ifelse(is.na(z), "", z), ",", fixed = TRUE)))
  unique(z[nzchar(z)])
}

links_all <- bind_rows(lapply(seq_len(nrow(dat)), function(i) {
  genes <- split_ids(dat$IDs[i])
  if (!length(genes)) return(NULL)
  data.frame(pathway = dat$Pathway_Name[i], gene = genes, stringsAsFactors = FALSE)
}))
if (!nrow(links_all)) stop("Selected pathways contain no parseable gene IDs")

gene_nodes <- links_all %>%
  count(gene, name = "degree") %>%
  arrange(desc(degree), gene) %>%
  slice_head(n = max_genes)
links <- links_all %>% semi_join(gene_nodes, by = "gene")

path_nodes <- dat %>%
  transmute(pathway = Pathway_Name, S, TS, GeneRatio, Q.value, neglog10FDR) %>%
  left_join(links %>% count(pathway, name = "degree"), by = "pathway") %>%
  mutate(degree = ifelse(is.na(degree), 0L, degree))

slot_h <- 0.22
node_gap_gene <- 0.16
node_gap_path <- 0.50
node_w <- 0.032
ribbon_fill <- "grey68"
ribbon_alpha <- 0.42

pack_nodes <- function(tbl, gap) {
  tbl$node_h <- pmax(tbl$degree, 1) * slot_h
  total <- sum(tbl$node_h) + gap * max(0, nrow(tbl) - 1)
  from_top <- cumsum(tbl$node_h + gap) - (tbl$node_h + gap) / 2
  tbl$y <- total - from_top + gap / 2
  tbl$total_h <- total
  tbl
}

gene_nodes <- pack_nodes(gene_nodes, node_gap_gene)
path_nodes <- pack_nodes(path_nodes, node_gap_path)
overall_h <- max(gene_nodes$total_h[1], path_nodes$total_h[1])
gene_nodes$y <- gene_nodes$y + (overall_h - gene_nodes$total_h[1]) / 2
path_nodes$y <- path_nodes$y + (overall_h - path_nodes$total_h[1]) / 2

gene_x <- 0.035
path_x <- 0.785
label_x <- 0.505
panel_left <- 0.825
panel_right <- 1.055

gene_nodes <- gene_nodes %>%
  mutate(node_id = paste0("gene:", gene),
         xmin = gene_x - node_w / 2, xmax = gene_x + node_w / 2,
         ymin = y - node_h / 2, ymax = y + node_h / 2)
path_nodes <- path_nodes %>%
  mutate(node_id = paste0("path:", pathway),
         xmin = path_x - node_w / 2, xmax = path_x + node_w / 2,
         ymin = y - node_h / 2, ymax = y + node_h / 2)

links <- links %>%
  left_join(gene_nodes %>% select(gene, gene_center = y, gene_ymin = ymin), by = "gene") %>%
  left_join(path_nodes %>% select(pathway, path_center = y, path_ymin = ymin), by = "pathway") %>%
  group_by(gene) %>%
  arrange(path_center, .by_group = TRUE) %>%
  mutate(gene_slot = row_number(), gene_y = gene_ymin + (gene_slot - 0.5) * slot_h) %>%
  ungroup() %>%
  group_by(pathway) %>%
  arrange(gene_center, .by_group = TRUE) %>%
  mutate(path_slot = row_number(), path_y = path_ymin + (path_slot - 0.5) * slot_h) %>%
  ungroup() %>%
  mutate(link_id = row_number())

make_ribbon <- function(row, n = 70) {
  t <- seq(0, 1, length.out = n)
  ease <- t^2 * (3 - 2 * t)
  x0 <- gene_x + node_w / 2
  x1 <- path_x - node_w / 2
  xx <- x0 + (x1 - x0) * t
  yy <- row$gene_y + (row$path_y - row$gene_y) * ease
  data.frame(link_id = row$link_id,
             x = c(xx, rev(xx)),
             y = c(yy + slot_h / 2, rev(yy - slot_h / 2)))
}
ribbons <- bind_rows(lapply(seq_len(nrow(links)), function(i) make_ribbon(links[i, ])))

gene_base <- c(
  "#E76F51", "#F4A261", "#E9C46A", "#A7C957", "#70C1B3",
  "#5BC0BE", "#4EA8DE", "#4895EF", "#577590", "#7B6DCC",
  "#9D79BC", "#C77DFF", "#D77FA1", "#F28482", "#84A59D",
  "#43AA8B", "#90BE6D", "#F9C74F", "#F8961E", "#F3722C"
)
gene_values <- if (nrow(gene_nodes) <= length(gene_base)) gene_base[seq_len(nrow(gene_nodes))] else grDevices::colorRampPalette(gene_base)(nrow(gene_nodes))
gene_cols <- setNames(gene_values, gene_nodes$node_id)

path_base <- c("#F05A47", "#FF9F35", "#9B78C6", "#9A7660",
               "#3F8FC1", "#55B85A", "#D65DB1", "#6F8FAF")
path_values <- if (nrow(path_nodes) <= length(path_base)) path_base[seq_len(nrow(path_nodes))] else grDevices::colorRampPalette(path_base)(nrow(path_nodes))
path_cols <- setNames(path_values, path_nodes$node_id)
node_cols <- c(gene_cols, path_cols)

ratio_range <- range(path_nodes$GeneRatio)
if (diff(ratio_range) == 0) ratio_range <- ratio_range + c(-0.001, 0.001)
path_nodes <- path_nodes %>%
  mutate(bubble_x = rescale(GeneRatio, c(panel_left + 0.026, panel_right - 0.026), from = ratio_range))

ticks <- pretty(ratio_range, n = 4)
ticks <- ticks[ticks >= ratio_range[1] & ticks <= ratio_range[2]]
if (length(ticks) < 2) ticks <- ratio_range
tick_df <- data.frame(ratio = ticks,
                      x = rescale(ticks, c(panel_left + 0.026, panel_right - 0.026), from = ratio_range))
panel_bottom <- min(path_nodes$ymin) - 0.30
panel_top <- max(path_nodes$ymax) + 0.30
plot_bottom <- panel_bottom - 0.82

p <- ggplot() +
  geom_polygon(data = ribbons, aes(x = x, y = y, group = link_id),
               fill = ribbon_fill, colour = NA, alpha = ribbon_alpha) +
  geom_rect(data = gene_nodes, aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax, fill = node_id), colour = NA) +
  geom_text(data = gene_nodes, aes(x = xmin - 0.010, y = y, label = gene),
            hjust = 1, size = 3.18, fontface = "plain", colour = "grey10") +
  geom_rect(data = path_nodes, aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax, fill = node_id), colour = NA) +
  geom_text(data = path_nodes, aes(x = label_x, y = y, label = pathway),
            size = 3.22, fontface = "bold", colour = "grey10", lineheight = 0.96) +
  geom_rect(aes(xmin = panel_left, xmax = panel_right, ymin = panel_bottom, ymax = panel_top),
            fill = NA, colour = "black", linewidth = 0.60) +
  geom_segment(data = tick_df, aes(x = x, xend = x, y = panel_bottom, yend = panel_bottom - 0.09),
               colour = "black", linewidth = 0.4) +
  geom_text(data = tick_df, aes(x = x, y = panel_bottom - 0.25, label = sprintf("%.3f", ratio)),
            size = 2.42, colour = "grey10", angle = -32, hjust = 0.25) +
  geom_point(data = path_nodes, aes(x = bubble_x, y = y, size = S, colour = neglog10FDR), shape = 16, alpha = 0.98) +
  geom_point(data = path_nodes, aes(x = bubble_x, y = y, size = S),
             shape = 21, fill = NA, colour = "black", stroke = 0.55, show.legend = FALSE) +
  annotate("text", x = (panel_left + panel_right) / 2,
           y = panel_bottom - 0.66, label = "Gene.Ratio", size = 2.75) +
  scale_fill_manual(values = node_cols, guide = "none") +
  scale_colour_gradientn(colours = c("#4B1D8A", "#8A3F9D", "#D05A8D", "#F48A64", "#FFD166"),
                         name = expression(-log[10](FDR))) +
  scale_size_continuous(name = "Count", range = c(3.8, 7.5)) +
  guides(colour = guide_colourbar(order = 1, barheight = grid::unit(2.2, "cm"), barwidth = grid::unit(0.38, "cm")),
         size = guide_legend(order = 2, override.aes = list(colour = "black"))) +
  coord_cartesian(xlim = c(-0.115, panel_right + 0.006),
                  ylim = c(plot_bottom, overall_h + 0.28), clip = "off") +
  labs(title = plot_title, subtitle = paste0("Top ", nrow(path_nodes), " KEGG pathways by FDR")) +
  theme_void(base_size = 11) +
  theme(plot.title = element_text(hjust = 0.5, face = "bold", size = 16),
        plot.subtitle = element_text(hjust = 0.5, colour = "grey40", size = 10),
        legend.position = "right", legend.box = "vertical",
        legend.spacing.y = grid::unit(0.12, "cm"),
        legend.margin = margin(l = -10, r = 0),
        legend.box.margin = margin(0, 0, 0, -8),
        legend.title = element_text(size = 9), legend.text = element_text(size = 8),
        plot.margin = margin(12, 0, 14, 30))

png_file <- file.path(output_dir, paste0(prefix, ".png"))
pdf_file <- file.path(output_dir, paste0(prefix, ".pdf"))
ggsave(png_file, p, width = 11.45, height = 8.15, dpi = 300, bg = "white")
pdf_device <- if (capabilities("cairo")) grDevices::cairo_pdf else grDevices::pdf
ggsave(pdf_file, p, width = 11.45, height = 8.15, device = pdf_device, bg = "white")

write.csv(path_nodes %>% select(pathway, degree, node_h, S, TS, GeneRatio, Q.value, neglog10FDR),
          file.path(output_dir, paste0(prefix, "_selected_pathways.csv")), row.names = FALSE)
write.csv(gene_nodes %>% select(gene, degree, node_h),
          file.path(output_dir, paste0(prefix, "_gene_nodes.csv")), row.names = FALSE)
write.csv(links %>% select(gene, pathway, gene_slot, path_slot, gene_y, path_y),
          file.path(output_dir, paste0(prefix, "_link_slots.csv")), row.names = FALSE)

parameters <- c(
  paste0("input=", normalizePath(input_file, winslash = "/", mustWork = FALSE)),
  paste0("title=", plot_title), paste0("top_n=", top_n), paste0("max_genes=", max_genes),
  paste0("selected_pathways=", nrow(path_nodes)), paste0("displayed_genes=", nrow(gene_nodes)),
  paste0("displayed_links=", nrow(links)), paste0("slot_h=", slot_h), paste0("node_w=", node_w),
  paste0("ribbon_fill=", ribbon_fill), paste0("ribbon_alpha=", ribbon_alpha),
  "width_in=11.45", "height_in=8.15", "dpi=300", paste0("R=", R.version.string),
  paste0("ggplot2=", as.character(packageVersion("ggplot2"))),
  paste0("dplyr=", as.character(packageVersion("dplyr"))),
  paste0("scales=", as.character(packageVersion("scales")))
)
writeLines(parameters, file.path(output_dir, paste0(prefix, "_parameters.txt")), useBytes = TRUE)

cat("KEGG Flow-Bubble Plot completed\n")
cat("PNG:", png_file, "\nPDF:", pdf_file, "\n")
cat("Pathways:", nrow(path_nodes), "Genes:", nrow(gene_nodes), "Links:", nrow(links), "\n")
