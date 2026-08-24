# Input JSON Schema

Use a JSON object with these fields:

```json
{
  "title": "单细胞转录组 QC 项目汇总",
  "subtitle": "可选副标题",
  "columns": ["项目号", "客户名", "Sample"],
  "rows": [
    {
      "项目号": "LC-X20260302026",
      "客户名": "段前鹏",
      "Sample": "WT"
    }
  ]
}
```

`columns` is optional. If omitted, the script uses the default single-cell QC column order.

`rows` is required and should contain one object per Sample. Missing columns are rendered as blank.

Recommended project-level fields:

- 项目号
- 客户名
- 组学方案
- 实验物种
- 样本数
- 测序量
- 组织
- 组织消化方案
- 预期捕获细胞数
- 关注细胞类型
- 实验前细胞状态质控
- 服务范畴

Recommended sample-level fields:

- Sample
- Estimated number
- Mean reads per cell
- Mean genes per cell
- Reads mapped to genome
- Sequencing saturation
- Cell type

If a value is not captured from text or images, use an empty string.
