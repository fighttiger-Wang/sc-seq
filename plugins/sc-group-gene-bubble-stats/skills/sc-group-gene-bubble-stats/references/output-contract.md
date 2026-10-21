# Output Contract: 17 · 单细胞分组基因表达气泡图与统计分析

## 1. 输出目录结构
每次运行将在指定的 `--output` 目录下生成以下完整图表与数据分析文件：

```text
output_directory/
├── 01_group_split_dotplot.pdf          # 组间分面气泡图 (矢量 PDF)
├── 01_group_split_dotplot.png          # 组间分面气泡图 (300 DPI PNG)
├── 02_group_expression_barplot.pdf     # 组间表达量柱状散点图 (含 SEM 与显著性星号)
├── 02_group_expression_barplot.png     # 组间表达量柱状散点图
├── 03_group_ratio_barplot.pdf          # 组间阳性细胞占比柱状散点图 (含 SEM 与显著性)
├── 03_group_ratio_barplot.png          # 组间阳性细胞占比柱状散点图
├── 04_combined_twopanel_plot.pdf       # 表达量与比例综合双面板图 (Panel A + Panel B)
├── 04_combined_twopanel_plot.png       # 表达量与比例综合双面板图
├── 05_facet_subclusters_barplot.pdf    # 各亚群独立刻度分面图 (自由 Y 轴)
├── 05_facet_subclusters_barplot.png    # 各亚群独立刻度分面图
├── 06_combined_threeinone_overview.pdf # 三合一综合全景大图 (A+B+C)
├── 06_combined_threeinone_overview.png # 三合一综合全景大图
├── group_gene_statistical_summary.xlsx # 完整统计分析表 (专业三Sheet Excel 工作簿)
├── group_gene_statistical_summary.tsv  # 统计汇总纯文本长表
└── run_summary.txt                     # 运行摘要与参数审计日志
```

## 2. 统计分析工作簿字段说明 (Excel Sheet 1)
- `Gene`：基因符号
- `CellType`：细胞亚群名称
- `Reference_Group`：对照组/参考组名称
- `Comparison_Group`：处理组/比较组名称
- `Ref_Mean_Norm` / `Comp_Mean_Norm`：两组的平均归一化表达量
- `Ref_SEM_Norm` / `Comp_SEM_Norm`：两组表达量的标准误（SEM）
- `Ref_SD_Norm` / `Comp_SD_Norm`：两组表达量的标准差（SD）
- `Ref_N` / `Comp_N`：两组的独立生物学重复样本数
- `Diff_Mean_Norm`：均值差值（比较组 - 参考组）
- `Fold_Change`：变化倍数（附加 0.0001 pseudo-count 平滑）
- `Log2_FC`：$\log_2(\text{Fold Change})$
- `P_val_t_test_equal`：两独立样本等方差 Student's t-test $p$ 值
- `P_val_t_test_welch`：异方差 Welch's t-test $p$ 值
- `P_val_Wilcoxon`：Wilcoxon 秩和检验 (Mann-Whitney U) $p$ 值
- `Significance_Expr`：表达量显著性标识（`***` $p < 0.001$, `**` $p < 0.01$, `*` $p < 0.05$, `ns` 无显著差异）
- `Ref_Ratio_Pct_Mean` / `Comp_Ratio_Pct_Mean`：两组表达阳性细胞比例均值（%）
- `Ref_Ratio_Pct_SEM` / `Comp_Ratio_Pct_SEM`：阳性细胞比例标准误（%）
- `P_val_ratio_t_test`：阳性细胞占比 $t$ 检验 $p$ 值
- `Significance_Ratio`：阳性比例显著性标识
