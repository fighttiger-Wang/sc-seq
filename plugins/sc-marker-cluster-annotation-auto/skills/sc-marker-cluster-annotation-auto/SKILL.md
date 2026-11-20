---
name: sc-marker-cluster-annotation-auto
description: Expert-style subcluster annotation within a declared parent population using average expression, detection ratio, marker statistics, UMAP topology, tissue/species context, and versioned literature verification.
---

# Subcluster annotation

Before making any annotation decision, apply the bundled [universal annotation contract](references/annotation-universal-contract.md). This versioned copy is included in the plugin so an installed cache does not depend on a marketplace checkout outside its package. This skill adds the parent-restricted sibling-level rules below; it does not replace the shared evidence, UMAP, naming, or workbook QA requirements.

Use this skill only when the supplied dataset is already restricted to one
parent population. Review every cluster at the most specific level supported
by its current evidence, but do not force a fine-grained label when the expert
plotting standard is not reached. Parent-level, unresolved, provisional,
manual-review, merge, or recluster outcomes are valid formal decisions when
the evidence cannot support a defensible subtype.

When the current evidence resolves some clusters to a registered leaf while
other clusters remain at that leaf's parent, preserve the supported leaf only
when its expert plotting verdict is `allow_specific_label`. Otherwise retain a
conservative parent or unresolved label and record the evidence gap. Different
ontology branches may stop at different depths, but a final subcluster mapping
must not co-display an ancestor and its descendant. Resolve that depth conflict
with same-level evidence, an approved residual leaf, or a blocked/recluster
outcome; never hide it in `下位亚类`. States, programs, and disease roles remain
separate fields and must not be concatenated into `Celltype_EN`.

### 严禁偷懒粗化合并与强制精细化命名规范 (Strict Anti-Lumping & Fine-Grained Mandate)
1. **禁止大类泛化与大锅饭合并**：凡在 UMAP 上成簇分布、构成独立拓扑分支（如外突岛、半岛），或具有明确特异 Marker 表达谱的亚群（如神经伴行 ANGPTL7/CDH19、神经束膜屏障 CLDN1/SLC2A1、微钙化调控 MGP、弹力板 ELN 等），**必须在最终交付的 `Celltype_EN`、`中文名称` 以及 `cluster注释信息.xlsx` 主列中直接赋予独立、特异的精细亚型名称**。
2. **严禁利用门控漏洞偷懒**：严禁为了迎合“同名亚群拓扑相邻门控”而将具有不同生物学特异性的多个簇偷懒打包归入同一宽泛标签（例如将多个不同的成纤维亚群全部归入 `Adv2_Structural_Fibroblast`）。
3. **交付主表一致性**：交付的主 Excel 表格（《注释与详细证据》和《cluster注释信息.xlsx》）主列必须直接呈现差异化精细命名，严禁“在正文解释中声称有细分，但大表主列全为同一大类”的脱节行为。

## Inputs

Require species, tissue/organ, parent population, average-expression input,
marker workbook, and a UMAP PNG with readable cluster IDs and legend. The
expression file has `gene`, `group`, `mean_expr`, `expr_ratio`, and `norm_expr`;
`expr_ratio` is detection ratio. Marker statistics may include
`Target_Cluster_mean`, `Other_Cluster_mean`, `log2FC`, `pct.1`, and `pct.2`.
Preserve parent scope and cluster IDs. Final output sorts numeric cluster IDs from small to large, then uses natural alphanumeric order for mixed IDs.

## Decision logic

按需读取：[references/subcluster-decision-logic.md](references/subcluster-decision-logic.md)（逐 cluster 决策 1-8 步、`Boundary behavior`、开放世界研究与身份仲裁；每个 cluster 定标签前必读）。

## Output

按需读取：[references/subcluster-output-contract.md](references/subcluster-output-contract.md)（`Celltype_EN`、四类决策分离、命名字典、红色警示、`下位亚类`、UMAP 几何；构造映射与工作簿前必读）。

## Expert review and retrieval

按需读取：[references/retrieval-and-expert-review-gate.md](references/retrieval-and-expert-review-gate.md)（专家复核门、校准计数、`research_required` 检索与 `--force-research`；正式构表前必读）。

## Delivery and workbook

交付固定为 4-sheet 标准版（`注释与详细证据`、`细胞配色`、`细胞类型与文献`、`说明与数据来源`）加 `cluster注释信息.xlsx`；历史 5-sheet 工作簿仅作只读校验输入，不得新生成。

按需读取：[references/delivery-and-workbook-contract.md](references/delivery-and-workbook-contract.md)（交付目录纯净、环境调用、开放发现保证、Cambria 11 与列宽格式；交付前必读）。

按需读取：[references/output-schema.md](references/output-schema.md)（4-sheet 详细列契约；构表或校验前必读）。

## Blind test

按需读取：[references/blind-test-protocol.md](references/blind-test-protocol.md)（`--blind-test` 流程与盲测约束；执行盲测时必读）。

## Release handoff

发布请调用 /E05-Skill同步发布（A04-知识库发布 负责知识库同步）。

Never output generic `Cell`, mix ancestors and descendants, infer same-cell
coexpression from aggregate data, silently discard off-parent clusters, or
claim confirmed doublet from aggregate-only evidence.
