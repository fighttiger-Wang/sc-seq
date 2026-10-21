#!/usr/bin/env Rscript
# ==============================================================================
# 17 · 单细胞分组基因表达气泡图与统计分析
# Core implementation: draw_group_gene_bubble_stats.R
# ==============================================================================

suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tidyr)
  library(scales)
  library(patchwork)
  library(openxlsx)
})

# Split comma/semicolon/newline separated string cleanly
clean_split <- function(x) {
  if (is.null(x) || length(x) == 0) return(character(0))
  items <- unlist(strsplit(as.character(x), split = "[,;\n\r\t]+"))
  items <- trimws(items)
  items[nzchar(items)]
}

# Parse command line arguments
parse_args <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  params <- list(
    input = NULL,
    genes = "Cxcl13",
    output = "./output",
    groups = NULL,           # e.g. "Middle_aged_Con,Middle_aged_Fru"
    celltypes = NULL,        # e.g. "Spp1_Mic,Ifit3_Mic,..."
    colors = "#4B87B9,#E15759", # Con (Blue), Fru (Red)
    yaml_config = NULL,
    title = NULL
  )
  
  i <- 1
  while (i <= length(args)) {
    arg <- args[i]
    if (arg %in% c("-i", "--input")) {
      params$input <- args[i + 1]
      i <- i + 2
    } else if (arg %in% c("-g", "--genes")) {
      params$genes <- args[i + 1]
      i <- i + 2
    } else if (arg %in% c("-o", "--output")) {
      params$output <- args[i + 1]
      i <- i + 2
    } else if (arg %in% c("--groups")) {
      params$groups <- args[i + 1]
      i <- i + 2
    } else if (arg %in% c("--celltypes")) {
      params$celltypes <- args[i + 1]
      i <- i + 2
    } else if (arg %in% c("--colors")) {
      params$colors <- args[i + 1]
      i <- i + 2
    } else if (arg %in% c("-c", "--config")) {
      params$yaml_config <- args[i + 1]
      i <- i + 2
    } else if (arg %in% c("-t", "--title")) {
      params$title <- args[i + 1]
      i <- i + 2
    } else {
      if (is.null(params$input) && !startsWith(arg, "-")) {
        params$input <- arg
      }
      i <- i + 1
    }
  }
  
  # If YAML config provided, load YAML
  if (!is.null(params$yaml_config) && file.exists(params$yaml_config)) {
    if (requireNamespace("yaml", quietly = TRUE)) {
      ycfg <- yaml::read_yaml(params$yaml_config)
      for (k in names(ycfg)) {
        params[[k]] <- ycfg[[k]]
      }
    }
  }
  
  return(params)
}

# Main execution
run_pipeline <- function(params) {
  if (is.null(params$input) || !file.exists(params$input)) {
    stop("Input file/folder does not exist: ", params$input)
  }
  
  dir.create(params$output, recursive = TRUE, showWarnings = FALSE)
  out_dir <- normalizePath(params$output, mustWork = FALSE)
  
  # Parse genes
  if (is.character(params$genes) && length(params$genes) == 1) {
    if (file.exists(params$genes)) {
      gene_list <- clean_split(readLines(params$genes))
    } else {
      gene_list <- clean_split(params$genes)
    }
  } else {
    gene_list <- unlist(lapply(params$genes, clean_split))
  }
  gene_list <- gene_list[nzchar(gene_list)]
  
  cat("Target genes (", length(gene_list), "):", paste(gene_list, collapse = ", "), "\n")
  cat("Input path:", params$input, "\n")
  cat("Output path:", out_dir, "\n")
  
  # Load data: support ZIP, folder, or table file
  is_zip <- grepl("\\.zip$", params$input, ignore.case = TRUE)
  
  df_sample_raw <- NULL
  df_group_raw <- NULL
  
  if (is_zip) {
    file_list <- unzip(params$input, list = TRUE)$Name
    
    # 1. Look for sample level table
    cs_entry <- grep("Celltype_Sample/avg_expr_result\\.txt$", file_list, value = TRUE)
    if (length(cs_entry) == 0) {
      cs_entry <- grep("cluster_sample/avg_expr_result\\.txt$", file_list, value = TRUE)
    }
    if (length(cs_entry) > 0) {
      con <- unz(params$input, cs_entry[1])
      df_sample_raw <- read.table(con, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE)
    }
    
    # 2. Look for group level table
    cg_entry <- grep("Celltype_Group/avg_expr_result\\.txt$", file_list, value = TRUE)
    if (length(cg_entry) == 0) {
      cg_entry <- grep("Cluster_Group/avg_expr_result\\.txt$", file_list, value = TRUE)
    }
    if (length(cg_entry) > 0) {
      con <- unz(params$input, cg_entry[1])
      df_group_raw <- read.table(con, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE)
    }
  } else if (dir.exists(params$input)) {
    cs_file <- file.path(params$input, "Celltype_Sample", "avg_expr_result.txt")
    if (file.exists(cs_file)) {
      df_sample_raw <- read.table(cs_file, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE)
    }
    cg_file <- file.path(params$input, "Celltype_Group", "avg_expr_result.txt")
    if (file.exists(cg_file)) {
      df_group_raw <- read.table(cg_file, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE)
    }
  } else {
    df_raw <- read.table(params$input, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE)
    df_sample_raw <- df_raw
  }
  
  if (is.null(df_sample_raw) && is.null(df_group_raw)) {
    stop("Could not locate avg_expr_result.txt (sample or group level) in: ", params$input)
  }
  
  # Normalize column names in tables
  norm_cols <- function(df) {
    cn <- tolower(colnames(df))
    colnames(df)[cn %in% c("gene", "symbol", "genes")] <- "gene"
    colnames(df)[cn %in% c("group", "cluster", "celltype", "subcluster", "ident")] <- "group"
    colnames(df)[cn %in% c("norm_expr", "avg_expr", "expression", "mean_norm_expr")] <- "norm_expr"
    colnames(df)[cn %in% c("mean_expr", "raw_mean_expr", "avg_raw_expr")] <- "mean_expr"
    colnames(df)[cn %in% c("expr_ratio", "pct.exp", "pct_exp", "ratio", "percentage")] <- "expr_ratio"
    
    if (!"norm_expr" %in% colnames(df) && "mean_expr" %in% colnames(df)) {
      df$norm_expr <- df$mean_expr
    }
    if (!"mean_expr" %in% colnames(df) && "norm_expr" %in% colnames(df)) {
      df$mean_expr <- df$norm_expr
    }
    if (!"expr_ratio" %in% colnames(df)) {
      df$expr_ratio <- 1.0
    }
    return(df)
  }
  
  if (!is.null(df_sample_raw)) df_sample_raw <- norm_cols(df_sample_raw)
  if (!is.null(df_group_raw)) df_group_raw <- norm_cols(df_group_raw)
  
  # Filter for target genes (case-insensitive match)
  match_genes <- function(df, target_genes) {
    df_genes_lower <- tolower(df$gene)
    targets_lower <- tolower(target_genes)
    df_matched <- df %>% filter(df_genes_lower %in% targets_lower)
    matched_map <- setNames(target_genes, targets_lower)
    df_matched$gene <- matched_map[tolower(df_matched$gene)]
    return(df_matched)
  }
  
  # Parse group strings into celltype, sample, condition
  parse_group_str <- function(df, is_sample_level = TRUE) {
    if ("celltype" %in% colnames(df) && "group_name" %in% colnames(df)) {
      return(df)
    }
    
    groups <- df$group
    if (is_sample_level) {
      celltype <- sub("_(LC_14m_.*|[A-Za-z0-9]+_[0-9]+|rep[0-9]+|[Cc]on[0-9]+|[Ff]ru[0-9]+|[Tt]reat[0-9]+|[Ss]ample[0-9]+)$", "", groups)
      sample <- sub("^.*_(LC_14m_.*|[A-Za-z0-9]+_[0-9]+|rep[0-9]+|[Cc]on[0-9]+|[Ff]ru[0-9]+|[Tt]reat[0-9]+|[Ss]ample[0-9]+)$", "\\1", groups)
      condition <- ifelse(grepl("fru|treat|ko|disease|tumor|model|case", sample, ignore.case = TRUE), 
                          "Treated", "Control")
      if (any(grepl("fru", groups, ignore.case = TRUE)) && any(grepl("con", groups, ignore.case = TRUE))) {
        condition <- ifelse(grepl("fru", groups, ignore.case = TRUE), "Middle_aged_Fru", "Middle_aged_Con")
      }
      df$celltype <- celltype
      df$sample <- sample
      df$group_name <- condition
    } else {
      if (any(grepl("Middle_aged_Fru|Middle_aged_Con", groups))) {
        df$celltype <- sub("_(Middle_aged_.*)$", "", groups)
        df$group_name <- sub("^.*_(Middle_aged_.*)$", "\\1", groups)
      } else {
        parts <- strsplit(groups, "_")
        df$celltype <- sapply(parts, function(x) paste(head(x, -1), collapse = "_"))
        df$group_name <- sapply(parts, function(x) tail(x, 1))
      }
    }
    return(df)
  }
  
  if (!is.null(df_sample_raw)) {
    df_sample_filt <- match_genes(df_sample_raw, gene_list)
    df_sample_parsed <- parse_group_str(df_sample_filt, is_sample_level = TRUE)
  } else {
    df_sample_parsed <- NULL
  }
  
  if (!is.null(df_group_raw)) {
    df_group_filt <- match_genes(df_group_raw, gene_list)
    df_group_parsed <- parse_group_str(df_group_filt, is_sample_level = FALSE)
  } else {
    df_group_parsed <- df_sample_parsed %>%
      group_by(gene, celltype, group_name) %>%
      summarise(
        norm_expr = mean(norm_expr),
        mean_expr = mean(mean_expr),
        expr_ratio = mean(expr_ratio),
        .groups = "drop"
      )
  }
  
  # Determine groups
  detected_groups <- unique(df_group_parsed$group_name)
  if (!is.null(params$groups)) {
    group_vec <- clean_split(params$groups)
  } else {
    con_idx <- grep("con|ctrl|wt|normal|mock", detected_groups, ignore.case = TRUE)
    if (length(con_idx) > 0) {
      ref_g <- detected_groups[con_idx[1]]
      other_g <- setdiff(detected_groups, ref_g)
      group_vec <- c(ref_g, other_g)
    } else {
      group_vec <- sort(detected_groups)
    }
  }
  
  # Determine celltypes
  detected_celltypes <- unique(df_group_parsed$celltype)
  detected_celltypes <- detected_celltypes[!tolower(detected_celltypes) %in% c("other", "unassigned", "unknown")]
  
  if (!is.null(params$celltypes)) {
    celltype_vec <- clean_split(params$celltypes)
    celltype_vec <- celltype_vec[celltype_vec %in% unique(df_group_parsed$celltype)]
  } else {
    celltype_vec <- detected_celltypes
  }
  
  cat("Active groups (", length(group_vec), "):", paste(group_vec, collapse = ", "), "\n")
  cat("Active celltypes (", length(celltype_vec), "):", paste(celltype_vec, collapse = ", "), "\n")
  
  # Filter & factorize datasets
  df_group_final <- df_group_parsed %>%
    filter(celltype %in% celltype_vec, group_name %in% group_vec) %>%
    mutate(
      celltype = factor(celltype, levels = celltype_vec),
      group_name = factor(group_name, levels = group_vec),
      expr_percent = expr_ratio * 100
    )
  
  if (!is.null(df_sample_parsed)) {
    df_sample_final <- df_sample_parsed %>%
      filter(celltype %in% celltype_vec, group_name %in% group_vec) %>%
      mutate(
        celltype = factor(celltype, levels = celltype_vec),
        group_name = factor(group_name, levels = group_vec),
        expr_percent = expr_ratio * 100
      )
  } else {
    df_sample_final <- NULL
  }
  
  # Colors
  color_vec <- clean_split(params$colors)
  if (length(color_vec) < length(group_vec)) {
    color_vec <- scales::hue_pal()(length(group_vec))
  }
  names(color_vec) <- group_vec
  
  # ============================================================================
  # Statistical Analysis & Workbook Generation
  # ============================================================================
  cat("Calculating statistics and generating Excel workbook...\n")
  
  if (!is.null(df_sample_final)) {
    summary_stats <- df_sample_final %>%
      group_by(gene, celltype, group_name) %>%
      summarise(
        n = n(),
        mean_norm = mean(norm_expr),
        sd_norm = sd(norm_expr),
        sem_norm = ifelse(n() > 1, sd(norm_expr) / sqrt(n()), 0),
        mean_ratio_pct = mean(expr_percent),
        sd_ratio_pct = sd(expr_percent),
        sem_ratio_pct = ifelse(n() > 1, sd(expr_percent) / sqrt(n()), 0),
        .groups = "drop"
      )
    
    if (length(group_vec) >= 2) {
      g1 <- group_vec[1]
      g2 <- group_vec[2]
      
      stat_list <- list()
      for (gn in unique(df_sample_final$gene)) {
        for (ct in celltype_vec) {
          sub_d <- df_sample_final %>% filter(gene == gn, celltype == ct)
          vals_g1 <- sub_d %>% filter(group_name == g1) %>% pull(norm_expr)
          vals_g2 <- sub_d %>% filter(group_name == g2) %>% pull(norm_expr)
          r_g1 <- sub_d %>% filter(group_name == g1) %>% pull(expr_percent)
          r_g2 <- sub_d %>% filter(group_name == g2) %>% pull(expr_percent)
          
          p_t_eq <- NA_real_
          p_t_welch <- NA_real_
          p_wilcox <- NA_real_
          p_ratio_t <- NA_real_
          
          if (length(vals_g1) >= 2 && length(vals_g2) >= 2) {
            if (sd(vals_g1) > 0 || sd(vals_g2) > 0) {
              p_t_eq <- tryCatch(t.test(vals_g2, vals_g1, var.equal = TRUE)$p.value, error = function(e) NA_real_)
              p_t_welch <- tryCatch(t.test(vals_g2, vals_g1, var.equal = FALSE)$p.value, error = function(e) NA_real_)
              p_wilcox <- tryCatch(wilcox.test(vals_g2, vals_g1)$p.value, error = function(e) NA_real_)
            } else if (all(vals_g1 == vals_g2)) {
              p_t_eq <- 1.0
              p_t_welch <- 1.0
              p_wilcox <- 1.0
            }
          }
          if (length(r_g1) >= 2 && length(r_g2) >= 2) {
            if (sd(r_g1) > 0 || sd(r_g2) > 0) {
              p_ratio_t <- tryCatch(t.test(r_g2, r_g1, var.equal = TRUE)$p.value, error = function(e) NA_real_)
            } else if (all(r_g1 == r_g2)) {
              p_ratio_t <- 1.0
            }
          }
          
          m1 <- mean(vals_g1)
          m2 <- mean(vals_g2)
          diff_m <- m2 - m1
          fc <- (m2 + 0.0001) / (m1 + 0.0001)
          log2fc <- log2(fc)
          
          sig_mark <- ifelse(is.na(p_t_eq), "ns",
                      ifelse(p_t_eq < 0.001, "***",
                      ifelse(p_t_eq < 0.01, "**",
                      ifelse(p_t_eq < 0.05, "*", "ns"))))
          
          sig_ratio <- ifelse(is.na(p_ratio_t), "ns",
                       ifelse(p_ratio_t < 0.001, "***",
                       ifelse(p_ratio_t < 0.01, "**",
                       ifelse(p_ratio_t < 0.05, "*", "ns"))))
          
          stat_list[[length(stat_list) + 1]] <- data.frame(
            Gene = gn,
            CellType = ct,
            Reference_Group = g1,
            Comparison_Group = g2,
            Ref_Mean_Norm = m1,
            Ref_SEM_Norm = ifelse(length(vals_g1) > 1, sd(vals_g1) / sqrt(length(vals_g1)), 0),
            Ref_SD_Norm = ifelse(length(vals_g1) > 1, sd(vals_g1), 0),
            Ref_N = length(vals_g1),
            Comp_Mean_Norm = m2,
            Comp_SEM_Norm = ifelse(length(vals_g2) > 1, sd(vals_g2) / sqrt(length(vals_g2)), 0),
            Comp_SD_Norm = ifelse(length(vals_g2) > 1, sd(vals_g2), 0),
            Comp_N = length(vals_g2),
            Diff_Mean_Norm = diff_m,
            Fold_Change = fc,
            Log2_FC = log2fc,
            P_val_t_test_equal = p_t_eq,
            P_val_t_test_welch = p_t_welch,
            P_val_Wilcoxon = p_wilcox,
            Significance_Expr = sig_mark,
            Ref_Ratio_Pct_Mean = mean(r_g1),
            Ref_Ratio_Pct_SEM = ifelse(length(r_g1) > 1, sd(r_g1) / sqrt(length(r_g1)), 0),
            Comp_Ratio_Pct_Mean = mean(r_g2),
            Comp_Ratio_Pct_SEM = ifelse(length(r_g2) > 1, sd(r_g2) / sqrt(length(r_g2)), 0),
            P_val_ratio_t_test = p_ratio_t,
            Significance_Ratio = sig_ratio,
            stringsAsFactors = FALSE
          )
        }
      }
      stats_summary_table <- bind_rows(stat_list)
    } else {
      stats_summary_table <- summary_stats
    }
  } else {
    summary_stats <- df_group_final %>%
      rename(mean_norm = norm_expr, mean_ratio_pct = expr_percent) %>%
      mutate(sem_norm = 0, sd_norm = 0, sem_ratio_pct = 0, sd_ratio_pct = 0, n = 1)
    stats_summary_table <- df_group_final
  }
  
  wb <- createWorkbook()
  header_style <- createStyle(
    fontColour = "#FFFFFF",
    fgFill = "#1F4E79",
    halign = "center",
    valign = "center",
    textDecoration = "bold",
    border = "TopBottomLeftRight"
  )
  
  addWorksheet(wb, "亚群统计汇总表")
  writeData(wb, "亚群统计汇总表", stats_summary_table, headerStyle = header_style)
  setColWidths(wb, "亚群统计汇总表", cols = 1:ncol(stats_summary_table), widths = "auto")
  
  if (!is.null(df_sample_final)) {
    addWorksheet(wb, "样本水平表达明细")
    writeData(wb, "样本水平表达明细", df_sample_final %>% select(gene, celltype, sample, group_name, norm_expr, mean_expr, expr_ratio, expr_percent), headerStyle = header_style)
    setColWidths(wb, "样本水平表达明细", cols = 1:8, widths = "auto")
  }
  
  addWorksheet(wb, "亚群分组聚合总表")
  writeData(wb, "亚群分组聚合总表", df_group_final %>% select(gene, celltype, group_name, norm_expr, mean_expr, expr_ratio, expr_percent), headerStyle = header_style)
  setColWidths(wb, "亚群分组聚合总表", cols = 1:7, widths = "auto")
  
  excel_file <- file.path(out_dir, "group_gene_statistical_summary.xlsx")
  saveWorkbook(wb, excel_file, overwrite = TRUE)
  cat("Saved Excel workbook:", excel_file, "\n")
  
  tsv_file <- file.path(out_dir, "group_gene_statistical_summary.tsv")
  write.table(stats_summary_table, tsv_file, sep = "\t", row.names = FALSE, quote = FALSE)
  
  # ============================================================================
  # Publication-Ready Visualizations
  # ============================================================================
  cat("Generating publication-ready figures...\n")
  
  theme_pub <- theme_classic(base_size = 12) +
    theme(
      axis.text = element_text(color = "black", size = 11),
      axis.title = element_text(face = "bold", color = "black", size = 12),
      legend.title = element_text(face = "bold", size = 11),
      legend.text = element_text(size = 10.5),
      plot.title = element_text(face = "bold", hjust = 0.5, size = 13.5),
      plot.subtitle = element_text(hjust = 0.5, size = 10.5, color = "grey35"),
      axis.text.x = element_text(angle = 35, hjust = 1, vjust = 1, face = "bold"),
      panel.grid.major.y = element_line(color = "grey92", linetype = "dashed")
    )
  
  single_gene <- length(gene_list) == 1
  cur_gene <- gene_list[1]
  
  # -------------------------------------------------------------
  # PLOT 1: Group Split DotPlot (组间分面/并列气泡图)
  # -------------------------------------------------------------
  max_expr <- max(df_group_final$norm_expr, na.rm = TRUE)
  max_pct <- max(df_group_final$expr_percent, na.rm = TRUE)
  
  p_dotplot <- ggplot(df_group_final, aes(x = celltype, y = group_name)) +
    geom_point(aes(size = expr_percent, color = norm_expr)) +
    scale_size_continuous(
      name = "Percent Expressed (%)",
      range = c(2.5, 10),
      limits = c(0, max(max_pct * 1.1, 10))
    ) +
    scale_color_gradientn(
      name = "Average Expression",
      colors = c("#3B4CC0", "#8CBDFF", "#F2F2F2", "#F49A7B", "#B40426"),
      limits = c(0, max(max_expr * 1.05, 1.0))
    ) +
    labs(
      title = ifelse(!is.null(params$title), params$title, paste0(cur_gene, " DotPlot Across Subclusters by Group")),
      x = "Cell Subcluster",
      y = "Group"
    ) +
    theme_bw(base_size = 12) +
    theme(
      axis.text = element_text(color = "black", size = 11),
      axis.text.x = element_text(angle = 35, hjust = 1, face = "bold"),
      axis.text.y = element_text(face = "bold"),
      axis.title = element_text(face = "bold"),
      plot.title = element_text(face = "bold", hjust = 0.5, size = 13.5),
      panel.grid.major = element_line(color = "grey90", linewidth = 0.4),
      legend.box = "horizontal",
      legend.position = "right"
    )
  
  if (!single_gene) {
    p_dotplot <- p_dotplot + facet_wrap(~gene, ncol = 1)
  }
  
  ggsave(file.path(out_dir, "01_group_split_dotplot.pdf"), p_dotplot, width = 8.5, height = ifelse(single_gene, 4.2, 3.5 * length(gene_list)))
  ggsave(file.path(out_dir, "01_group_split_dotplot.png"), p_dotplot, width = 8.5, height = ifelse(single_gene, 4.2, 3.5 * length(gene_list)), dpi = 300)
  
  # -------------------------------------------------------------
  # PLOT 2 & 3: Expression & Ratio Bar Plots (if sample data available)
  # -------------------------------------------------------------
  if (!is.null(df_sample_final)) {
    cur_sum <- summary_stats %>% filter(gene == cur_gene)
    cur_pts <- df_sample_final %>% filter(gene == cur_gene)
    
    max_y_expr <- max(cur_sum$mean_norm + cur_sum$sem_norm, cur_pts$norm_expr, na.rm = TRUE) * 1.25
    max_y_ratio <- max(cur_sum$mean_ratio_pct + cur_sum$sem_ratio_pct, cur_pts$expr_percent, na.rm = TRUE) * 1.25
    
    # 2. Expression Bar Plot
    p_bar_expr <- ggplot() +
      geom_bar(
        data = cur_sum,
        aes(x = celltype, y = mean_norm, fill = group_name),
        stat = "identity",
        position = position_dodge(0.8),
        width = 0.72,
        alpha = 0.88,
        color = "black",
        linewidth = 0.5
      ) +
      geom_errorbar(
        data = cur_sum,
        aes(x = celltype, ymin = mean_norm, ymax = mean_norm + sem_norm, group = group_name),
        position = position_dodge(0.8),
        width = 0.22,
        linewidth = 0.6
      ) +
      geom_point(
        data = cur_pts,
        aes(x = celltype, y = norm_expr, group = group_name, fill = group_name),
        position = position_jitterdodge(jitter.width = 0.12, dodge.width = 0.8, seed = 42),
        size = 2.4,
        shape = 21,
        color = "black",
        stroke = 0.6,
        alpha = 0.95
      ) +
      scale_fill_manual(name = "Group:", values = color_vec) +
      labs(
        title = paste0(cur_gene, " Expression in Subclusters"),
        subtitle = "Normalized Average Expression (Mean ± SEM)",
        x = "Cell Subcluster",
        y = paste0(cur_gene, " Normalized Expression")
      ) +
      scale_y_continuous(limits = c(0, max_y_expr), expand = c(0, 0)) +
      theme_pub +
      theme(legend.position = "top")
    
    # Auto-add significance stars
    if (exists("stats_summary_table") && "Significance_Expr" %in% colnames(stats_summary_table)) {
      sig_rows <- stats_summary_table %>% filter(Gene == cur_gene, Significance_Expr != "ns")
      if (nrow(sig_rows) > 0) {
        for (ri in 1:nrow(sig_rows)) {
          c_name <- sig_rows$CellType[ri]
          c_idx <- which(celltype_vec == c_name)
          if (length(c_idx) > 0) {
            y_base <- cur_sum %>% filter(celltype == c_name) %>% summarize(m = max(mean_norm + sem_norm)) %>% pull(m)
            y_line <- y_base * 1.15 + 0.05
            p_val_txt <- paste0(sig_rows$Significance_Expr[ri], " (p = ", formatC(sig_rows$P_val_t_test_equal[ri], digits = 3, format = "f"), ")")
            p_bar_expr <- p_bar_expr +
              annotate("segment", x = c_idx - 0.2, xend = c_idx + 0.2, y = y_line, yend = y_line, linewidth = 0.6) +
              annotate("text", x = c_idx, y = y_line * 1.06, label = p_val_txt, size = 3.5, fontface = "bold")
          }
        }
      }
    }
    
    ggsave(file.path(out_dir, "02_group_expression_barplot.pdf"), p_bar_expr, width = 8.5, height = 5.2)
    ggsave(file.path(out_dir, "02_group_expression_barplot.png"), p_bar_expr, width = 8.5, height = 5.2, dpi = 300)
    
    # 3. Ratio Bar Plot
    p_bar_ratio <- ggplot() +
      geom_bar(
        data = cur_sum,
        aes(x = celltype, y = mean_ratio_pct, fill = group_name),
        stat = "identity",
        position = position_dodge(0.8),
        width = 0.72,
        alpha = 0.88,
        color = "black",
        linewidth = 0.5
      ) +
      geom_errorbar(
        data = cur_sum,
        aes(x = celltype, ymin = mean_ratio_pct, ymax = mean_ratio_pct + sem_ratio_pct, group = group_name),
        position = position_dodge(0.8),
        width = 0.22,
        linewidth = 0.6
      ) +
      geom_point(
        data = cur_pts,
        aes(x = celltype, y = expr_percent, group = group_name, fill = group_name),
        position = position_jitterdodge(jitter.width = 0.12, dodge.width = 0.8, seed = 42),
        size = 2.4,
        shape = 21,
        color = "black",
        stroke = 0.6,
        alpha = 0.95
      ) +
      scale_fill_manual(name = "Group:", values = color_vec) +
      labs(
        title = paste0(cur_gene, " Expressing Cell Proportion (%)"),
        subtitle = "Percentage of Positive Expressing Cells (Mean ± SEM)",
        x = "Cell Subcluster",
        y = paste0(cur_gene, "+ Cells (%)")
      ) +
      scale_y_continuous(limits = c(0, max_y_ratio), expand = c(0, 0)) +
      theme_pub +
      theme(legend.position = "top")
    
    if (exists("stats_summary_table") && "Significance_Ratio" %in% colnames(stats_summary_table)) {
      sig_r_rows <- stats_summary_table %>% filter(Gene == cur_gene, Significance_Ratio != "ns")
      if (nrow(sig_r_rows) > 0) {
        for (ri in 1:nrow(sig_r_rows)) {
          c_name <- sig_r_rows$CellType[ri]
          c_idx <- which(celltype_vec == c_name)
          if (length(c_idx) > 0) {
            y_base <- cur_sum %>% filter(celltype == c_name) %>% summarize(m = max(mean_ratio_pct + sem_ratio_pct)) %>% pull(m)
            y_line <- y_base * 1.15 + 0.1
            p_val_txt <- paste0(sig_r_rows$Significance_Ratio[ri], " (p = ", formatC(sig_r_rows$P_val_ratio_t_test[ri], digits = 3, format = "f"), ")")
            p_bar_ratio <- p_bar_ratio +
              annotate("segment", x = c_idx - 0.2, xend = c_idx + 0.2, y = y_line, yend = y_line, linewidth = 0.6) +
              annotate("text", x = c_idx, y = y_line * 1.06, label = p_val_txt, size = 3.5, fontface = "bold")
          }
        }
      }
    }
    
    ggsave(file.path(out_dir, "03_group_ratio_barplot.pdf"), p_bar_ratio, width = 8.5, height = 5.2)
    ggsave(file.path(out_dir, "03_group_ratio_barplot.png"), p_bar_ratio, width = 8.5, height = 5.2, dpi = 300)
    
    # 4. Combined 2-in-1 Stacked Plot
    p_2in1 <- (
      p_bar_expr + theme(axis.title.x = element_blank(), axis.text.x = element_blank(), legend.position = "top")
    ) / (
      p_bar_ratio + theme(legend.position = "none")
    ) +
    plot_annotation(tag_levels = 'A') &
    theme(plot.tag = element_text(face = "bold", size = 15))
    
    ggsave(file.path(out_dir, "04_combined_twopanel_plot.pdf"), p_2in1, width = 8.5, height = 8.8)
    ggsave(file.path(out_dir, "04_combined_twopanel_plot.png"), p_2in1, width = 8.5, height = 8.8, dpi = 300)
    
    # 5. Faceted Free-Y Scale Plot
    p_facet <- ggplot() +
      geom_bar(data = cur_sum, aes(x = group_name, y = mean_norm, fill = group_name),
               stat = "identity", width = 0.65, alpha = 0.85, color = "black", linewidth = 0.4) +
      geom_errorbar(data = cur_sum, aes(x = group_name, ymin = mean_norm, ymax = mean_norm + sem_norm),
                    width = 0.25, linewidth = 0.5) +
      geom_point(data = cur_pts, aes(x = group_name, y = norm_expr, fill = group_name),
                 position = position_jitter(width = 0.1, seed = 42),
                 size = 2.2, shape = 21, color = "black", stroke = 0.5, alpha = 0.95) +
      facet_wrap(~celltype, scales = "free_y", ncol = min(4, length(celltype_vec))) +
      scale_fill_manual(values = color_vec) +
      labs(
        title = paste0(cur_gene, " Expression in Each Subcluster (Individual Scales)"),
        subtitle = "Normalized Average Expression (Mean ± SEM)",
        x = NULL,
        y = paste0(cur_gene, " Normalized Expression")
      ) +
      theme_bw(base_size = 11.5) +
      theme(
        strip.background = element_rect(fill = "#E8EEF5", color = "grey50"),
        strip.text = element_text(face = "bold", size = 11, color = "#1F4E79"),
        axis.text = element_text(color = "black", size = 10.5),
        axis.title = element_text(face = "bold", color = "black", size = 11.5),
        plot.title = element_text(face = "bold", hjust = 0.5, size = 13.5),
        plot.subtitle = element_text(hjust = 0.5, size = 10.5, color = "grey35"),
        legend.position = "none",
        panel.grid.minor = element_blank()
      )
    
    ggsave(file.path(out_dir, "05_facet_subclusters_barplot.pdf"), p_facet, width = 9.5, height = 6.2)
    ggsave(file.path(out_dir, "05_facet_subclusters_barplot.png"), p_facet, width = 9.5, height = 6.2, dpi = 300)
    
    # 6. Combined 3-in-1 Comprehensive Overview
    p_bar_expr_clean <- p_bar_expr +
      labs(title = paste0(cur_gene, " Normalized Expression"), subtitle = "Mean ± SEM") +
      theme(legend.position = "top", plot.title = element_text(size = 12.5), plot.subtitle = element_text(size = 10))
    p_bar_ratio_clean <- p_bar_ratio +
      labs(title = paste0(cur_gene, " Positive Proportion (%)"), subtitle = "Mean ± SEM") +
      theme(legend.position = "top", plot.title = element_text(size = 12.5), plot.subtitle = element_text(size = 10))
    
    p_3in1 <- (
      (p_bar_expr_clean | p_bar_ratio_clean)
    ) / (
      p_dotplot + theme(plot.margin = margin(t = 6, r = 12, b = 6, l = 12))
    ) +
    plot_layout(heights = c(1.35, 0.85)) +
    plot_annotation(
      tag_levels = 'A',
      title = paste0(cur_gene, " Expression and Cellular Distribution Across Subclusters"),
      theme = theme(plot.title = element_text(face = "bold", hjust = 0.5, size = 15, margin = margin(b = 8)))
    ) &
    theme(plot.tag = element_text(face = "bold", size = 14))
    
    ggsave(file.path(out_dir, "06_combined_threeinone_overview.pdf"), p_3in1, width = 12.5, height = 9.2)
    ggsave(file.path(out_dir, "06_combined_threeinone_overview.png"), p_3in1, width = 12.5, height = 9.2, dpi = 300)
  }
  
  summary_txt <- file.path(out_dir, "run_summary.txt")
  cat(
    paste0(
      "================================================================================\n",
      "17 · 单细胞分组基因表达气泡图与统计分析 - 运行摘要\n",
      "================================================================================\n",
      "运行时间: ", Sys.time(), "\n",
      "输入文件: ", params$input, "\n",
      "分析基因: ", paste(gene_list, collapse = ", "), "\n",
      "对比分组: ", paste(group_vec, collapse = " vs "), "\n",
      "细胞亚群 (", length(celltype_vec), "): ", paste(celltype_vec, collapse = ", "), "\n",
      "样本水平数据: ", ifelse(!is.null(df_sample_final), "是 (计算样本均值、SEM、SD及假设检验)", "否 (直接使用分组聚合数据)"), "\n",
      "输出目录: ", out_dir, "\n",
      "\n生成交付物清单:\n",
      "1. 01_group_split_dotplot.pdf / .png (组间分面气泡图)\n",
      "2. 02_group_expression_barplot.pdf / .png (表达量柱状散点图)\n",
      "3. 03_group_ratio_barplot.pdf / .png (表达比例柱状散点图)\n",
      "4. 04_combined_twopanel_plot.pdf / .png (表达量与比例综合双面板图)\n",
      "5. 05_facet_subclusters_barplot.pdf / .png (亚群独立刻度分面图)\n",
      "6. 06_combined_threeinone_overview.pdf / .png (三合一综合大图)\n",
      "7. group_gene_statistical_summary.xlsx (完整统计分析表 - 多Sheet Excel)\n",
      "8. group_gene_statistical_summary.tsv (统计汇总纯文本长表)\n",
      "9. run_summary.txt (本摘要文件)\n"
    ),
    file = summary_txt
  )
  cat("Run completed successfully! Artifacts written to:", out_dir, "\n")
}

# Run with parsed arguments
params <- parse_args()
run_pipeline(params)
