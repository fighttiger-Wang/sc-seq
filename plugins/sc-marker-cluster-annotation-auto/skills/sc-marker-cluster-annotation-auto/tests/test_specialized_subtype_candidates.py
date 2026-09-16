#!/usr/bin/env python3
"""Synthetic regression for conditional specialization candidates."""

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch


def primary(label):
    return {"label": label, "program_gate": "通过"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    Path(args.work_dir).resolve().mkdir(parents=True, exist_ok=True)

    skill = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(skill / "scripts"))
    import qualitative_evidence_core as core

    config = {
        "specialization_panels": {
            "Synthetic_tip": {
                "allowed_primary_labels": ["Synthetic_capillary"],
                "markers": ["TIP_A", "TIP_B", "TIP_C"],
                "required_any": ["TIP_A", "TIP_B"],
                "minimum_markers": 2,
                "minimum_strong_markers": 1,
                "evidence_ids": ["SYNTHETIC"],
            }
        }
    }

    def metric(gene, *args):
        active = gene in {"TIP_A", "TIP_B"}
        return {"gene": gene, "review": active, "strong": gene == "TIP_A"}

    with patch.object(core, "gene_metric", side_effect=metric):
        candidates = core._evaluate_specialized_subtypes(
            config, primary("Synthetic_capillary"), "0", {}, ["0"], {}, True, set()
        )
        rejected = core._evaluate_specialized_subtypes(
            config, primary("Synthetic_venous"), "0", {}, ["0"], {}, True, set()
        )

    assert len(candidates) == 1
    assert candidates[0]["label"] == "Synthetic_tip"
    assert candidates[0]["base_identity"] == "Synthetic_capillary"
    assert candidates[0]["identity_binding"] == "conditional_lower_level_subtype_only"
    assert len(candidates[0]["supporting_markers"]) == 2
    assert rejected == []
    print(json.dumps({"status": "pass", "checks": 6}, ensure_ascii=False))


if __name__ == "__main__":
    main()
