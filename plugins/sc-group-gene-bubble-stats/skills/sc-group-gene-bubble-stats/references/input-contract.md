# Input Contract: 17 · 单细胞分组基因表达气泡图与统计分析

## 1. 概述
本技能支持从多种常见的单细胞转录组（scRNA-seq）分析表达数据中提取目标基因的亚群与组别表达信息，自动完成数据清洗、长表重塑、样本级别汇总与统计学假设检验。

## 2. 支持的数据输入形式

### 形式 A：Seurat 标准交付压缩包（推荐）
提供包含 Seurat 平均表达量分析交付物的 `.zip` 文件（例如 `Microglia-02.zip`），内部需包含：
- `Celltype_Sample/avg_expr_result.txt`：生物学重复样本水平的平均表达量与阳性比例长表（用于计算组内 Mean, SEM, SD, $t$ 检验与 Wilcoxon 检验）。
- `Celltype_Group/avg_expr_result.txt`：组水平聚合后的平均表达量与阳性比例长表（用于绘制气泡图）。
- 亦兼容 `cluster_sample/avg_expr_result.txt` 与 `Cluster_Group/avg_expr_result.txt`。

### 形式 B：解压数据目录
直接传入包含上述子文件夹与 `avg_expr_result.txt` 的本地目录路径。

### 形式 C：单文件长表（TSV / CSV / TXT）
包含以下字段的表格文件（制表符或逗号分隔）：
- `gene`（或 `Symbol`, `Genes`）：基因符号，大小写不敏感。
- `group`（或 `Cluster`, `Celltype`, `SubCluster`）：亚群与分组/样本组合标识（例如 `Spp1_Mic_Middle_aged_Fru` 或 `Spp1_Mic_LC_14m_fru1`）。
- `norm_expr`（或 `avg_expr`, `Expression`）：标准化平均表达量。
- `expr_ratio`（或 `pct.exp`, `pct_exp`, `ratio`）：表达阳性细胞比例（0 ~ 1 或 0% ~ 100%）。
- `mean_expr`（可选）：原始均值表达量。

## 3. 参数契约
| 参数名 | 简写 | 必填 | 默认值 | 说明 |
| :--- | :--- | :---: | :---: | :--- |
| `--input` | `-i` | 是 | 无 | 输入 ZIP、目录或文本表路径 |
| `--genes` | `-g` | 否 | `Cxcl13` | 目的基因，多个基因以逗号分隔，或文本文件路径 |
| `--output` | `-o` | 否 | `./output` | 输出目录路径 |
| `--groups` | | 否 | 自动识别 | 对比分组（如 `Control,Treated`），第一组为对照/参考组 |
| `--celltypes`| | 否 | 自动提取 | 亚群显示顺序（逗号分隔） |
| `--colors` | | 否 | `#4B87B9,#E15759` | 分组色彩 Hex 编码 |
| `--config` | `-c` | 否 | 无 | YAML 配置文件路径 |
| `--title` | `-t` | 否 | 无 | 自定义主标题 |
