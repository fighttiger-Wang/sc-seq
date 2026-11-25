#!/usr/bin/env python3
"""Regression test for the qualitative major-celltype workbook contract."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


SKILL = Path(__file__).resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    repo = next((parent for parent in Path(__file__).resolve().parents if (parent / "skill-pack.json").is_file()), None)
    skill = repo / "plugins" / "sc-major-celltype-annotation-auto" / "skills" / "sc-major-celltype-annotation-auto"
    sys.path.insert(0, str(skill / "scripts"))
    from qualitative_annotation_workbook import validate_workbook_content
    evidence = {
        "clusters": ["10", "2", "0"], "average_shape": [12, 3], "average_reader": "test",
        "confirmed_metadata": {"species": "Human", "tissue": "lung", "annotation_level": "major", "parent_population": "All_cells"},
        "source_paths": {"cell_avg_exp": "avg.tsv", "marker_table": "markers.xlsx"},
        "cluster_profiles": {
            "0": {"top_markers": [{"gene": "EPCAM", "mean_expr": 3.0, "pct1": 0.8, "pct2": 0.1, "log2FC": 2.0}]},
            "2": {"top_markers": [{"gene": "TRAC", "mean_expr": 2.5, "pct1": 0.7, "pct2": 0.05, "log2FC": 1.8}]},
            "10": {"top_markers": [{"gene": "NCR1", "mean_expr": 2.8, "pct1": 0.65, "pct2": 0.03, "log2FC": 2.1}]},
        },
        "qualitative_annotation_evidence": {
            "0": {"stable_id": "Epithelial_cell", "qualitative_gates": {"identity_anchor": "通过"}},
            "2": {"stable_id": "T_cell", "qualitative_gates": {"identity_anchor": "通过"}},
            "10": {"stable_id": "NK_cell", "qualitative_gates": {"identity_anchor": "通过"}},
        },
    }
    rows = [("10", "NK细胞", "NK_cell", "NCR1"), ("2", "T细胞", "T_cell", "TRAC"), ("0", "上皮细胞", "Epithelial_cell", "EPCAM")]
    records = [{
        "cluster_id": cluster, "celltype_cn": cn, "celltype_en": en, "stable_id": en,
        "broad_type": en, "supporting_markers": marker, "candidate_labels": en,
        "rationale": "Qualitative multi-marker program retained.",
        "review_action": "Retain identity and verify on UMAP.",
        "literature_source": "Curated Cell Ontology reference",
    } for cluster, cn, en, marker in rows]
    by_cluster = {record["cluster_id"]: record for record in records}
    by_cluster["2"].update(review_status="conditional", downstream_eligible=False, exclusion_markers=["EPCAM"])
    by_cluster["10"].update(suspected_doublet=True, exclusion_markers=["EPCAM"])
    records.extend([
        dict(by_cluster["0"], cluster_id="11", literature_details=[
            {"title": "Later cluster candidate", "doi": "10.1000/major.later"},
        ]),
        dict(by_cluster["10"], cluster_id="12", celltype_en="Multi_cell", celltype_cn="多细胞污染",
             stable_id="Multi_cell", broad_type="Multi_cell"),
    ])
    evidence["clusters"].extend(["11", "12"])
    evidence["average_gene_names"] = [
        "EPCAM", "TRAC", "NCR1", "Lyve1", "Cd14", "RT1-Db1", "mpeg1.1", "H2-Aa",
        "RareDeg", "ExtraSupport", "RareDeg2", "RareDeg3", "Fallback1", "Fallback2", "WrongFallback",
    ]
    evidence["canonical_expression_by_gene"] = {"Lyve1": [0, 0, 2.1, 0, 0]}
    by_cluster["0"]["key_markers"] = [{"gene": "RareDeg", "p_in": 0.6}, {"gene": "CD14"}, {"gene": "GhostGene"}]
    by_cluster["0"]["supporting_markers"] = [
        {"gene": "EXTRASUPPORT"}, {"gene": "RT1-DB1"}, {"gene": "RareDeg2"}, {"gene": "RareDeg3"},
    ]
    by_cluster["0"]["celltype_cn"] = "仅用于紧凑简表宽度测试的上皮细胞中文名称示例"
    evidence["cluster_profiles"]["0"]["top_markers"].append({"gene": "WrongFallback"})
    evidence["cluster_profiles"]["0"]["top_informative_markers"] = [{"gene": "Fallback1"}, {"gene": "Fallback2"}]
    records[-2]["key_markers"] = "MPEG1.1、GhostGene；RareDeg"
    records[-2]["supporting_markers"] = ""
    evidence["cluster_profiles"]["11"] = {
        "top_informative_markers": [{"gene": "Fallback1"}, {"gene": "Fallback2"}],
    }
    by_cluster["0"]["literature_details"] = [
        {"title": "Adopted epithelial reference", "url": "https://example.org/major/adopted",
         "supported_program": "IFIT 家族；LYVE1、Cd14; CD11b（分型）, RT1-Db1；mpeg1.1、H2-Aa; CFAP genes; MHC-II"},
        {"title": "Other epithelial candidate", "doi": "10.1000/major.other"},
    ]
    ep, rp, output = work / "evidence.json", work / "records.json", work / "major.xlsx"
    ep.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    rp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    completed = subprocess.run([
        sys.executable, str(skill / "scripts" / "build_annotation_workbook.py"),
        "--records", str(rp), "--evidence", str(ep), "--output", str(output),
        "--workspace-root", str(work.parents[1]), "--force",
    ], text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    workbook = load_workbook(output)
    assert workbook.sheetnames == ["注释结果总览", "质控与深度审计", "细胞配色", "细胞类型与文献", "说明与数据来源"]
    for sheet, widths in zip(workbook.worksheets, (
        [10, 22, 26, 16, 18, 11, 30, 40, 28, 44], [10, 22, 26, 11, 32, 28, 42, 28, 18, 24, 36],
        [26, 14], [26, 32, 40, 22, 32, 42, 44], [30, 58],
    )):
        assert [sheet.column_dimensions[get_column_letter(i)].width for i in range(1, sheet.max_column + 1)] == widths
    for sheet_name in ("注释结果总览", "质控与深度审计"):
        assert [workbook[sheet_name].cell(row, 1).value for row in range(2, 5)] == ["0", "2", "10"]
        headers = [cell.value for cell in workbook[sheet_name][1]]
        assert "质量评分" not in headers and "置信度" not in headers and "验证建议" not in headers and "下游处理建议" not in headers
    for sheet_name in ("注释结果总览", "质控与深度审计"):
        sheet = workbook[sheet_name]
        headers = {cell.value: cell.column for cell in sheet[1]}
        for row, verdict, fill, font in (
            (2, "保留", "FFE6F4EA", "137333"),
            (3, "复核", "FFF3F4F6", "374151"),
            (4, "建议过滤", "FFFDE8E8", "9C0006"),
        ):
            cell = sheet.cell(row, headers["质控结论"])
            assert (cell.value, cell.fill.fgColor.rgb, cell.font.color.rgb[-6:]) == (verdict, fill, font)
    assert sheet.cell(3, headers["阴性排除验证"]).value.startswith("已排除: ")
    assert sheet.cell(4, headers["阴性排除验证"]).value.startswith("跨谱系冲突: ")
    assert workbook["细胞配色"].max_row == 5
    assert [cell.value for cell in workbook["注释结果总览"]["C"][1:]].count("Epithelial_cell") == 2
    literature = workbook["细胞类型与文献"]
    assert [cell.value for cell in literature["A"][1:]] == ["Epithelial_cell", "T_cell", "NK_cell", "Multi_cell"]
    assert literature["C2"].value == "Adopted epithelial reference"
    assert literature["B2"].hyperlink.target == "https://example.org/major/adopted"
    assert "质控过滤指标" in literature["B5"].value
    summary = workbook["注释结果总览"]
    assert summary["G2"].value == "Lyve1, Cd14, RT1-Db1, EPCAM, RareDeg, ExtraSupport"
    assert summary["G5"].value == "mpeg1.1, RareDeg, Fallback1, Fallback2"
    assert literature["E2"].value == "LYVE1, Cd14, RT1-Db1, mpeg1.1, H2-Aa"
    assert literature["F2"].value == "Lyve1, Cd14, RT1-Db1, EPCAM, mpeg1.1, RareDeg, ExtraSupport, RareDeg2"
    validate_workbook_content(workbook, evidence=evidence)
    for cell, bad_values in (
        (literature["E2"], ("IFIT 家族", "CD11b（分型）", "MHC-II", "CFAP genes", "IFIT_family", "f4/80")),
        (literature["F2"], ("GhostGene",)),
        (summary["G2"], ("GhostGene", "LYVE1", "Lyve1,Cd14")),
    ):
        original = cell.value
        for bad in bad_values:
            cell.value = bad
            try:
                validate_workbook_content(workbook, average_gene_names=evidence["average_gene_names"])
            except ValueError as exc:
                assert cell.coordinate in str(exc) and bad in str(exc), exc
            else:
                raise AssertionError(f"Accepted invalid marker content {bad!r} at {cell.coordinate}")
        cell.value = original
    assert all(sheet.auto_filter.ref is None for sheet in workbook.worksheets)
    assert all(not cell.alignment.wrap_text for sheet in workbook.worksheets for row in sheet.iter_rows() for cell in row)
    qa = json.loads(output.with_suffix(".qa.json").read_text(encoding="utf-8"))
    assert qa["aggregate_scores_exported"] is False and qa["confidence_exported"] is False
    delivered = work / "delivered"
    copy = subprocess.run([
        sys.executable, str(skill / "scripts" / "copy_final_workbook.py"),
        "--source", str(output), "--workspace-root", str(work.parents[1]),
        "--destination", str(delivered),
    ], capture_output=True, encoding="utf-8")
    assert copy.returncode == 0, copy
    brief = load_workbook(delivered / "cluster注释信息.xlsx")
    assert [brief.active.column_dimensions[col].width for col in "ABC"] == [10, 18, 32]
    assert brief.active["C2"].value == by_cluster["0"]["celltype_cn"]
    brief.close()

    duplicate_source = work / "duplicate_literature.xlsx"
    workbook["细胞类型与文献"].cell(3, 1).value = "Epithelial_cell"
    workbook.save(duplicate_source)
    qa["workbook_sha256"] = hashlib.sha256(duplicate_source.read_bytes()).hexdigest()
    duplicate_source.with_suffix(".qa.json").write_text(json.dumps(qa), encoding="utf-8")
    rejected_destination = work / "rejected_literature" / duplicate_source.name
    duplicate_copy = subprocess.run([
        sys.executable, str(skill / "scripts" / "copy_final_workbook.py"),
        "--source", str(duplicate_source), "--workspace-root", str(work.parents[1]),
        "--destination", str(rejected_destination),
    ], capture_output=True, encoding="utf-8")
    assert duplicate_copy.returncode == 2, duplicate_copy
    error = json.loads(duplicate_copy.stdout)["error"]
    assert "重复 ['Epithelial_cell']" in error and "缺少 ['T_cell']" in error, error
    assert not rejected_destination.parent.exists()

    # Regression test: Hierarchy consistency check (Ancestor-Descendant Exclusion)
    conflict_records = [
        {"cluster_id": "0", "celltype_cn": "上皮细胞", "celltype_en": "Epithelial_cell", "rationale": "ok"},
        {"cluster_id": "1", "celltype_cn": "纤毛细胞", "celltype_en": "Ciliated_cell", "rationale": "ok"}
    ]
    conflict_rp = work / "records_conflict.json"
    conflict_output = work / "major_conflict.xlsx"
    conflict_evidence = {
        "clusters": ["0", "1"],
        "confirmed_metadata": {"species": "Human", "tissue": "lung", "annotation_level": "major", "parent_population": "All_cells"}
    }
    (work / "evidence_conflict.json").write_text(json.dumps(conflict_evidence), encoding="utf-8")
    conflict_rp.write_text(json.dumps(conflict_records), encoding="utf-8")
    res_conflict = subprocess.run([
        sys.executable, str(skill / "scripts" / "build_annotation_workbook.py"),
        "--records", str(conflict_rp), "--evidence", str(work / "evidence_conflict.json"),
        "--output", str(conflict_output), "--workspace-root", str(work.parents[1]), "--force",
    ], text=True, capture_output=True)
    assert res_conflict.returncode != 0, "Expected hierarchy conflict to raise error!"
    assert "Hierarchy consistency violation in major delivery" in (res_conflict.stdout + res_conflict.stderr)

    print(json.dumps({"status": "pass", "checks": 13, "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
