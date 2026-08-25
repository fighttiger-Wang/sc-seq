# Classic scientific-document visual system

Use a centered, paper-like report layout derived from a traditional Chinese scientific study plan. Reuse the layout language, never the reference document's scientific claims or fixed chapter content.

## Design tokens

- Outer screen background: `#eef1f4`
- Paper background: `#ffffff`
- Main text: `#1e2a3a`
- Primary burgundy: `#8b0000`
- Secondary heading: `#2c3e50`
- Muted text: `#5f6f82`
- Section band: `#f8f9fa`
- Table header: `#e9ecef`
- Table border: `#a0aec0`
- Information callout: pale blue with `#2b6cb0` left border
- Warning callout: pale amber with `#9a5b13` left border
- Danger callout: pale red with `#b42318` left border
- Support callout: pale green with `#3f6f52` left border

Use system Chinese fonts. Prefer a readable Song-style serif stack for narrative text and a neutral sans-serif stack for compact labels and interface controls. Quantitative cells should use tabular numerals.

## Layout

- Center one white document column, approximately 1000–1080 px wide, with generous page margins and no fixed sidebar.
- Put the report title at the top, centered, with a burgundy bottom rule.
- Place metadata and compact project indicators directly below the title; keep them document-like rather than dashboard-like.
- Render the contents as an in-flow block near the top. It may use two columns on wide screens and one column on mobile.
- Style chapter headings as a light-gray band with a thick burgundy left rule. Style subsection headings with a restrained dashed bottom rule.
- Keep report sections visually continuous. Avoid separate floating cards for every section.
- On mobile, reduce page padding and let wide tables or wide figures scroll inside their own containers. The page itself must not overflow horizontally.

## Tables and evidence blocks

- Use full grid borders for scientific tables, with centered light-gray headers and top-aligned body cells.
- Allow wrapping by default. Preserve no-wrap only for short numeric or identifier cells when it improves legibility.
- Use blue, amber, red, or green left-border callouts for evidence notes; keep rounded corners modest.
- Findings may use simple bordered panels, but they must read as document summaries rather than KPI cards.

## Figures

- Preserve the original background, palette, labels, and aspect ratio.
- Center figures within the document and place title, interpretation, and source immediately below.
- Use a one- or two-column figure arrangement only when both remain readable.
- Wide heatmaps and networks should scroll within the figure container rather than widening the page.
- Optimize embedded images to a readable maximum dimension and use one native `<dialog>` enlargement viewer.

## Interaction and accessibility

- A thin burgundy reading-progress line is allowed.
- Contents links may update their active state, but the contents block remains in normal document flow.
- Image enlargement must support visible close text, keyboard focus, Escape closing, backdrop closing, descriptive alt text, and focus restoration.
- Keep feedback transitions under 200 ms and respect `prefers-reduced-motion`.
- Do not require network access, web fonts, frameworks, icon libraries, or external CSS.

## Prohibited drift

Do not add a sticky side navigation, navy hero banner, dashboard tiles, dark mode, neon accents, gradients, glow, glass effects, decorative cover imagery, recolored scientific figures, or dense image mosaics.

## QA

Check desktop and 390 px mobile layouts, title wrapping, chapter bands, table overflow, figure distortion, caption readability, contents navigation, keyboard focus, Escape and backdrop dialog closing, print behavior, contrast, clickable citations, and absence of external asset dependencies.
