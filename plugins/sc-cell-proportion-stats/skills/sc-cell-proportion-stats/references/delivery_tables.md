# B05 标准化统计分析表格交付明细（verbatim 自 SKILL.md）

交付至 `summary/tables/` 目录：
- **`Cell_Proportion_Significance_Summary.xlsx`**（标准化科研配色专业工作簿）：
  - **Sheet 1「说明与统计规范」**：记录项目来源、细胞总数、样本分组、统计学检验原理与显著性符号定义。
  - **Sheet 2「<Prefix>_样本比例明细」**：各生物学重复样本在各细胞类型中的绝对计数与归一化百分比（%）宽表。
  - **Sheet 3「<Prefix>_组统计量」**：各实验组的样本量 $N$、均值（Mean）、标准差（SD）、标准误（SEM）、中位数（Median）、四分位距（IQR）、极小值与极大值。
  - **Sheet 4「<Prefix>_两两比较显著性」**：各组两两对比的均值差（Diff Mean）、变化倍数（Fold Change）、$\log_2\text{FC}$、Welch's $t$ 检验 $p$ 值、Wilcoxon 秩和检验 $p$ 值、FDR 校正 $p$ 值（$p.adj$）及严格对应的显著性符号。
  - **Sheet 5「<Prefix>_Roe组织偏好性」**：基于卡方检验期望频数的 Ro/e 比值表（$\text{Ro/e} > 1$ 代表正向富集，$\text{Ro/e} < 1$ 代表负向耗竭）。
- **纯文本 TSV 伴随表**：
  - `Cell_Proportion_<Prefix>_Sample_Percentages.tsv`
  - `Cell_Proportion_<Prefix>_Group_Statistics.tsv`
  - `Cell_Proportion_<Prefix>_Pairwise_Tests.tsv`
  - `Cell_Proportion_<Prefix>_Roe_Preferences.tsv`
