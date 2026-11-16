# Input contract

## Expression matrices

Both TSV files must have:

- first column named `gene`;
- unique gene symbols;
- finite numeric expression values in every remaining column.

The cell-type matrix columns must equal the retained cell types after exclusions.

Each sample-matrix column must be named `<full_celltype>_<sample>`. Cell types may contain underscores. Parsing uses the longest matching cell-type prefix, so full source annotations are preserved. Sample order is the order first encountered in the source matrix. Every sample must contain every retained cell type exactly once.

## Gene-module workbook

One row represents one module. By default the first column is the module name and the second column is a gene list separated by commas, semicolons, Chinese commas, or Chinese semicolons. Override column names with `gene_group_column` and `gene_list_column` when needed.

Module row order determines module order. Gene order inside each list determines heatmap row order. Genes must not repeat across modules.

## Cell-type color workbook

Required columns:

- `Celltype`: exact matrix annotation;
- `Hex_Color`: valid hex color.

YAML `celltype_order` takes precedence when supplied and must exactly match all retained color-table cell types. Otherwise optional `Plot_Order` controls order, followed by workbook row order. After exclusions, the color table and cell-type matrix must contain exactly the same cell types.

## YAML behavior

- Relative paths resolve from the YAML file directory.
- `gene_aliases` maps requested workbook symbols to matrix symbols.
- `module_names` optionally supplies one concise display label per workbook row without changing module membership or gene order.
- `exclude_celltypes` is the only source of exclusions.
- Named `sample_colors` and `module_colors` override defaults; missing names receive deterministic palette colors.
- Plot dimensions and fonts are configurable, but the layout algorithm and exactly-two-figure contract remain fixed.
