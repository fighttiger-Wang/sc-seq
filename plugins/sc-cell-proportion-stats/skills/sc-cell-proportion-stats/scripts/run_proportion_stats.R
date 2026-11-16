#!/usr/bin/env Rscript
# ==============================================================================
# Script: run_proportion_stats.R
# Skill: 23-单细胞细胞比例统计与显著性分析
# Description: Standardized single-cell cell type proportion statistical analysis.
#   Calculates sample percentages, group statistics (Mean, SD, SEM, Median, IQR),
#   ANOVA, Kruskal-Wallis, pairwise t-tests, Wilcoxon rank-sum tests, Log2FC,
#   FDR multiple testing corrections, and Ro/e (Observed / Expected) ratios.
#   Outputs a formatted multi-sheet Excel workbook and standard TSVs.
# ==============================================================================

suppressPackageStartupMessages({
  library(optparse)
  library(openxlsx)
  library(dplyr)
  library(tidyr)
})

option_list <- list(
  make_option(c("-i", "--input"), type = "character", default = NULL,
              help = "Path to input file: Seurat RDS/RData or metadata TSV/CSV/RDS [required]", metavar = "file"),
  make_option(c("-a", "--anno"), type = "character", default = NULL,
              help = "Path to cluster/cell-type annotation Excel/TSV/CSV file (optional)", metavar = "file"),
  make_option(c("-g", "--group"), type = "character", default = NULL,
              help = "Path to sample-to-group Excel/TSV/CSV file (optional if group exists in metadata)", metavar = "file"),
  make_option(c("-o", "--output"), type = "character", default = "./cell_proportion_analysis",
              help = "Output directory [default: %default]", metavar = "dir"),
  make_option(c("--group_col"), type = "character", default = "group",
              help = "Group column name in metadata [default: %default]"),
  make_option(c("--sample_col"), type = "character", default = "sample",
              help = "Sample column name in metadata [default: %default]"),
  make_option(c("--cluster_col"), type = "character", default = "seurat_clusters",
              help = "Cluster column name in metadata [default: %default]"),
  make_option(c("--celltype_cols"), type = "character", default = "cell_type_fine,cell_type_major",
              help = "Comma-separated cell type column name(s) to analyze [default: %default]"),
  make_option(c("--group_order"), type = "character", default = NULL,
              help = "Comma-separated group order (e.g., 'WT,Placebo,A118P,N141R')"),
  make_option(c("--sample_order"), type = "character", default = NULL,
              help = "Comma-separated sample order")
)

opt_parser <- OptionParser(option_list = option_list)
opt <- parse_args(opt_parser)

if (is.null(opt$input)) {
  print_help(opt_parser)
  stop("Missing required argument: --input", call. = FALSE)
}

out_dir <- opt$output
tab_dir <- file.path(out_dir, "summary", "tables")
plot_dir <- file.path(out_dir, "summary", "plots")
dir.create(tab_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(plot_dir, recursive = TRUE, showWarnings = FALSE)

# 1. Load Data
cat("[1/5] Loading input data from:", opt$input, "\n")
ext <- tolower(tools::file_ext(opt$input))

if (ext == "rds") {
  obj <- readRDS(opt$input)
  if (inherits(obj, "Seurat")) {
    meta <- obj@meta.data
  } else if (is.data.frame(obj)) {
    meta <- obj
  } else {
    stop("Unsupported RDS object class: ", class(obj))
  }
} else if (ext %in% c("rdata", "rda")) {
  e <- new.env()
  load(opt$input, envir = e)
  objs <- ls(envir = e)
  seurat_objs <- objs[sapply(objs, function(x) inherits(get(x, envir = e), "Seurat"))]
  if (length(seurat_objs) > 0) {
    meta <- get(seurat_objs[1], envir = e)@meta.data
  } else {
    df_objs <- objs[sapply(objs, function(x) is.data.frame(get(x, envir = e)))]
    if (length(df_objs) > 0) {
      meta <- get(df_objs[1], envir = e)
    } else {
      stop("No Seurat or data.frame object found in RData file")
    }
  }
} else if (ext %in% c("tsv", "txt")) {
  meta <- read.delim(opt$input, stringsAsFactors = FALSE)
} else if (ext == "csv") {
  meta <- read.csv(opt$input, stringsAsFactors = FALSE)
} else {
  stop("Unsupported input file extension: ", ext)
}

# Normalize basic columns
if (!"sample" %in% colnames(meta) && opt$sample_col %in% colnames(meta)) {
  meta$sample <- as.character(meta[[opt$sample_col]])
} else if ("orig.ident" %in% colnames(meta) && !"sample" %in% colnames(meta)) {
  meta$sample <- as.character(meta$orig.ident)
}

# 2. Map Annotation and Group if provided
if (!is.null(opt$anno) && file.exists(opt$anno)) {
  cat("[2/5] Merging cluster annotations from:", opt$anno, "\n")
  anno_ext <- tolower(tools::file_ext(opt$anno))
  if (anno_ext %in% c("xlsx", "xls")) {
    anno_df <- read.xlsx(opt$anno, sheet = 1)
  } else {
    anno_df <- read.delim(opt$anno, stringsAsFactors = FALSE)
  }
  cluster_col_anno <- colnames(anno_df)[1]
  meta$cluster_str <- as.character(meta[[opt$cluster_col]])
  anno_df[[cluster_col_anno]] <- as.character(anno_df[[cluster_col_anno]])
  
  # Merge or map columns
  for (cname in colnames(anno_df)[-1]) {
    map_vec <- setNames(anno_df[[cname]], anno_df[[cluster_col_anno]])
    # sanitize name
    clean_cname <- gsub("[ /()+-]", "_", cname)
    meta[[clean_cname]] <- map_vec[meta$cluster_str]
  }
}

if (!is.null(opt$group) && file.exists(opt$group)) {
  cat("[2/5] Merging sample grouping from:", opt$group, "\n")
  grp_ext <- tolower(tools::file_ext(opt$group))
  if (grp_ext %in% c("xlsx", "xls")) {
    grp_df <- read.xlsx(opt$group, sheet = 1)
    if (sheetCount <- length(getSheetNames(opt$group)) > 1) {
      # try sheet 2 if exists
      sheets <- getSheetNames(opt$group)
      if (any(grepl("分组|group", sheets, ignore.case = TRUE))) {
        grp_df <- read.xlsx(opt$group, sheet = grep("分组|group", sheets, ignore.case = TRUE)[1])
      }
    }
  } else {
    grp_df <- read.delim(opt$group, stringsAsFactors = FALSE)
  }
  s_col <- colnames(grp_df)[1]
  g_col <- colnames(grp_df)[2]
  sample_to_group <- setNames(as.character(grp_df[[g_col]]), as.character(grp_df[[s_col]]))
  meta$group <- sample_to_group[as.character(meta$sample)]
} else if (opt$group_col %in% colnames(meta)) {
  meta$group <- as.character(meta[[opt$group_col]])
}

if (!"group" %in% colnames(meta) || all(is.na(meta$group))) {
  stop("Group information could not be resolved in metadata. Please provide --group file or check --group_col.")
}

# Determine Group and Sample Orders
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

meta$group <- factor(meta$group, levels = group_order)
meta$sample <- factor(meta$sample, levels = sample_order)

# Save intermediate annotated metadata
saveRDS(meta, file.path(out_dir, "metadata_annotated.rds"))
cat("Metadata annotated and saved. Total cells:", nrow(meta), "across", length(unique(meta$sample)), "samples.\n")

# Helper function for significance symbols
get_asterisk <- function(p) {
  if (is.na(p)) return("NA")
  if (p < 0.001) return("***")
  if (p < 0.01) return("**")
  if (p < 0.05) return("*")
  if (p < 0.1) return(".")
  return("ns")
}

# Helper to compute Ro/e
compute_roe <- function(df_counts) {
  # df_counts: cell_type, group, count
  mat <- df_counts %>%
    pivot_wider(names_from = group, values_from = count, values_fill = 0) %>%
    tibble::column_to_rownames("cell_type") %>%
    as.matrix()
  
  chisq_res <- chisq.test(mat)
  obs <- chisq_res$observed
  exp <- chisq_res$expected
  roe <- obs / exp
  return(as.data.frame(roe) %>% tibble::rownames_to_column("cell_type"))
}

# 3. Analyze each cell type column
target_cols <- strsplit(opt$celltype_cols, ",")[[1]]
valid_cols <- intersect(target_cols, colnames(meta))

if (length(valid_cols) == 0) {
  stop("None of the specified cell type columns found in metadata: ", opt$celltype_cols)
}

cat("[3/5] Performing statistical analyses on:", paste(valid_cols, collapse = ", "), "\n")

# Master Excel Workbook
wb <- createWorkbook()

# Style definitions
header_style <- createStyle(fontSize = 11, fontColour = "#FFFFFF", fgColor = "#2C3E50",
                            halign = "center", valign = "center", textDecoration = "bold")
num_style <- createStyle(numFmt = "0.0000")
pct_style <- createStyle(numFmt = "0.00%")

addWorksheet(wb, "说明与统计规范")
readme_df <- data.frame(
  项目 = c("技能名称", "输入数据", "细胞总数", "分析样本数", "实验分组", "统计检验", "显著性标准", "Ro/e解释"),
  说明 = c(
    "23 · 单细胞细胞比例统计与显著性分析 v0.1.0",
    opt$input,
    as.character(nrow(meta)),
    as.character(length(unique(meta$sample))),
    paste(group_order, collapse = ", "),
    "方差分析(ANOVA)、Kruskal-Wallis、双尾两样本t检验、Wilcoxon秩和检验、Benjamini-Hochberg FDR校正",
    "***: p < 0.001, **: p < 0.01, *: p < 0.05, .: p < 0.1, ns: p >= 0.1",
    "Ro/e = 观察细胞数 / 期望细胞数。Ro/e > 1 代表该细胞类型在目标组富集，Ro/e < 1 代表耗竭"
  ),
  stringsAsFactors = FALSE
)
writeData(wb, "说明与统计规范", readme_df)

for (col_name in valid_cols) {
  cat("\nProcessing column:", col_name, "...\n")
  prefix <- gsub("^cell_type_", "", col_name)
  prefix_title <- paste0(toupper(substr(prefix, 1, 1)), substr(prefix, 2, nchar(prefix)))
  
  df_sub <- meta[!is.na(meta[[col_name]]) & !is.na(meta$group), ]
  cell_types <- sort(unique(df_sub[[col_name]]))
  
  # A. Sample Percentages
  sample_counts <- df_sub %>%
    group_by(sample, group, cell_type = .data[[col_name]]) %>%
    summarise(count = n(), .groups = "drop") %>%
    group_by(sample) %>%
    mutate(total_sample_cells = sum(count),
           percentage = (count / total_sample_cells) * 100) %>%
    ungroup()
  
  # Ensure all cell types and samples are represented (fill 0)
  grid_all <- expand.grid(
    sample = levels(meta$sample),
    cell_type = cell_types,
    stringsAsFactors = FALSE
  )
  sample_to_grp <- unique(data.frame(sample = meta$sample, group = meta$group))
  grid_all <- merge(grid_all, sample_to_grp, by = "sample")
  
  sample_pct_full <- merge(grid_all, sample_counts[, c("sample", "cell_type", "count", "percentage")],
                           by = c("sample", "cell_type"), all.x = TRUE)
  sample_pct_full$count[is.na(sample_pct_full$count)] <- 0
  sample_pct_full$percentage[is.na(sample_pct_full$percentage)] <- 0
  
  # Wide percentage table for plotting & export
  wide_pct <- sample_pct_full %>%
    select(sample, group, cell_type, percentage) %>%
    pivot_wider(names_from = cell_type, values_from = percentage, values_fill = 0)
  
  # B. Group Summary Statistics
  group_stats <- sample_pct_full %>%
    group_by(cell_type, group) %>%
    summarise(
      N = n(),
      Mean_Pct = mean(percentage),
      SD_Pct = sd(percentage),
      SEM_Pct = sd(percentage) / sqrt(n()),
      Median_Pct = median(percentage),
      IQR_Pct = IQR(percentage),
      Min_Pct = min(percentage),
      Max_Pct = max(percentage),
      .groups = "drop"
    )
  
  # C. Pairwise Comparisons & Global Tests
  pairwise_res <- list()
  global_res <- list()
  
  for (ct in cell_types) {
    df_ct <- sample_pct_full[sample_pct_full$cell_type == ct, ]
    
    # Global tests if >2 groups
    if (length(group_order) > 2) {
      aov_fit <- aov(percentage ~ group, data = df_ct)
      aov_p <- summary(aov_fit)[[1]][["Pr(>F)"]][1]
      kw_p <- kruskal.test(percentage ~ group, data = df_ct)$p.value
    } else {
      aov_p <- NA
      kw_p <- NA
    }
    
    global_res[[ct]] <- data.frame(
      cell_type = ct,
      ANOVA_p = aov_p,
      Kruskal_p = kw_p,
      stringsAsFactors = FALSE
    )
    
    # Pairwise tests
    for (i in 1:(length(group_order) - 1)) {
      for (j in (i + 1):length(group_order)) {
        g1 <- group_order[i]
        g2 <- group_order[j]
        
        v1 <- df_ct$percentage[df_ct$group == g1]
        v2 <- df_ct$percentage[df_ct$group == g2]
        
        mean1 <- mean(v1)
        mean2 <- mean(v2)
        diff_mean <- mean2 - mean1
        fc <- (mean2 + 0.001) / (mean1 + 0.001)
        log2fc <- log2(fc)
        
        # t-test (Welch)
        t_p <- tryCatch({
          if (sd(v1) == 0 && sd(v2) == 0) 1.0 else t.test(v1, v2)$p.value
        }, error = function(e) NA)
        
        # Wilcoxon
        w_p <- tryCatch({
          if (length(unique(c(v1, v2))) <= 1) 1.0 else wilcox.test(v1, v2, exact = FALSE)$p.value
        }, error = function(e) NA)
        
        pairwise_res[[paste(ct, g1, g2, sep = "__")]] <- data.frame(
          cell_type = ct,
          Group1 = g1,
          Group2 = g2,
          Contrast = paste0(g2, " vs ", g1),
          Mean_Group1 = mean1,
          Mean_Group2 = mean2,
          Diff_Mean = diff_mean,
          Fold_Change = fc,
          Log2FC = log2fc,
          t_test_p = t_p,
          t_test_sig = get_asterisk(t_p),
          wilcox_p = w_p,
          wilcox_sig = get_asterisk(w_p),
          stringsAsFactors = FALSE
        )
      }
    }
  }
  
  df_pairwise <- do.call(rbind, pairwise_res)
  # Multi-testing correction per contrast
  df_pairwise <- df_pairwise %>%
    group_by(Contrast) %>%
    mutate(
      t_test_fdr = p.adjust(t_test_p, method = "BH"),
      t_test_fdr_sig = sapply(t_test_fdr, get_asterisk),
      wilcox_fdr = p.adjust(wilcox_p, method = "BH"),
      wilcox_fdr_sig = sapply(wilcox_fdr, get_asterisk)
    ) %>%
    ungroup()
  
  # D. Ro/e Analysis
  counts_group <- df_sub %>%
    group_by(cell_type = .data[[col_name]], group) %>%
    summarise(count = n(), .groups = "drop")
  
  roe_df <- compute_roe(counts_group)
  
  # E. Export TSV files
  cat("[4/5] Writing standardized TSVs for:", prefix_title, "\n")
  write.table(wide_pct, file.path(tab_dir, paste0("Cell_Proportion_", prefix_title, "_Sample_Percentages.tsv")),
              sep = "\t", quote = FALSE, row.names = FALSE)
  write.table(group_stats, file.path(tab_dir, paste0("Cell_Proportion_", prefix_title, "_Group_Statistics.tsv")),
              sep = "\t", quote = FALSE, row.names = FALSE)
  write.table(df_pairwise, file.path(tab_dir, paste0("Cell_Proportion_", prefix_title, "_Pairwise_Tests.tsv")),
              sep = "\t", quote = FALSE, row.names = FALSE)
  write.table(roe_df, file.path(tab_dir, paste0("Cell_Proportion_", prefix_title, "_Roe_Preferences.tsv")),
              sep = "\t", quote = FALSE, row.names = FALSE)
  
  # F. Add to Master Excel
  sheet_pct <- paste0(prefix_title, "_样本比例明细")
  sheet_stat <- paste0(prefix_title, "_组统计量")
  sheet_pair <- paste0(prefix_title, "_两两比较显著性")
  sheet_roe <- paste0(prefix_title, "_Roe组织偏好性")
  
  addWorksheet(wb, sheet_pct)
  writeData(wb, sheet_pct, wide_pct, headerStyle = header_style)
  
  addWorksheet(wb, sheet_stat)
  writeData(wb, sheet_stat, group_stats, headerStyle = header_style)
  
  addWorksheet(wb, sheet_pair)
  writeData(wb, sheet_pair, df_pairwise, headerStyle = header_style)
  
  addWorksheet(wb, sheet_roe)
  writeData(wb, sheet_roe, roe_df, headerStyle = header_style)
}

excel_out <- file.path(tab_dir, "Cell_Proportion_Significance_Summary.xlsx")
saveWorkbook(wb, excel_out, overwrite = TRUE)
cat("[5/5] Master Excel workbook generated:", excel_out, "\n")
cat("Statistical pipeline completed successfully!\n")
