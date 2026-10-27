# Output schema

The final workbook contains exactly these 4 sheets in order:

1. `注释与详细证据`
2. `细胞配色`
3. `细胞类型与文献`
4. `说明与数据来源`

## 1. 注释与详细证据

One row per cluster. Deduplicated merge of annotation results and detailed evidence into a single primary table (exactly 18 columns, matching `qualitative_annotation_workbook.py`):

1. `Cluster`
2. `中文名称`
3. `Celltype_EN`
4. `细胞谱系`
5. `发育/成熟阶段`
6. `细胞状态`
7. `组织/疾病相关角色`
8. `关键 Marker`
9. `支持 Marker 证据`
10. `冲突/缺失 Marker`
11. `主要身份程序`
12. `主要竞争候选`
13. `定性门控审计`
14. `UMAP 判断摘要`
15. `异常/边界标记`
16. `可能组成`
17. `判定依据与论证`
18. `证据缺口`

- **No numeric scoring / advice columns**: Contains no score, confidence, rank, `验证建议`, or `下游处理建议`.
- **Gene formatting**: `关键 Marker` contains gene symbols only. Supporting evidence formats values as:
  ```text
  FGFBP2(mean=4.67, ratio=70.20%, log2FC=1.74, pct.1=70.20%, pct.2=14.30%)
  ```
- **Visual Warning**: Static red fill `#FFF8696B` is applied only to `中文名称` when a cluster carries a significant state program, is `Multi_cell`, suspected doublet, low quality, debris, ambient contamination, or lineage boundary.
- **Freeze Panes**: Frozen at `D2` (columns A-C: Cluster, 中文名称, Celltype_EN stay visible during horizontal scrolling).

## 2. 细胞配色

Standard 2-column cell type color mapping sheet:

1. `细胞类型`: Distinct `Celltype_EN` values appearing in the annotation.
2. `色号`: Publication-grade HEX color codes (e.g., `#4DAF4A`).
   - Cell text value is the pure HEX string.
   - Cell background is rendered with the corresponding color fill preview.
   - Text color dynamically adjusts (white/black) based on background luminance for optimal contrast.
- **Freeze Panes**: Frozen at `A2`.

## 3. 细胞类型与文献

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

## 4. 说明与数据来源

2-column table (`项目 | 内容`) providing biological and methodological context:
- Records tissue, species, parent population context, input file names (basenames only), quantitative metrics definitions, cluster count, and analytical limitations.
- Excludes tool version numbers, execution timestamps, red-fill logic declarations, and disclaimer clauses.
- **Freeze Panes**: Frozen at `A2`.

## Shared Table Styling & QA Contract

- Font: `Cambria 11` across all sheets.
- Header row: Grey header fill (`#D9D9D9` or `#F2F2F2`), thin bottom border, bold text, height 24 pt.
- Data rows: Row height 22-24 pt, left-aligned text, centered Cluster and Color codes.
- AutoFilter: Strictly disabled (`auto_filter.ref is None`) on all worksheets.
- Order: Numerical ascending order on `Cluster` (0, 1, 2, ... 10).

## 交付产物规范 (Delivery Artifacts Specification)

最终向用户数据目录交付的文件固定且仅保留两个：
1. **时间戳注释大表**：`{project_name}_亚群注释结果_{YYYYMMDD_HHMMSS}.xlsx`，严格包含上述 4 个 sheet 及其格式契约。
2. **简明对应关系表**：`cluster注释信息.xlsx`，仅含 `Cluster`, `Celltype_EN`, `中文名称` 3 列，无 AutoFilter，冻结 A2，自适应列宽。
- **杜绝冗余无时间戳大表**：严禁在数据目录下交付或保留 `{project_name}_亚群注释结果.xlsx`。
- **绝对纯净**：严禁在用户目录下生成或遗留任何中间过程文件（如 `build/`、`scratch/`、`*.json`、`*.py`、`*.qa.json` 等）。
