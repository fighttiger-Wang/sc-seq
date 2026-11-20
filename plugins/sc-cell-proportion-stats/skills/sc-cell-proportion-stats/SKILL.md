---
name: sc-cell-proportion-stats
displayName: B05 · 细胞比例统计图 v0.1.0
description: B05 · 细胞比例统计图 v0.1.0：从单细胞转录组数据（Seurat/RDS/RData/注释表）自动化完成样本水平与组水平细胞占比统计、多组差异分析（ANOVA/Kruskal-Wallis）、两两比较显著性检验（t-test/Wilcoxon）、多重检验校正（FDR/p.adj）、Ro/e 组织偏好性分析，并生成高分出版级两态可视化：1) 动态网格自适应零重叠高分云雨图（Raincloud Plot：左镂空散点+中窄箱线图+右平滑半小提琴+顶部显著性括号+隔离顶部双图例）；2) 多维细胞比例复合气泡图（顶部细胞堆叠柱状图+中心占比气泡图+右侧细胞总数条形图）。包含专业配色多 Sheet Excel 工作簿与 TSV 数据表交付。Use when users ask for 单细胞细胞比例统计、细胞占比显著性分析、细胞比例云雨图、Raincloud Plot、细胞比例多维复合气泡图、Ro/e 偏好分析、或需要对单细胞各样本及实验组进行严谨的细胞比例统计与出版级绘图。
---

# B05 · 细胞比例统计图 v0.1.0

从单细胞转录组数据（Seurat 对象、RData、RDS、或元数据长表）出发，全自动完成生物学重复样本水平的细胞占比归一化、实验组水平的描述性统计（均值、标准差、标准误、中位数、四分位距）、全局多组差异假设检验（ANOVA 与 Kruskal-Wallis）、两两配对差异显著性检验（Welch's $t$ 检验与 Wilcoxon 秩和检验）、多重检验校正（Benjamini-Hochberg FDR / $p.adj$）、变化倍数（Fold Change 与 $\log_2\text{FC}$）及列联表 Ro/e 组织偏好性分析；并自动化生成符合国际顶级期刊（*Nature* / *Cancer Cell*）出版审美的两大可视化图表面板与标准数据交付包。

---

## 核心功能与交付成果标准

### 1. 出版级核心图表交付（矢量 PDF + 300 DPI 超清 PNG）

#### 样式一：动态网格自适应零重叠高分云雨图 (Publication Raincloud Plot)
- **交付文件**：
  - `plots/Cell_Proportion_Significance_Raincloud_Fine.pdf / .png`（精细亚群全景图）
  - `plots/Cell_Proportion_Significance_Raincloud_Major.pdf / .png`（大类主要谱系全景图）
  - `plots/individual_cell_types/<Prefix>_<CellType>_raincloud.pdf / .png`（各细胞类型独立高分单图）
- **核心形态规范**：
  - **左侧镂空散点**：生物学重复样本真实散点，采用透明镂空背景（`facecolors='none'`）、组别专属颜色描边与区分形状（圆形、方块、三角、菱形），固定随机抖动（Jitter），杜绝数据点遮挡。
  - **中间极简箱线图**：极窄宽度（`0.10`）、纯白填充截断背景网格线、组色描边与中位线，隐藏离群点。
  - **右侧平滑半小提琴**：采用 Silverman 自适应带宽核密度估计（KDE），单侧平滑展开，淡色半透明填充（$\alpha=0.28$）加精致描边。
  - **多层级差异显著性连线**：自动在顶部标注层级括号与显著性星号（`***`, `**`, `*`, `.`, `ns`），各括号纵向安全阶梯递增，杜绝穿插或压字。
  - **绝对隔离 Header 双图例架构**：采用 `GridSpec` 预留独立 Row 0 区域（高度 2.0 英寸），上层居中放置实验组颜色/形状图例框，下层居中放置圆角独立显著性说明条（Significance Thresholds Banner），两者物理间距超 1.1 英寸，从数学拓扑上 **100% 杜绝图例重叠、文字压线或遮挡子图**。
  - **自适应动态网格排版**：代码自动根据细胞类型数量 $N$ 计算最优行数与列数（如 6 群为 $2\times 3$，10 或 11 群自适应为 $3\times 4$），自动隐藏多余空白子图。

#### 样式二：多维细胞比例复合气泡图 (Multi-Dimensional Composite Bubble Plot)
- **交付文件**：
  - `plots/Cell_Proportion_<Prefix>_multidim_composite_by_group.pdf / .png`（按实验分组复合图）
  - `plots/Cell_Proportion_<Prefix>_multidim_composite_by_sample.pdf / .png`（按样本复合图）
- **核心形态规范**：
  - 基于 `aplot` 像素级精准拼装的三合一复合画卷：
    - **顶部面板**：各分组或样本的总细胞量堆叠柱状图（Stacked Barplot）。
    - **中心面板**：细胞类型占比气泡图（Bubble DotPlot），气泡面积严格线性映射细胞比例百分比（%），颜色区分细胞亚群。
    - **右侧面板**：各细胞类型在全局数据集中的总细胞计数横向条形图（Horizontal Barplot）。

---

### 2. 标准化统计分析表格交付（多 Sheet Excel 工作簿 + 规范 TSV）

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

---

## 快速调用方式

### 方式一：一键式 Shell 自动化流水线（推荐集群使用）
```bash
bash scripts/run_all_proportion_pipeline.sh \
  -i "/mnt/test/AABB/Project_Name/Plot.rData" \
  -a "/mnt/test/AABB/Project_Name/Annotation_Input.xlsx" \
  -g "/mnt/test/AABB/Project_Name/Annotation_Input.xlsx" \
  -o "/mnt/test/AABB/Project_Name/cell_proportion_analysis" \
  --group_order "WT,Placebo,Treatment_A,Treatment_B" \
  --celltype_cols "cell_type_fine,cell_type_major" \
  --sif "/mnt/test/FCX/sif/sc_Analysis_V4.0.sif"
```

### 方式二：分步独立脚本调用

#### 1. 统计计算与主工作簿生成 (R)
```bash
Rscript scripts/run_proportion_stats.R \
  --input "path/to/Plot.rData" \
  --anno "path/to/Annotation_Input.xlsx" \
  --group "path/to/Annotation_Input.xlsx" \
  --output "./cell_proportion_analysis" \
  --celltype_cols "cell_type_fine,cell_type_major" \
  --group_order "WT,Placebo,Treatment_A,Treatment_B"
```

#### 2. 自适应网格零重叠高分云雨图绘制 (Python)
```bash
python3 scripts/plot_dynamic_raincloud.py \
  --input "./cell_proportion_analysis/summary/tables/Cell_Proportion_Fine_Sample_Percentages.tsv" \
  --output "./cell_proportion_analysis/summary/plots" \
  --prefix "Fine" \
  --groups "WT,Placebo,Treatment_A,Treatment_B" \
  --ncols 4 \
  --palette "nature"
```

#### 3. 多维复合气泡柱状图绘制 (R)
```bash
Rscript scripts/plot_multidim_composite.R \
  --input "./cell_proportion_analysis/metadata_annotated.rds" \
  --output "./cell_proportion_analysis/summary/plots" \
  --celltype_col "cell_type_fine" \
  --prefix "Fine" \
  --group_order "WT,Placebo,Treatment_A,Treatment_B"
```

---

## 避坑与质控守则 (Best Practices & Pitfalls)

1. **图例防撞红线**：
   - 严禁在包含多子图的画板中使用自由浮动的 `bbox_to_anchor` 叠加在子图坐标轴上方。
   - 必须通过 `GridSpec` 划分出物理高度 $\geq 1.8$ 英寸的专用 Row 0，将 `Experimental Groups` 放置于顶部（$y \geq 0.8$），显著性条带置于下方（$y \leq 0.25$）。
2. **生物学重复单元守则**：
   - 细胞占比统计必须基于**样本（Sample / orig.ident）**作为独立分析单元，不可把成千上万个单细胞当作抽样点（否则会造成假性极小 $p$ 值膨胀）。
3. **补零与分母对齐**：
   - 某些罕见亚群在特定样本中可能计数为 0，统计矩阵中必须进行显式补零（`0.0%`），严禁将其作为 `NA` 剔除，否则会导致各组样本量 $N$ 不一致。
4. **集群内存与容器兼容**：
   - 集群提交 Slurm 作业时，注意部分集群（如 `openclaw01`）配置了 `RealMemory=1` 默认值，在 `#SBATCH` 中**严禁显式声明 `--mem=...`**，直接使用容器运行即可。

---

## 参考资料与规范

- 输入数据格式规范：详见 [references/input_contract.md](references/input_contract.md)
- 统计检验与数学模型：详见 [references/statistical_methods.md](references/statistical_methods.md)
- 出版级可视化排版指南：详见 [references/visualization_guidelines.md](references/visualization_guidelines.md)
- 参数模版文件：详见 [assets/parameters_template.yaml](assets/parameters_template.yaml)
