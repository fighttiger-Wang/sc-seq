# Hypothesis matrix JSON schema

Use the matrix renderer only for qualitative expectations or comparison frameworks. It does not accept numeric values.

```json
{
  "title": "三组预期变化框架",
  "subtitle": "仅表达待检验方向，不表示效应量、显著性或个体变异",
  "disclaimer": "概念示意 · 非项目实测结果",
  "groups": [
    {"name": "对照组", "subtitle": "基础状态"},
    {"name": "模型组", "subtitle": "疾病状态"},
    {"name": "治疗组", "subtitle": "检验是否回调"}
  ],
  "rows": [
    {
      "label": "炎症募集程序",
      "note": "样本级验证",
      "states": ["基线存在", "可能增加", "可能回落"]
    }
  ],
  "footnotes": ["所有方向均需由独立样本统计和实验验证共同确认。"]
}
```

## Constraints

- `groups`: 2–4 items.
- `rows`: 1–6 items.
- Every row must contain exactly one qualitative state per group.
- `title`, group names, row labels, and states are required strings.
- `subtitle`, `disclaimer`, group subtitle, row note, and `footnotes` are optional.
- The renderer wraps long Chinese and Latin text deterministically. Shorten scientifically redundant wording before increasing density.
