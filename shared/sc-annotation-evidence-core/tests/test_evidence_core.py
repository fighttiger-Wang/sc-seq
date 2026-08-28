#!/usr/bin/env python3
"""Regression tests for annotation-depth projection and conservative risks."""

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotation_evidence_core import compose_display_label, enrich_evidence, score_panel  # noqa: E402
from knowledge_base import build_runtime_config, load_knowledge_base  # noqa: E402


PANELS = {
    "epi": ["EPCAM", "KRT8", "KRT18", "KRT19"],
    "endo": ["PECAM1", "CDH5", "VWF", "KDR"],
    "mono": ["LYZ", "LST1", "TYROBP", "FCER1G"],
    "macro": ["C1QA", "C1QB", "C1QC", "MERTK"],
    "t": ["CD3D", "CD3E", "CD3G", "TRAC"],
    "nk": ["NKG7", "KLRD1", "NCR1", "GNLY"],
    "cd4_th17": ["CD3D", "CD3E", "TRAC", "CD4", "CD40LG", "RORC", "CCR6", "IL17A", "IL17F", "IL23R", "RORA"],
    "cd4_branch": ["CD4", "CD40LG"],
    "cd4_tem": ["CD44", "IL7R", "IFNG", "TNFSF8", "TNFSF11", "TNFRSF4", "IL21"],
    "cd8_branch": ["CD8A", "CD8B1"],
    "exhaustion": ["TOX", "PDCD1", "LAG3", "HAVCR2", "TIGIT", "ENTPD1"],
    "naive_t": ["TCF7", "LEF1", "CCR7", "SELL", "IL7R", "KLF2", "BCL2", "SATB1"],
    "gdt_partial": ["TRDC", "TRGC1"],
    "gdt_anchors": ["TRDC", "TRGC1", "TRGC2"],
    "gdt_naive": ["TCF7", "LEF1", "SELL", "CCR7", "KLF2", "IL7R", "BCL2", "SATB1"],
    "gdt_il17": ["IL17A", "IL23R", "RORC", "RORA", "ZBTB16", "SCART1", "CCR6", "IL17F", "IL1R1"],
    "mait_shared": ["SLC4A10", "KLRB1", "ZBTB16", "NCR3"],
    "mait_tcr": ["TRAV1-2"],
    "ose": ["KRT8", "KRT18", "EPCAM"],
    "ta": ["MKI67", "TOP2A", "PCNA"],
    "neuroendocrine": ["CHGA", "CHGB", "SYP", "GAST"],
}


def evidence(clusters):
    return {
        "clusters": list(clusters),
        "cluster_profiles": {
            cluster: {"top_markers": [], "qc_state_fraction_top50": 0.0} for cluster in clusters
        },
    }


def write_ratios(path, programs):
    genes = sorted({gene for panel in PANELS.values() for gene in panel})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "group", "expr_ratio", "mean_expr"])
        for cluster, active in programs.items():
            active_genes = {gene for name in active for gene in PANELS[name]}
            for gene in genes:
                writer.writerow([gene, cluster, 0.80 if gene in active_genes else 0.01, 2.0 if gene in active_genes else 0.0])


def write_ratio_values(path, cluster_values):
    genes = sorted({gene for values in cluster_values.values() for gene in values})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene", "group", "expr_ratio", "mean_expr"])
        for cluster, values in cluster_values.items():
            for gene in genes:
                ratio = float(values.get(gene, 0.01))
                writer.writerow([gene, cluster, ratio, ratio * 3.0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)

    split_path = work / "split.tsv"
    split_programs = {"0": ["epi"], "1": ["endo"], "2": ["t"], "3": ["nk"]}
    write_ratios(split_path, split_programs)
    split = enrich_evidence(evidence(split_programs), ratio_path=split_path, annotation_level="major", tissue="blood")
    decisions = split["deterministic_annotation_evidence"]
    assert decisions["0"]["primary_major_label"] == "Epithelial_cell"
    assert decisions["1"]["primary_major_label"] == "Endothelial_cell"
    assert decisions["2"]["tnk_provisional"] == "T_supported"
    assert decisions["3"]["tnk_provisional"] == "NK_supported"
    assert split["deterministic_tnk_arbitration"]["recommended_regime"] == "per_cluster"
    assert decisions["2"]["auto_merge_allowed"] is True

    same_major_path = work / "same_major.tsv"
    same_programs = {"0": ["mono", "macro"], "1": ["epi"], "2": ["endo"]}
    write_ratios(same_major_path, same_programs)
    major = enrich_evidence(evidence(same_programs), ratio_path=same_major_path, annotation_level="major", tissue="blood")
    sub = enrich_evidence(evidence(same_programs), ratio_path=same_major_path, annotation_level="subcluster", tissue="blood")
    assert major["deterministic_annotation_evidence"]["0"]["primary_major_label"] == "Myeloid_cell"
    assert major["deterministic_annotation_evidence"]["0"]["risk_level"] == "R0_ACCEPT"
    assert sub["deterministic_annotation_evidence"]["0"]["risk_level"] in {"R0_ACCEPT", "R1_REVIEW_RETAIN"}

    # N135-derived myeloid boundary regression: an isolated CSF3R/FCGR3B
    # signal cannot override a complete monocyte program, inflammatory
    # neutrophils require a coherent alternative program, and DC3 remains a
    # cell-level coexpression question rather than a literature-only call.
    myeloid_boundary_path = work / "n135_myeloid_boundaries.tsv"
    myeloid_boundary_values = {
        "3_like": {
            "CSF3R": .59, "FCGR3B": .18, "CXCR2": .06,
            "PI3": .32, "SLPI": .25, "CXCL8": .79,
            "S100A8": .69, "S100A9": .70, "CD14": .24,
            "FCN1": .08, "VCAN": .08, "LST1": .45, "TYROBP": .76,
            "CD1C": .00, "CLEC10A": .004, "FCER1A": .00,
            "HLA-DRA": .14, "HLA-DPA1": .04, "HLA-DPB1": .03, "CD74": .13,
        },
        "4_like": {
            "CSF3R": .91, "FCGR3B": .22, "CXCR2": .11,
            "PI3": .02, "SLPI": .04, "CXCL8": .36,
            "MPO": .02, "ELANE": .006, "PRTN3": .002, "AZU1": .009,
            "DEFA1": .006, "DEFA3": .016, "MS4A3": .014, "CEBPE": .039,
            "PGLYRP1": .037, "LTF": .004, "CAMP": .037, "CD177": .02,
            "CD14": .81, "FCN1": .97, "VCAN": .98, "LST1": .93, "TYROBP": .99,
            "FCGR3A": .45, "S100A8": .99, "S100A9": .99,
            "CD1C": .036, "CLEC10A": .087, "FCER1A": .001,
        },
        "17_like": {
            "HLA-DRA": .99, "HLA-DPA1": .88, "HLA-DPB1": .86, "CD74": .99,
            "CD1C": .11, "CLEC10A": .36, "FCER1A": .11,
            "CD14": .38, "FCN1": .59, "VCAN": .45, "FCGR3A": .50, "LST1": .81,
            "C1QA": .18, "C1QB": .17, "C1QC": .26, "FOLR2": .13,
            "CSF3R": .36, "FCGR3B": .02, "CXCR2": .00,
        },
    }
    write_ratio_values(myeloid_boundary_path, myeloid_boundary_values)
    myeloid_boundary = enrich_evidence(
        evidence(myeloid_boundary_values), ratio_path=myeloid_boundary_path,
        annotation_level="subcluster", species="Human", tissue="fetal lung",
        parent_population="Myeloid_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert myeloid_boundary["3_like"]["stable_id"] == "Neutrophil"
    assert myeloid_boundary["3_like"]["identity_boundary_audit"]["neutrophil_vs_monocyte"]["neutrophil_program_passed"] is True
    assert myeloid_boundary["3_like"]["decision_trace"]["neutrophil_reclassified_to_monocyte"] is False
    assert myeloid_boundary["3_like"]["auto_merge_allowed"] is True
    assert myeloid_boundary["4_like"]["stable_id"] == "Classical_monocyte"
    assert myeloid_boundary["4_like"]["decision_trace"]["neutrophil_reclassified_to_monocyte"] is True
    assert myeloid_boundary["4_like"]["identity_boundary_audit"]["neutrophil_vs_monocyte"]["neutrophil_blocked_by_monocyte"] is True
    assert myeloid_boundary["4_like"]["auto_merge_allowed"] is False
    assert myeloid_boundary["17_like"]["identity_boundary_audit"]["dc3_vs_monocyte"]["dc3_boundary_candidate"] is True
    assert myeloid_boundary["17_like"]["boundary_validation_required"] is True
    assert myeloid_boundary["17_like"]["risk_level"] == "R2_IDENTITY_BOUNDARY_REVIEW"
    assert myeloid_boundary["17_like"]["auto_merge_allowed"] is False
    myeloid_cell_evidence = work / "n135_myeloid_cell_evidence.json"
    myeloid_cell_evidence.write_text(json.dumps({
        "17_like": {
            "identity_boundary_validation": {
                "rule_id": "MYELOID_DC3_VS_MONOCYTE_COEXPRESSION_GATE",
                "coexpression_validated": True,
                "method": "cell-level coexpression plot",
            }
        }
    }), encoding="utf-8")
    myeloid_validated = enrich_evidence(
        evidence(myeloid_boundary_values), ratio_path=myeloid_boundary_path,
        cell_evidence_path=myeloid_cell_evidence,
        annotation_level="subcluster", species="Human", tissue="fetal lung",
        parent_population="Myeloid_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]["17_like"]
    assert myeloid_validated["boundary_validation_required"] is False
    assert myeloid_validated["boundary_validation_resolved"] is True
    assert myeloid_validated["identity_boundary_audit"]["dc3_vs_monocyte"]["cell_level_validated"] is True

    cluster8_path = work / "n135_cluster8_borderline.tsv"
    cluster8_values = {
        "8_like": {
            "CSF3R": .486, "FCGR3B": .093, "CXCR2": .020,
            "PI3": .440, "SLPI": .299, "CXCL8": .867,
            "CD14": .040, "FCN1": .029, "VCAN": .032, "FCGR3A": .018,
            "LST1": .080, "TYROBP": .120,
            "CD83": .748, "ITGAX": .681, "RELB": .120, "XCR1": .172,
            "CLEC9A": .000, "WDFY4": .000, "CADM1": .000,
            "CD1C": .000, "CLEC10A": .000, "FCER1A": .000,
            "CCR7": .000, "FSCN1": .015, "LAMP3": .016,
            "HLA-DRA": .105, "HLA-DPA1": .040, "HLA-DPB1": .030, "CD74": .086,
        },
        "monocyte_reference": {
            "CSF3R": .010, "FCGR3B": .010, "PI3": .020, "SLPI": .030, "CXCL8": .100,
            "CD14": .800, "FCN1": .900, "VCAN": .850, "FCGR3A": .300,
            "LST1": .900, "TYROBP": .900, "CD83": .020, "ITGAX": .030,
        },
    }
    write_ratio_values(cluster8_path, cluster8_values)
    cluster8 = enrich_evidence(
        evidence(cluster8_values), ratio_path=cluster8_path,
        annotation_level="subcluster", species="Human", tissue="fetal lung",
        parent_population="Myeloid_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]["8_like"]
    assert cluster8["stable_id"] == "Neutrophil"
    assert cluster8["risk_level"] == "R1_REVIEW_RETAIN"
    assert cluster8["auto_merge_allowed"] is False
    assert cluster8["identity_boundary_audit"]["neutrophil_vs_monocyte"]["borderline_activated_neutrophil_candidate"] is True
    assert cluster8["identity_boundary_audit"]["neutrophil_vs_monocyte"]["monocyte_program_passed"] is False
    assert cluster8["identity_boundary_audit"]["dc_like_activation"]["passed"] is True
    assert not any(item["passed"] for item in cluster8["identity_boundary_audit"]["dc_identity_programs"].values())
    assert "DC_like" in cluster8["state_list"]

    same_major_cross_module_path = work / "same_major_cross_module.tsv"
    same_major_cross_module_programs = {
        "0": ["ose", "ta"],
        "1": ["neuroendocrine"],
    }
    write_ratios(same_major_cross_module_path, same_major_cross_module_programs)
    same_major_cross_module = enrich_evidence(
        evidence(same_major_cross_module_programs),
        ratio_path=same_major_cross_module_path,
        annotation_level="subcluster",
        species="Human",
        tissue="stomach",
        parent_population="Epithelial_cell",
        parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert same_major_cross_module["0"]["risk_level"] != "R2_RECLUSTER_OR_DOUBLET_REVIEW"
    assert same_major_cross_module["0"]["mixed_population"] is False
    assert same_major_cross_module["0"]["auto_merge_allowed"] is True
    assert same_major_cross_module["1"]["risk_level"] != "R2_RECLUSTER_OR_DOUBLET_REVIEW"
    assert same_major_cross_module["1"]["mixed_population"] is False
    assert same_major_cross_module["1"]["auto_merge_allowed"] is True

    mixed_path = work / "mixed.tsv"
    mixed_programs = {"0": ["mono", "endo"], "1": ["epi"], "2": ["t", "nk"]}
    write_ratios(mixed_path, mixed_programs)
    mixed = enrich_evidence(evidence(mixed_programs), ratio_path=mixed_path, annotation_level="major", tissue="blood")
    assert mixed["deterministic_annotation_evidence"]["0"]["risk_level"] == "R2_RECLUSTER_OR_DOUBLET_REVIEW"
    assert mixed["deterministic_annotation_evidence"]["2"]["tnk_provisional"] == "unresolved_T_NK"
    assert mixed["deterministic_tnk_arbitration"]["recommended_regime"] == "per_cluster"
    assert mixed["deterministic_annotation_evidence"]["2"]["mixed_population"] is True
    assert mixed["deterministic_annotation_evidence"]["2"]["auto_merge_allowed"] is False
    assert mixed["deterministic_annotation_evidence"]["0"]["stable_id"] == "Multi_cell"
    assert mixed["deterministic_annotation_evidence"]["2"]["stable_id"] == "Multi_cell"
    assert mixed["deterministic_annotation_evidence"]["2"]["formal_identity_fallback"] == "multi_cell_annotation"

    t_sublineage_path = work / "t_sublineage_mixed.tsv"
    t_sublineage_programs = {"0": ["cd4_th17", "gdt_partial"], "1": ["t"]}
    write_ratios(t_sublineage_path, t_sublineage_programs)
    t_sublineage = enrich_evidence(
        evidence(t_sublineage_programs), ratio_path=t_sublineage_path,
        annotation_level="subcluster", species="Mouse", tissue="liver tumor",
        parent_population="T_NK", parent_kind="mixed",
    )
    t_sublineage_decision = t_sublineage["deterministic_annotation_evidence"]["0"]
    assert t_sublineage_decision["risk_level"] == "R2_RECLUSTER_OR_DOUBLET_REVIEW"
    assert t_sublineage_decision["mixed_population"] is True
    assert t_sublineage_decision["auto_merge_allowed"] is False
    assert t_sublineage_decision["stable_id"] == "Multi_cell"
    assert t_sublineage_decision["formal_identity_fallback"] == "multi_cell_annotation"
    assert set(t_sublineage_decision["possible_components"]) == {"CD4_Th17", "IL17A_gdT"}
    assert t_sublineage_decision["sublineage_conflict"]["rule_id"] == "CD4_ALPHA_BETA_VS_GAMMA_DELTA_T"

    gdt_subtype_path = work / "gdt_subtypes.tsv"
    gdt_subtype_programs = {
        "0": ["t", "gdt_anchors", "gdt_naive"],
        "1": ["t", "gdt_anchors", "gdt_il17"],
        "2": ["t", "gdt_il17"],
    }
    write_ratios(gdt_subtype_path, gdt_subtype_programs)
    gdt_subtypes = enrich_evidence(
        evidence(gdt_subtype_programs), ratio_path=gdt_subtype_path,
        annotation_level="subcluster", species="Mouse", tissue="ovary;tumor",
        parent_population="T_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert gdt_subtypes["0"]["stable_id"] == "Naive_like_gdT"
    assert gdt_subtypes["0"]["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_GAMMA_DELTA_TCR_ANCHORS"
    assert gdt_subtypes["0"]["decision_trace"]["identity_branch_gate"]["passed"] is True
    assert gdt_subtypes["1"]["stable_id"] == "IL17A_gdT"
    assert gdt_subtypes["1"]["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_GAMMA_DELTA_TCR_ANCHORS"
    assert gdt_subtypes["1"]["decision_trace"]["identity_branch_gate"]["passed"] is True
    assert gdt_subtypes["2"]["stable_id"] != "IL17A_gdT"

    mait_gate_path = work / "mait_tcr_gate.tsv"
    mait_gate_programs = {
        "0": ["t", "mait_shared", "gdt_anchors"],
        "1": ["t", "mait_shared", "mait_tcr"],
        "2": ["t", "mait_shared"],
    }
    write_ratios(mait_gate_path, mait_gate_programs)
    mait_gate = enrich_evidence(
        evidence(mait_gate_programs), ratio_path=mait_gate_path,
        annotation_level="subcluster", species="Human", tissue="fetal lung",
        parent_population="T_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert mait_gate["0"]["stable_id"] == "gdT"
    assert mait_gate["0"]["stable_id"] != "MAIT"
    assert mait_gate["1"]["stable_id"] == "MAIT"
    assert mait_gate["1"]["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_MAIT_CANONICAL_TCR_ANCHOR"
    assert mait_gate["2"]["stable_id"] != "MAIT"

    tn_dnt_path = work / "tn_dnt.tsv"
    tn_dnt_programs = {
        "0": ["t", "naive_t"],
        "1": ["t", "naive_t", "cd4_branch"],
        "2": ["t", "naive_t", "cd8_branch"],
        "3": ["t", "naive_t", "gdt_partial"],
    }
    write_ratios(tn_dnt_path, tn_dnt_programs)
    tn_dnt = enrich_evidence(
        evidence(tn_dnt_programs), ratio_path=tn_dnt_path,
        annotation_level="subcluster", species="Mouse", tissue="ovary;tumor",
        parent_population="T_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert tn_dnt["0"]["stable_id"] == "DNT"
    assert tn_dnt["0"]["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_DOUBLE_NEGATIVE_T_PHENOTYPE"
    assert tn_dnt["0"]["decision_trace"]["identity_branch_gate"]["passed"] is True
    assert tn_dnt["1"]["stable_id"] in {"CD4_T", "CD4_Tn"}
    assert tn_dnt["1"]["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_CD4_ALPHA_BETA_ANCHOR"
    assert tn_dnt["2"]["stable_id"] in {"CD8_T", "CD8_Tn"}
    assert tn_dnt["2"]["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_CD8_ALPHA_BETA_ANCHOR"
    assert tn_dnt["3"]["stable_id"] != "DNT"

    cd4_cd8_path = work / "cd4_cd8_branch.tsv"
    cd4_cd8_programs = {
        "0": ["t", "cd4_branch", "exhaustion"],
        "1": ["t", "cd8_branch", "exhaustion"],
        "2": ["t", "cd4_branch", "cd8_branch", "exhaustion"],
        "3": ["t"],
        "4": ["t"],
        "5": ["t"],
    }
    write_ratios(cd4_cd8_path, cd4_cd8_programs)
    cd4_cd8 = enrich_evidence(
        evidence(cd4_cd8_programs), ratio_path=cd4_cd8_path,
        annotation_level="subcluster", species="Mouse", tissue="ovary;tumor",
        parent_population="T_cell", parent_kind="lineage",
    )
    cd4_decision = cd4_cd8["deterministic_annotation_evidence"]["0"]
    assert cd4_decision["primary_evidence_label"] == "CD4_T"
    assert cd4_decision["stable_id"] == "CD4_T"
    assert cd4_decision["primary_state"] == "Exhausted"
    assert cd4_decision["display_label"] == "CD4_T"
    assert cd4_decision["formal_identity_fallback"] == "branch_identity_no_supported_leaf"
    assert cd4_decision["resolution_search_required"] is True
    assert cd4_decision["decision_trace"]["resolution_search_required"] is True
    assert "targeted subtype-resolution search" in cd4_decision["recommended_action"]
    assert cd4_decision["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_CD4_ALPHA_BETA_ANCHOR"
    assert cd4_decision["decision_trace"]["identity_branch_gate"]["passed"] is True
    cd8_decision = cd4_cd8["deterministic_annotation_evidence"]["1"]
    assert cd8_decision["primary_evidence_label"] == "CD8_T"
    assert cd8_decision["stable_id"] == "CD8_T"
    assert cd8_decision["primary_state"] == "Exhausted"
    assert cd8_decision["display_label"] == "CD8_T"
    assert cd8_decision["formal_identity_fallback"] == "branch_identity_no_supported_leaf"
    assert cd8_decision["resolution_search_required"] is True
    assert cd8_decision["decision_trace"]["identity_branch_gate"]["rule_id"] == "REQUIRE_CD8_ALPHA_BETA_ANCHOR"
    assert cd8_decision["decision_trace"]["identity_branch_gate"]["passed"] is True
    mixed_cd4_cd8 = cd4_cd8["deterministic_annotation_evidence"]["2"]
    assert mixed_cd4_cd8["risk_level"] == "R2_RECLUSTER_OR_DOUBLET_REVIEW"
    assert mixed_cd4_cd8["stable_id"] == "Multi_cell"
    assert mixed_cd4_cd8["formal_identity_fallback"] == "multi_cell_annotation"
    assert mixed_cd4_cd8["auto_merge_allowed"] is False
    assert set(mixed_cd4_cd8["possible_components"]) == {"CD4_T", "CD8_T"}
    assert mixed_cd4_cd8["sublineage_conflict"]["rule_id"] == "CD4_ALPHA_BETA_VS_CD8_ALPHA_BETA_T"

    minimal_tex = evidence(["0"])
    minimal_tex["cluster_profiles"]["0"]["top_markers"] = [
        {"gene": gene, "pct1": 0.80, "pct2": 0.05, "log2FC": 2.0}
        for gene in PANELS["exhaustion"]
    ]
    minimal_tex_decision = enrich_evidence(
        minimal_tex, annotation_level="subcluster", species="Mouse", tissue="ovary;tumor",
        parent_population="T_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]["0"]
    assert minimal_tex_decision["stable_id"] == "T_cell"
    assert minimal_tex_decision["risk_level"] == "R1_REVIEW_RETAIN"

    off_parent_path = work / "off_parent_audit.tsv"
    off_parent_programs = {
        "0": ["nk"],
        "1": ["t"],
        "2": ["t", "nk"],
    }
    write_ratios(off_parent_path, off_parent_programs)
    off_parent = enrich_evidence(
        evidence(off_parent_programs), ratio_path=off_parent_path,
        annotation_level="subcluster", species="Mouse", tissue="ovary;tumor",
        parent_population="T_cell", parent_kind="lineage",
    )
    nk_contaminant = off_parent["deterministic_annotation_evidence"]["0"]
    assert nk_contaminant["stable_id"] == "NK_cell"
    assert nk_contaminant["formal_identity_fallback"] == "off_parent_lineage_reassignment"
    assert nk_contaminant["off_parent_detected"] is True
    assert nk_contaminant["off_parent_reassignment"] is True
    assert nk_contaminant["tnk_provisional"] == "NK_supported"
    assert nk_contaminant["auto_merge_allowed"] is False
    assert nk_contaminant["decision_trace"]["parent_candidate_coherent"] is False
    assert nk_contaminant["primary_evidence_label"] != "NKT"
    expected_t = off_parent["deterministic_annotation_evidence"]["1"]
    assert expected_t["off_parent_detected"] is False
    mixed_parent = off_parent["deterministic_annotation_evidence"]["2"]
    assert mixed_parent["stable_id"] == "Multi_cell"
    assert mixed_parent["formal_identity_fallback"] == "multi_cell_annotation"
    assert mixed_parent["risk_level"] == "R2_RECLUSTER_OR_DOUBLET_REVIEW"
    assert mixed_parent["auto_merge_allowed"] is False

    # N132-B boundary regressions: weak detection must not outweigh a
    # directional sibling program, cycling remains state, and shared EPCAM
    # must not manufacture an epithelial mixture.
    b_boundary_path = work / "n132_b_boundaries.tsv"
    b_values = {
        "naive_case": {
            "CD79A": .70, "CD79B": .65, "EBF1": .72, "PAX5": .68, "MS4A1": .62,
            "IGHM": .707, "IGHD": .442, "FCER2A": .183, "GPR183": .36,
            "AIM2": .139, "TNFRSF13B": .139,
        },
        "memory_reference": {
            "CD79A": .68, "CD79B": .62, "EBF1": .66, "PAX5": .63, "MS4A1": .60,
            "IGHM": .18, "IGHD": .12, "FCER2A": .08, "GPR183": .08,
            "AIM2": .13, "TNFRSF13B": .13,
        },
        "cycling_immature": {
            "CD79A": .74, "CD79B": .61, "EBF1": .782, "PAX5": .579, "MS4A1": .481,
            "CD24A": .820, "CD93": .271, "VPREB3": .692, "IGHM": .609,
            "MZB1": .053, "PRDM1": .06, "XBP1": .08, "SDC1": .04,
            "MKI67": .820, "TOP2A": .835,
        },
        "plasma_epcam_1": {
            "PRDM1": .70, "XBP1": .76, "SDC1": .55, "MZB1": .82, "DERL3": .78,
            "JCHAIN": .72, "FKBP11": .75, "EPCAM": .846, "KRT18": .12,
        },
        "plasma_epcam_2": {
            "PRDM1": .68, "XBP1": .72, "SDC1": .50, "MZB1": .79, "DERL3": .74,
            "JCHAIN": .69, "FKBP11": .70, "EPCAM": .594, "KRT18": .11,
        },
        "pre_b_case": {
            "CD79A": .68, "EBF1": .72, "PAX5": .45, "MS4A1": .07,
            "RAG1": .61, "VPREB1A": .15, "IGLL1": .15, "VPREB3": .92,
            "CD24A": .68, "LEF1": .73, "SOX4": .76,
        },
    }
    write_ratio_values(b_boundary_path, b_values)
    b_decisions = enrich_evidence(
        evidence(b_values), ratio_path=b_boundary_path,
        annotation_level="subcluster", species="Mouse", tissue="ovary;tumor",
        parent_population="B_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert b_decisions["naive_case"]["stable_id"] == "Naive_B"
    assert b_decisions["naive_case"]["primary_evidence_label"] != "Memory_B"
    assert b_decisions["cycling_immature"]["stable_id"] == "Immature_B"
    assert b_decisions["cycling_immature"]["primary_state"] == "Cycling"
    absolute_gate = score_panel(
        "Plasma_cell",
        {
            "core": ["PRDM1", "XBP1", "SDC1", "MZB1"],
            "supportive": ["JCHAIN", "DERL3"],
            "negative": ["MS4A1", "PAX5"],
            "absolute_negative_genes": ["MS4A1", "PAX5"],
            "absolute_negative_detection_floor": .30,
            "maximum_absolute_negative_hits": 1,
        },
        "cycling_immature",
        {
            cluster: {gene: {"ratio": ratio, "mean": ratio * 3.0} for gene, ratio in values.items()}
            for cluster, values in b_values.items()
        },
        list(b_values),
        {
            "minimum_detection_floor": .05, "primary_detection_floor": .20,
            "rival_review_floor": .10, "minimum_detection_delta": .10,
            "primary_robust_z": 2.0, "rival_robust_z": 1.5,
            "minimum_core_markers": 3,
        },
        True,
    )
    assert absolute_gate["absolute_negative_blocked"] is True
    assert b_decisions["plasma_epcam_1"]["stable_id"] == "Plasma_cell"
    assert b_decisions["plasma_epcam_1"]["off_parent_detected"] is False
    assert b_decisions["plasma_epcam_2"]["off_parent_detected"] is False
    assert b_decisions["pre_b_case"]["stable_id"] == "Pre_B"

    cell_path = work / "cell.json"
    cell_path.write_text(json.dumps({"0": {"doublet_call": True, "method": "scDblFinder", "per_sample": True}}), encoding="utf-8")
    cell = enrich_evidence(
        evidence(mixed_programs), ratio_path=mixed_path, cell_evidence_path=cell_path, annotation_level="major", tissue="blood"
    )
    assert cell["deterministic_annotation_evidence"]["0"]["risk_level"] == "R3_DOUBLET_CANDIDATE"
    assert cell["deterministic_annotation_evidence"]["0"]["evidence_mode"] == "cell_validated"

    config = json.loads((ROOT / "annotation-evidence-config.v1.json").read_text(encoding="utf-8"))
    sparse = score_panel(
        "Sparse_test",
        {"core": ["A", "B", "C", "D"], "supportive": [], "negative": [], "required_core_markers": 2},
        "0",
        {"0": {"A": {"ratio": 0.80, "background": 0.01, "log2FC": 2.0}}},
        ["0"],
        config["thresholds"],
        False,
    )
    assert sparse["core_panel_size"] == 4
    assert sparse["core_known_fraction"] == 0.25
    assert sparse["core_positive_fraction"] == 0.25
    assert sparse["core_fraction"] == 0.25

    kb = load_knowledge_base()
    t_runtime = build_runtime_config(
        kb, species="Mouse", tissue="ovary;tumor", annotation_level="subcluster",
        parent_population="T_cell", parent_kind="lineage",
    )
    assert "CD4_T" in t_runtime["identity_panels"] and "CD8_T" in t_runtime["identity_panels"]
    assert "CD4_Tem" in t_runtime["identity_panels"]
    assert t_runtime["panel_provenance"]["CD4_Tem"]["panel_species"] == "Mouse"
    assert set(t_runtime["panel_provenance"]["CD4_Tem"]["evidence_ids"]) == {
        "SRC_CL", "SRC_CD4_TEM_MOUSE", "SRC_MEMORY_T"
    }
    assert "SRC_CD4_TEM_MOUSE" in t_runtime["evidence_source_registry"]
    assert "CD4_Tex" not in t_runtime["identity_panels"] and "CD8_Tex" not in t_runtime["identity_panels"]
    assert "Tn" in t_runtime["identity_panels"] and "DNT" in t_runtime["identity_panels"]
    try:
        compose_display_label("CD4_Tex", "Exhausted")
    except ValueError as exc:
        assert "Legacy identity/state boundary" in str(exc)
    else:
        raise AssertionError("Deprecated Tex Stable_ID must fail display-label composition")
    blood_panels = build_runtime_config(kb, species="Human", tissue="blood", annotation_level="major")["identity_panels"]
    aorta_panels = build_runtime_config(kb, species="Human", tissue="Aorta", annotation_level="major")["identity_panels"]
    intestine_panels = build_runtime_config(kb, species="Human", tissue="intestine", annotation_level="major")["identity_panels"]
    liver_panels = build_runtime_config(kb, species="Human", tissue="liver", annotation_level="major")["identity_panels"]
    fetal_lung_panels = build_runtime_config(kb, species="Human", tissue="fetal lung", annotation_level="major")["identity_panels"]
    assert "TA_cell" not in blood_panels and "Hepatocyte" not in blood_panels
    assert "Neutrophil" in aorta_panels and "Monocyte" in aorta_panels and "Classical_monocyte" in aorta_panels
    assert "TA_cell" in intestine_panels
    assert "Hepatocyte" in liver_panels
    assert "Erythroid" in fetal_lung_panels and "Megakaryocyte" in fetal_lung_panels

    rat_runtime = build_runtime_config(
        kb, species="Rat", tissue="blood", annotation_level="subcluster",
        parent_population="T_cell", parent_kind="lineage",
    )
    assert rat_runtime["species"] == "Rat"
    assert rat_runtime["species_panel_mode"] == "cross_species_human_fallback"
    assert rat_runtime["panel_provenance"]["Tn"]["target_species"] == "Rat"
    assert rat_runtime["panel_provenance"]["Tn"]["panel_species"] == "Human"
    assert rat_runtime["panel_provenance"]["Tn"]["cross_species_inference"] is True

    version = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))
    runtime_config = json.loads((ROOT / "annotation-evidence-config.v1.json").read_text(encoding="utf-8"))
    assert runtime_config["config_version"] == version["config_version"]

    b_runtime = build_runtime_config(
        kb,
        species="Mouse",
        tissue="ovary;tumor",
        annotation_level="subcluster",
        parent_population="B_cell",
        parent_kind="lineage",
    )
    b_panels = b_runtime["identity_panels"]
    for label in ("Pro_B", "Pre_B", "Immature_B", "Transitional_B", "Naive_B", "Memory_B", "GC_B", "Plasmablast", "Plasma_cell"):
        assert label in b_panels
    assert "Developing_B" not in b_panels and "Mature_B" not in b_panels and "Antibody_secreting_B" not in b_panels
    assert "VPREB1A" in b_panels["Pre_B"]["core"]
    assert "CD24A" in b_panels["Transitional_B"]["core"]
    assert b_runtime["panel_provenance"]["Pre_B"]["panel_species"] == "Mouse"
    assert b_runtime["panel_provenance"]["Pre_B"]["tissue_scope_match"] is False
    assert b_runtime["panel_provenance"]["Pre_B"]["tissue_context_review"] is True
    assert b_runtime["panel_provenance"]["Naive_B"]["tissue_scope_match"] is True
    assert b_runtime["panel_provenance"]["Naive_B"]["parent_path"] == ["Cell", "Immune_cell", "B_cell", "Mature_B", "Naive_B"]
    assert "NK_cell" in b_panels
    assert b_runtime["panel_provenance"]["NK_cell"]["within_parent_scope"] is False
    assert b_runtime["panel_provenance"]["NK_cell"]["off_parent_audit"] is True
    composite_b_runtime = build_runtime_config(
        kb,
        species="Mouse",
        tissue="ovarian tumor",
        annotation_level="subcluster",
        parent_population="B_cell",
        parent_kind="lineage",
    )
    assert composite_b_runtime["panel_provenance"]["Naive_B"]["tissue_scope_match"] is True
    assert composite_b_runtime["panel_provenance"]["Pre_B"]["tissue_scope_match"] is False

    empty_major = enrich_evidence(evidence(["0"]), annotation_level="major", tissue="blood", parent_population="All_cells", parent_kind="mixed")
    empty_major_decision = empty_major["deterministic_annotation_evidence"]["0"]
    assert empty_major_decision["stable_id"] == ""
    assert empty_major_decision["primary_major_label"] == ""
    assert empty_major_decision["formal_identity_fallback"] == "unresolved_requires_research"
    assert empty_major_decision["resolution_search_required"] is True
    empty_sub = enrich_evidence(evidence(["0"]), annotation_level="subcluster", tissue="stomach", parent_population="T_cell", parent_kind="lineage")
    assert empty_sub["deterministic_annotation_evidence"]["0"]["stable_id"] == "T_cell"
    assert empty_sub["deterministic_annotation_evidence"]["0"]["resolution_search_required"] is True

    repeated_naive_path = work / "repeated_naive_b.tsv"
    repeated_naive_values = {
        str(cluster): {
            "IGHM": 0.70, "IGHD": 0.50, "TCL1A": 0.40, "FCER2": 0.20,
            "CD79A": 0.60, "CD79B": 0.70, "MS4A1": 0.80, "PAX5": 0.80,
            "CD74": 0.90, "HLA-DRA": 0.90, "RAG1": 0.01, "RAG2": 0.01,
            "DNTT": 0.01, "VPREB1": 0.01, "IGLL1": 0.01, "PRDM1": 0.01,
            "SDC1": 0.01, "DERL3": 0.01,
        }
        for cluster in range(3)
    }
    write_ratio_values(repeated_naive_path, repeated_naive_values)
    repeated_naive = enrich_evidence(
        evidence(repeated_naive_values), ratio_path=repeated_naive_path,
        annotation_level="subcluster", species="Human", tissue="fetal lung",
        parent_population="B_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert all(repeated_naive[str(cluster)]["stable_id"] == "Naive_B" for cluster in range(3))
    assert all(
        repeated_naive[str(cluster)]["decision_trace"]["absolute_program_gate"]["passed"] is True
        for cluster in range(3)
    )
    assert all(repeated_naive[str(cluster)]["formal_identity_fallback"] == "" for cluster in range(3))

    immature_exit_path = work / "immature_b_recombination_exit.tsv"
    immature_exit_values = {
        "5": {
            "IGHM": 0.98, "CD24": 0.91, "CD38": 0.91, "TCL1A": 0.93, "VPREB3": 0.94,
            "ROR1": 0.66, "FCRL1": 0.72, "CD79A": 0.70, "CD79B": 0.94, "PAX5": 0.78,
            "CD74": 0.70, "HLA-DRA": 0.65, "VPREB1": 0.47, "IGLL1": 0.38,
            "RAG1": 0.52, "RAG2": 0.34, "DNTT": 0.00, "PRDM1": 0.01,
            "SDC1": 0.01, "DERL3": 0.01,
        },
        "6": {
            "IGHM": 0.93, "CD24": 0.81, "CD38": 0.83, "TCL1A": 0.61, "VPREB3": 0.84,
            "ROR1": 0.62, "FCRL1": 0.22, "CD79A": 0.74, "CD79B": 0.79, "PAX5": 0.88,
            "CD74": 0.60, "HLA-DRA": 0.55, "VPREB1": 0.75, "IGLL1": 0.83,
            "RAG1": 0.36, "RAG2": 0.50, "DNTT": 0.19, "PRDM1": 0.01,
            "SDC1": 0.01, "DERL3": 0.01,
        },
        "9": {
            "IGHM": 0.86, "CD24": 0.47, "CD38": 0.75, "TCL1A": 0.83, "VPREB3": 0.47,
            "ROR1": 0.67, "FCRL1": 0.69, "CD79A": 0.33, "CD79B": 0.67, "PAX5": 0.83,
            "CD74": 0.40, "HLA-DRA": 0.35, "VPREB1": 0.19, "IGLL1": 0.11,
            "RAG1": 0.22, "RAG2": 0.14, "DNTT": 0.00, "PRDM1": 0.01,
            "SDC1": 0.01, "DERL3": 0.01,
        },
    }
    write_ratio_values(immature_exit_path, immature_exit_values)
    immature_exit = enrich_evidence(
        evidence(immature_exit_values), ratio_path=immature_exit_path,
        annotation_level="subcluster", species="Human", tissue="fetal lung",
        parent_population="B_cell", parent_kind="lineage",
    )["deterministic_annotation_evidence"]
    assert immature_exit["5"]["stable_id"] == "Pre_B"
    assert immature_exit["6"]["stable_id"] == "Pre_B"
    assert immature_exit["9"]["stable_id"] == "Immature_B"
    assert immature_exit["9"]["decision_trace"]["absolute_program_gate"]["passed"] is True
    assert immature_exit["5"]["decision_trace"]["absolute_program_gate"].get("passed") is not True
    assert immature_exit["6"]["decision_trace"]["absolute_program_gate"].get("passed") is not True

    cd4_tem_path = work / "cd4_tem.tsv"
    cd4_tem_values = {
        "0": {
            "CD3D": 0.80, "CD3E": 0.80, "TRAC": 0.80, "CD4": 0.8458, "CD40LG": 0.2408,
            "CD44": 0.7871, "IL7R": 0.3833, "IFNG": 0.3348, "TNFSF8": 0.5404,
            "TNFSF11": 0.6505, "TNFRSF4": 0.6520, "IL21": 0.0925,
            "SELL": 0.0059, "CCR7": 0.1689, "TCF7": 0.02, "LEF1": 0.02,
            "FOXP3": 0.0103, "CXCL13": 0.0088,
        },
        "1": {
            "CD3D": 0.80, "CD3E": 0.80, "TRAC": 0.80, "CD4": 0.80, "CD40LG": 0.30,
            "CCR7": 0.80, "SELL": 0.80, "TCF7": 0.80, "LEF1": 0.80, "IL7R": 0.70,
            "CD44": 0.10, "IFNG": 0.01, "TNFSF8": 0.01,
        },
    }
    write_ratio_values(cd4_tem_path, cd4_tem_values)
    cd4_tem = enrich_evidence(
        evidence(cd4_tem_values), ratio_path=cd4_tem_path, annotation_level="subcluster",
        species="Mouse", tissue="ovarian tumor", parent_population="T_cell", parent_kind="lineage",
    )
    assert cd4_tem["deterministic_annotation_evidence"]["0"]["stable_id"] == "CD4_Tem"
    assert cd4_tem["deterministic_annotation_evidence"]["1"]["stable_id"] == "CD4_Tn"
    assert cd4_tem["deterministic_annotation_evidence"]["0"]["cross_species_inference"] is False

    print(json.dumps({"status": "pass", "tests": 161, "work_dir": str(work)}))


if __name__ == "__main__":
    main()
