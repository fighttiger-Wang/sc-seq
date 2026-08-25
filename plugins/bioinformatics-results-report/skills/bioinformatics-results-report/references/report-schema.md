# Report specification schema

Create a UTF-8 JSON file and pass it to `scripts/render_report.py`. Paths are resolved relative to the JSON file unless `base_dir` is supplied.

## Top-level object

```json
{
  "title": "项目结果智能解读报告",
  "subtitle": "基于既有统计结果与可核查文献的综合判读",
  "project_label": "项目结果报告",
  "output_stem": "项目名_生信结果解读报告",
  "base_dir": "E:/path/to/result-folder",
  "meta": [
    {"label": "物种/组织", "value": "Human / tissue"},
    {"label": "分组", "value": "A、B、Control"}
  ],
  "kpis": [
    {"value": "3", "label": "研究分组"}
  ],
  "summary": {
    "lead": "一段不夸大的核心结论。",
    "findings": ["关键结果一", "关键结果二"],
    "limitations": ["限制一"]
  },
  "sections": [],
  "conclusion": "综合结论。",
  "footer": "基于用户提供的既有统计结果生成；未重新计算统计检验。"
}
```

`output_stem` must be a filename-safe stem without `.html`. The renderer appends `_v001`, `_v002`, and so on without overwriting. `base_dir` and all referenced files must remain on the E drive.

## Section

```json
{
  "id": "primary-contrast",
  "eyebrow": "核心比较",
  "title": "主要生物学差异",
  "lead": "本节解决的科学问题。",
  "blocks": []
}
```

IDs must be unique ASCII lower-case hyphen-case. Section order determines the contents and narrative order.

## Blocks

### Paragraph

```json
{
  "type": "paragraph",
  "text": "结果显示……结合既往研究，这一变化可能反映……",
  "citations": [
    {"label": "Author 2024 / Journal", "url": "https://doi.org/..."}
  ]
}
```

Text is escaped as plain text. Use separate paragraph blocks instead of embedding HTML.

### Heading

```json
{"type": "heading", "text": "机制解释"}
```

### Callout

```json
{
  "type": "callout",
  "tone": "info",
  "title": "判读要点",
  "text": "需要强调的证据或限制。"
}
```

Allowed tones: `info`, `warning`, `danger`, `success`.

### Findings grid

```json
{
  "type": "findings",
  "items": [
    {"value": "↑", "title": "变化方向", "text": "解释"},
    {"value": "FDR < 0.05", "title": "统计支持", "text": "来自现有表格"}
  ]
}
```

### List

```json
{"type": "list", "ordered": false, "items": ["条目一", "条目二"]}
```

### Image

```json
{
  "type": "image",
  "path": "figures/result.png",
  "alt": "描述图中比较对象和指标",
  "title": "图题",
  "caption": "先说明图显示什么，再解释其生物学含义。",
  "source": "result.png",
  "layout": "normal",
  "pdf_page": 1
}
```

Allowed layouts: `normal`, `wide`. For PDF, `pdf_page` is 1-based. The renderer embeds one optimized raster image; it does not retain an additional lossless copy.

### Image grid

```json
{
  "type": "image-grid",
  "images": [
    {"path": "a.png", "alt": "A", "title": "A", "caption": "..."},
    {"path": "b.png", "alt": "B", "title": "B", "caption": "..."}
  ]
}
```

Use only when the pair answers one scientific question and both remain readable.

### Table

```json
{
  "type": "table",
  "title": "核心统计结果",
  "columns": ["指标", "方向", "效应", "FDR"],
  "rows": [["GeneA", "上调", "1.20", "0.003"]],
  "note": "仅展示与正文结论直接相关的结果。"
}
```

Tables are escaped and horizontally scrollable. Keep the main report concise; do not paste complete workbooks.

## Rendering

```bash
python scripts/render_report.py report-spec.json --template assets/report-shell.html
python scripts/validate_report.py /path/to/result/项目名_生信结果解读报告_v001.html
```

Use the bundled workspace Python when system Python is unavailable. The renderer requires Pillow for image optimization and uses `pdftoppm` for PDF pages when available.
