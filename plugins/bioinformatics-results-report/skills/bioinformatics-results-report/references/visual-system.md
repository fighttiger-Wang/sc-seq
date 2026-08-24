# Visual system

The design is a project-neutral extraction of the accepted light medical report layout. Reuse its visual language, not any prior project's scientific content or fixed sections.

## Design tokens

- Page: `#f4f6f8`
- Panel: `#ffffff`
- Primary navy: `#17365d`
- Accent blue: `#2f6f9f`
- Text: `#172033`
- Muted text: `#607086`
- Border: `#dbe3ec`
- Warning red: `#b42318`
- Warning amber: `#9a5b13`
- Support green: `#3f6f52`

Use system Chinese sans-serif fonts so the standalone report has no external font dependency. Use tabular numerals for quantitative values.

## Layout

- Desktop: centered shell, approximately 245 px sticky contents column, flexible main column, restrained 22 px gap.
- Main hierarchy: navy hero, compact KPI cards, white scientific sections, original-color figures, scrollable tables.
- Mobile: single column; contents becomes a normal block, grids collapse, tables scroll horizontally.
- Keep section order driven by the scientific question. Do not force a fixed chapter list from an earlier report.

## Figures

- Preserve the original background, palette, labels, and aspect ratio.
- Use one or two columns only when figures remain readable. Wide heatmaps and networks should receive a full-width block.
- Put the interpretive caption immediately below the figure.
- Main narrative contains only figures needed for the scientific storyline.
- Optimize embedded images to a readable maximum dimension; do not embed a second lossless copy. The same optimized image may open in a native `<dialog>` viewer.

## Interaction

- A thin reading-progress line may use `transform: scaleX()`.
- Highlight the current contents link with `IntersectionObserver`.
- Use a native `<dialog>` for image enlargement, with visible close text, focus support, Escape handling, and a descriptive alt attribute.
- Do not require network access, JavaScript frameworks, icon libraries, or external CSS.
- Keep feedback transitions under 200 ms and respect `prefers-reduced-motion`.

## Prohibited drift

Do not add dark dashboards, neon accents, gradients, glow, animated backgrounds, glass effects, recolored scientific figures, decorative hero imagery, excessive pills, or stacked image mosaics. Modernity comes from spacing, hierarchy, responsive behavior, navigation, and legibility—not visual noise.

## QA

Check desktop and narrow layouts, title wrapping, table overflow, figure distortion, readable captions, active navigation, keyboard focus, dialog closing, print behavior, contrast, external citation links, and absence of external asset dependencies.
