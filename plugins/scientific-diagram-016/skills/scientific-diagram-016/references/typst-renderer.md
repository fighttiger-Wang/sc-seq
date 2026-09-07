# Fixed Typst/CeTZ renderer

Use this route only when the content fits the fixed three-group scientific card grammar. Its purpose is stable composition, not arbitrary graph layout.

## Input

Start from `tests/study-design-example.json`. Keep exactly:

- three groups;
- two comparison labels;
- two hub comparison lines;
- three analysis modules;
- one concise outcome statement.

Shorten scientifically redundant wording before rendering. Do not modify geometry to accommodate paragraphs.

## Execution

```bash
python scripts/render_typst_variants.py spec.json output --stem study-design --typst /path/to/typst
```

The compiler must report exactly Typst `0.13.1`. Packages are loaded only from `assets/typst-packages`, containing CeTZ `0.3.4` and its vendored dependency. The script accepts `--typst`, then `TYPST_BIN`, then an executable named `typst` on `PATH`; it never scans the whole computer or downloads software.

The selected font must be an installed open-source Chinese font in this order: `Noto Sans SC`, `Source Han Sans`, `Noto Sans CJK SC`. A different font may be requested explicitly only when it is redistributable and has been visually tested. Do not bundle Microsoft fonts.

## Outputs

The renderer creates:

- `<stem>.desktop.typ` and `<stem>.desktop.svg`;
- `<stem>.mobile.typ` and `<stem>.mobile.svg`;
- `<stem>.print.typ` and `<stem>.print.svg`;
- `<stem>.manifest.json` with renderer, font, dimensions, and SHA-256 values.

The SVG finalizer adds `<title>`, `<desc>`, renderer metadata, and a real-text visible concept label. Body glyphs may be vector paths; the `.typ` files are the editable sources.

## Failure contract

Exit code `3` with `status: fallback_required` means the exact compiler or approved font is unavailable. Do not install anything, use Graphviz, or substitute another auto-layout engine. Use the smallest clear fallback: a plain HTML table, numbered steps, or a simple manually authored SVG with direct boxes and arrows.

## QA

Validate all three SVGs, inspect each at its native target, and compile one variant twice to verify stable SHA-256 output. If any text clips, a connector touches a label, the visual center drifts, or title composition fails, shorten the content or use the fallback.
