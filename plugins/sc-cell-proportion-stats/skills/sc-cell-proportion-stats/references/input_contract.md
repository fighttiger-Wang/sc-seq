# 输入数据规范与契约 (Input Contract)

本技能支持以下三种主流数据输入形式，具备自动字段识别与容错能力：

## 1. 完整 Seurat 分析对象 (`.rds` 或 `.rdata`)
- **适用场景**：上游已完成质控、聚类降维的标准 Seurat 对象。
- **必需字段**：
  - `meta.data$orig.ident` 或自定义样本列（如 `sample`）。
  - `meta.data$seurat_clusters`（若需结合注释表映射细胞类型）。
- **外部参数映射**：
  - 若细胞类型或样本分组尚未写入 `meta.data`，可传入 `--anno` 和 `--group` 参数进行外接映射：
    - `--anno`：包含 `cluster`、`cell_type_major`、`cell_type_fine` 的 Excel 或 TSV。
    - `--group`：包含 `sample`、`group` 的 Excel 或 TSV。

## 2. 单细胞元数据长表 (`metadata.tsv` / `metadata.csv` / `metadata.rds`)
- **适用场景**：集群计算环境下避免传输数 GB 的完整 Seurat 对象，仅提取轻量级 `meta.data`（通常仅几 MB）。
- **核心列规范**：
  - `sample`（字符串）：生物学重复样本唯一标识符，如 `WT_1`, `Placebo_2`。
  - `group`（字符串）：实验分组名称，如 `WT`, `Placebo`, `Treatment`。
  - 细胞类型列（字符串）：如 `cell_type_fine`、`cell_type_major` 或 `seurat_clusters`。

## 3. 预计算样本百分比宽表 (`*_Sample_Percentages.tsv`)
- **适用场景**：直接进行高分绘图，已具有各样本在各亚群中的百分比（%）。
- **格式示例**：
  ```tsv
  sample	group	Cholangiocytes	Hepatocytes	Macrophage	T_cell
  WT_1	WT	36.85	42.10	4.51	2.30
  WT_2	WT	39.12	38.45	3.35	1.85
  Placebo_1	Placebo	1.82	65.40	4.49	4.80
  ```
