# Output Schema

Use one row per sample. Recommended user-facing columns:

| Column | Meaning |
| --- | --- |
| 项目号 | Project ID, for example `LC-X20260302026` |
| 客户名 | Customer name |
| 组学方案 | Assay/omics plan |
| 实验物种 | Species |
| 样本数 | Number of samples |
| 测序量 | Sequencing volume |
| 组织 | Tissue source |
| 项目分析路径 | Analysis path |
| 预期捕获细胞数 | Expected captured cells |
| 关注细胞类型 | Concerned cell type; blank or `无` only if source says so |
| 实验前细胞状态质控 | Pre-experiment cell status QC |
| 服务范畴 | Service scope |
| Sample | Sample identifier |
| Estimated number | Estimated number of cells from screenshot |
| Mean reads per cell | Mean reads per cell from screenshot |
| Mean genes per cell | Mean genes per cell from screenshot |
| Reads mapped to genome | Genome mapping rate from screenshot |
| Sequencing saturation | Sequencing saturation from screenshot |
| Cell type | Cell-type annotation summary for the sample |

## Missing Values

Leave cells blank when the source text or screenshots do not provide a reliable value. Do not infer values from related metrics unless the user explicitly asks for derived fields.

## Example Title Parsing

`LC-X20260302026_段前鹏_单细胞转录组(华大C4)-定制分析项目_小鼠_3_100g`

- Project ID: `LC-X20260302026`
- Customer: `段前鹏`
- Omics plan: `单细胞转录组(华大C4)-定制分析项目`
- Species: `小鼠`
- Sample count: `3`
- Sequencing volume: `100g`

