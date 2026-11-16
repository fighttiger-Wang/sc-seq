---
name: sc-group-gene-bubble-stats
displayName: 17 · 单细胞分组基因表达气泡图与统计 v0.1.0
description: 17 · 单细胞分组基因表达气泡图与统计 v0.1.0：从单细胞表达谱数据生成分组基因表达分面气泡图与完整组间统计分析表 Create publication-ready single-cell split/faceted group gene expression bubble plots (DotPlots) and comprehensive inter-group statistical workbooks (means, SEM, fold change, p-values) from single-cell expression data and gene lists. Use when users ask for 单细胞组间分面气泡图、分组基因表达气泡图、表达谱数据组间比较、组间表达量与比例统计表、指定基因亚群表达比较柱状散点图、或复现 Microglia 样式的出版级组间比较分析图表。
---

# 17 · 单细胞分组基因表达气泡图与统计 v0.1.0

使用内置参数化 R 脚本从单细胞表达谱数据自动生成出版级组间分面气泡图（Split DotPlot）、表达量与比例组间对比柱状散点图、双面板综合图以及多 Sheet 完整统计分析表（包含均值、SEM、SD、Fold Change、Student's t 检验及 Wilcoxon 秩和检验 $p$ 值）。

## 核心功能与输出规范

### 1. 核心图表交付（PDF 矢量图 + 300 DPI 高清 PNG）
- `01_group_split_dotplot.pdf / .png`：**单细胞组间分面气泡图 (Split DotPlot)**。X 轴为细胞亚群/细胞类型，Y 轴为实验分组；气泡大小严格对应阳性表达细胞百分比例（%），颜色对应标准化表达量（平均表达丰度）；多基因时自动分面或纵向扩展排列。
- `02_group_expression_barplot.pdf / .png`：**组间表达量柱状散点图**。柱高代表组均值，误差线代表均值标准误（SEM），叠加各生物学重复样本散点，并自动标注组间差异统计学显著性星号与 $p$ 值。
- `03_group_ratio_barplot.pdf / .png`：**组间阳性细胞占比柱状散点图**。展示各亚群中目的基因表达阳性细胞比例（Mean ± SEM）及显著性标记。
- `04_combined_twopanel_plot.pdf / .png`：**双面板综合图 (A+B)**。上栏 Panel A 为标准化表达量柱状图，下栏 Panel B 为阳性细胞占比柱状图。
- `05_facet_subclusters_barplot.pdf / .png`：**各亚群独立刻度分面图**。针对亚群间基线表达量差异较大的特点，采用自由 Y 轴独立展示各亚群组间差异。
- `06_combined_threeinone_overview.pdf / .png`：**三合一综合全景大图 (A+B+C)**。整合表达量、阳性比例与气泡图，适合论文正文或汇报主图展示。

### 2. 统计分析表格交付
- `group_gene_statistical_summary.xlsx`（专业配色多 Sheet Excel 工作簿）：
  - **Sheet 1「亚群统计汇总表」**：包含各亚群中参考组/对照组（Ref）与比较组/处理组（Comp）的样本量 $N$、表达量均值、SEM、SD、两组间均值差、变化倍数（Fold Change）、$\log_2\text{FC}$、等方差 Student's t 检验 $p$ 值、Welch's t 检验 $p$ 值、Wilcoxon 秩和检验 $p$ 值、表达量显著性标记（`***`, `**`, `*`, `ns`）、阳性细胞比例均值与 SEM、比例差异 $t$ 检验 $p$ 值及比例显著性标记。
  - **Sheet 2「样本水平表达明细」**：各生物学重复样本在各亚群中的原始表达值与阳性比例。
  - **Sheet 3「亚群分组聚合总表」**：用于绘制气泡图的分组汇总聚合表达数据。
- `group_gene_statistical_summary.tsv`：制表符分隔纯文本长表，方便下游生信流程快速调用。
- `run_summary.txt`：详细运行摘要与参数审计日志。

## 输入格式与支持范围

详见 [references/input-contract.md](references/input-contract.md)。支持以下三种数据输入形态：
1. **Seurat 标准分析输出 ZIP 压缩包**（如 `Microglia-02.zip`），包含：
   - `Celltype_Sample/avg_expr_result.txt`（样本水平长表，含生物学重复）
   - `Celltype_Group/avg_expr_result.txt`（组水平长表）
2. **包含上述文本表的解压目录**。
3. **单文件表达矩阵长表（TSV/CSV/TXT）**，表头包含 `gene`, `group`, `mean_expr`, `expr_ratio`, `norm_expr`（或 `pct_exp`, `avg_expr` 等标准别名）。

## 运行方式

### 命令行直接调用
```bash
Rscript scripts/draw_group_gene_bubble_stats.R \
  --input "path/to/expression_data.zip" \
  --genes "Cxcl13" \
  --output "path/to/output_dir" \
  --groups "Middle_aged_Con,Middle_aged_Fru" \
  --celltypes "Spp1_Mic,Ifit3_Mic,Active_Mic,Adap2os_Mic,Gadd45b_Mic,Polr2a_Mic,Pnisr_Mic" \
  --colors "#4B87B9,#E15759"
```

### 参数文件调用
复制 `assets/parameters.template.yaml`，填入路径与参数后运行：
```bash
Rscript scripts/draw_group_gene_bubble_stats.R --config "path/to/parameters.yaml"
```

### 参数说明
- `-i, --input`：输入 ZIP 数据包、解压目录或表达表格文件路径（必需）。
- `-g, --genes`：目的基因名称，多个基因以逗号分隔，如 `Cxcl13,P2ry12`，或传入包含基因列表的 `.txt` 文件（默认 `Cxcl13`）。
- `-o, --output`：输出目录路径（默认 `./output`）。
- `--groups`：对比分组（参考组在前，处理组在后，以逗号分隔，如 `Control,Treated`；若省略且存在两组，则自动识别）。
- `--celltypes`：指定的细胞亚群展示顺序（逗号分隔；若省略则自动获取所有亚群并过滤未定义类群）。
- `--colors`：分组颜色 Hex 编码（默认 `#4B87B9,#E15759` 分别对应经典学术蓝与学术红）。
- `-t, --title`：图表自定义标题（可选）。

## 运行环境依赖
- R >= 4.0
- R 核心依赖包：`ggplot2`, `dplyr`, `tidyr`, `scales`, `patchwork`, `openxlsx`（可选 `yaml`）。
