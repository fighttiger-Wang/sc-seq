import unittest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_annotation_workbook import validate_expert_review


class ExpertReviewGateTests(unittest.TestCase):
    def test_missing_review_is_blocked(self):
        with self.assertRaises(ValueError):
            validate_expert_review([{"cluster_id": "0"}])

    def test_complete_review_is_accepted(self):
        validate_expert_review([{
            "cluster_id": "0",
            "expert_review_status": "conditional",
            "expert_review_basis": "Complete identity program reviewed against sibling alternatives.",
            "identity_review_summary": "Primary identity retained; closest sibling lacks a complete program.",
            "optimization_recommendations": "Validate with orthogonal markers.",
            "validation_advice": "Obtain orthogonal markers.",
            "handling_advice": "Keep the clean plotting label; manual review before quantitative analysis.",
            "identity_anchor_gate": "通过",
            "sibling_competition_gate": "通过",
            "exclusion_gate": "通过",
        }])

    def test_passed_with_failed_identity_gate_is_blocked(self):
        with self.assertRaises(ValueError):
            validate_expert_review([{
                "cluster_id": "13",
                "expert_review_status": "passed",
                "expert_review_basis": "Macrophage label retained.",
                "identity_review_summary": "Macrophage program reviewed.",
                "optimization_recommendations": "No additional optimization currently required.",
                "expert_plot_verdict": "allow_provisional_label",
                "identity_anchor_gate": "不通过",
                "evidence_gaps": "smooth-muscle boundary unresolved",
            }])


if __name__ == "__main__":
    unittest.main()
