# Output schema

The final workbook contains exactly these 5 sheets in layered order:

1. `注释结果总览`
2. `质控与深度审计`
3. `细胞配色`
4. `细胞类型与文献`
5. `说明与数据来源`

## 1. 注释结果总览

One row per cluster. Scannable primary summary table for fast biological & QC review (exactly 10 columns, matching `qualitative_annotation_workbook.py`):

1. `Cluster`
2. `中文名称`
3. `Celltype_EN`
4. `大类谱系`
5. `细胞状态`
6. `质控结论`（`保留` / `建议过滤` / `建议复核`）
7. `关键 Marker`（Top 5-6 symbols）
8. `核心定量摘要`（Top 3 compact metrics, e.g. `FGFBP2(mean=4.7, log2FC=1.7, 70.2%/14.3%)`, omitting `NA` fields）
9. `UMAP 拓扑位置`
10. `核心判定依据`（Concise single-line verdict）

- **Visual Highlight**: Soft coral red fill `#FFFDE8E8` with dark red bold text `#9C0006` is applied to `中文名称` and `质控结论` on warning/filtered clusters; mint green fill `#FFE6F4EA` with dark green bold text `#137333` is applied to `质控结论` (`保留`) on clean clusters.
- **Freeze Panes**: Frozen at `D2` (columns A-C: Cluster, 中文名称, Celltype_EN stay visible during horizontal scrolling).

## 2. 质控与深度审计

One row per cluster. Deep technical audit, gate status, and full quantitative marker evidence (exactly 11 columns):

1. `Cluster`
2. `中文名称`
3. `Celltype_EN`
4. `质控结论`
5. `定性门控审计`
6. `主要竞争候选(Top3)`（Capped at top 3 within-parent siblings）
7. `完整支持 Marker 定量`（Full precision without `mean=NA` or duplicate `ratio=`/`pct.1=`, e.g. `FGFBP2(mean=4.67, log2FC=1.74, pct=70.20%/14.30%)`）
8. `阴性排除验证`
9. `异常/边界标记`（Humanized Chinese labels such as `正常纯群`, `疑似双细胞`, `跨谱系污染`）
10. `可能组成`
11. `证据缺口与复核说明`

- **No numeric scoring / advice columns**: Neither `注释结果总览` nor `质控与深度审计` contains score, confidence, rank, `验证建议`, or `下游处理建议`.
- **Freeze Panes**: Frozen at `D2`.

## 3. 细胞配色

Standard 2-column cell type color mapping sheet:

1. `细胞类型`: Distinct `Celltype_EN` values appearing in the annotation.
2. `色号`: Publication-grade HEX color codes (e.g., `#4DAF4A`) with luminance-adaptive contrast text.
- **Freeze Panes**: Frozen at `A2`.

## 4. 细胞类型与文献

Publication-grade 7-column grounded literature registry:

1. `细胞类型(Celltype_EN)`
2. `文献标识 (DOI/PMID)`: Physical DOI / PMID locator with clickable hyperlink.
3. `文献来源与标题`: First author, year, journal, and paper title.
4. `研究物种与组织`: Species and tissue context.
5. `权威经典标记 (Classic Markers)`: Benchmark markers from literature.
6. `本次鉴定使用的主要 Marker (Sample Evidence)`: Sample markers verified in current data.
7. `核心生物学论证与功能定位`: Rigorous biological functional argument.

- One cell type x one reference is one row. Do not merge cells.
- Clickable hyperlinks on Column 2 (`文献标识 (DOI/PMID)`).
- **Freeze Panes**: Frozen at `B2`.

## 5. 说明与数据来源

2-column table (`项目 | 内容`) providing biological, project-level QC background, and methodological context:
- Records project name, species, tissue, annotation level, parent population context, input file basenames, project-wide QC background notes (`项目共性背景与质控说明`), quantitative metrics definitions, styling guide, cluster count, and skill version.
- **Freeze Panes**: Frozen at `A2`.

## Shared Table Styling & QA Contract

- Font: `Cambria 11` across all sheets.
- Header row: Navy fill `#FF1F4E79`, white bold centered text, height 26 pt.
- Data rows: Alternating zebra fill `#FFF7F9FC`, fixed row height 24 pt (`22 pt` on `细胞配色`), `wrap_text=False`, `shrink_to_fit=False` on every cell to avoid row-height explosion.
- AutoFilter: Strictly disabled (`auto_filter.ref is None`) on all worksheets.
- Order: Numerical ascending order on `Cluster` (0, 1, 2, ... 10).

## 交付产物规范 (Delivery Artifacts Specification)

最终向用户数据目录交付的文件固定且仅保留两个：
1. **时间戳注释大表**：`{project_name}_大类注释结果_{YYYYMMDD_HHMMSS}.xlsx`，严格包含上述 5 个分层 sheet 及其无换行紧凑格式契约。
2. **简明对应关系表**：`cluster注释信息.xlsx`，仅含 `Cluster`, `Celltype_EN`, `中文名称` 3 列，无 AutoFilter，冻结 A2，自适应列宽。
- **杜绝冗余无时间戳大表**：严禁在数据目录下交付或保留 `{project_name}_大类注释结果.xlsx`。
- **绝对纯净**：严禁在用户目录下生成或遗留任何中间过程文件（如 `build/`、`scratch/`、`*.json`、`*.py`、`*.qa.json` 等）。
