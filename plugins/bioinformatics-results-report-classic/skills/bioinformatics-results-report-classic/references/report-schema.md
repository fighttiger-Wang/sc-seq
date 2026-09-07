# Report specification schema

Create a UTF-8 JSON file and pass it to `scripts/render_report.py`. Paths are resolved relative to the JSON file unless `base_dir` is supplied.

## Top-level object

```json
{
  "title": "项目结果智能解读报告",
  "subtitle": "基于既有统计结果与可核查文献的综合判读",
  "project_label": "项目结果报告",
  "output_stem": "项目名_生信结果解读报告",
  "base_dir": "/path/to/result-folder",
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

`output_stem` must be a filename-safe stem without `.html`. The renderer appends `_v001`, `_v002`, and so on without overwriting. `base_dir` and all referenced files must remain inside the user-supplied local result folder or another explicitly authorized local path.

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
  "evidence": "DEG.xlsx / T_vs_C / log2FC 与 FDR 列",
  "citations": [
    {"label": "Author 2024 / Journal", "url": "https://doi.org/..."}
  ]
}
```

Text is escaped as plain text. Use separate paragraph blocks instead of embedding HTML.
`evidence` is optional but expected for paragraphs carrying a core data claim. Keep it concise and use relative filenames or human-readable table labels, never absolute local paths.

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
  "text": "需要强调的证据或限制。",
  "evidence": "来源表/图与关键字段"
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
  "mobile_path": "figures/result.mobile.svg",
  "print_path": "figures/result.print.svg",
  "alt": "描述图中比较对象和指标",
  "title": "图题",
  "caption": "先说明图显示什么，再解释其生物学含义。",
  "source": "result.png",
  "layout": "normal",
  "authored_concept": false,
  "pdf_page": 1
}
```

Allowed layouts: `normal`, `wide`. For PDF, `pdf_page` is 1-based. `path` is the desktop/default source. `mobile_path` and `print_path` are optional dedicated variants; do not point them to a desktop file that was merely resized. When present, the renderer uses `<picture>` for mobile selection and a print-only source under `@media print`.

Set `authored_concept` to `true` for every workflow, study-design, comparison-framework, hypothesis-matrix, evidence-chain, mechanism, or spatial schematic newly created for the report. Every declared variant must reference a finalized `.svg`; the renderer rejects PNG/JPEG/PDF input even when an older same-stem raster file exists. Each desktop/mobile/print source records its role, relative path, source format, source SHA-256, embedded MIME, embedded SHA-256, and dimensions. `validate_report.py` decodes each data URI and proves the metadata matches the actual embedded bytes.

### Image grid

```json
{
  "type": "image-grid",
  "images": [
    {"path": "a.svg", "alt": "A", "title": "A", "caption": "..."},
    {"path": "b.png", "alt": "B", "title": "B", "caption": "..."}
  ]
}
```

Use only when the pair answers one scientific question and both remain readable.

PNG/JPEG are optimized before embedding. Authored SVG is embedded without rasterization so labels and lines remain sharp in browser zoom and print. SVG must be self-contained and may not contain scripts, event-handler attributes, `foreignObject`, or external file/network references.

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

## Traceability and compatibility

- Core claims should include a visible `evidence` note in the nearest paragraph or callout.
- Summary `findings` may be plain strings or objects such as `{"text": "核心发现", "evidence": "来源表/图"}`.
- Do not include absolute paths, customer identifiers, or raw sample IDs in the specification's visible text.
- The renderer accepts the earlier string-only summary form for compatibility, but new reports should use evidence-bearing objects for the most important findings.

## Rendering

```powershell
python scripts/render_report.py report-spec.json --template assets/report-shell.html
python scripts/validate_report.py /path/to/result/项目名_生信结果解读报告_v001.html
```

Use the bundled workspace Python when system Python is unavailable. The renderer requires Pillow for image optimization and uses `pdftoppm` for PDF pages when available.
