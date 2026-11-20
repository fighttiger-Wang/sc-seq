# B05 快速调用命令（verbatim 自 SKILL.md）

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
