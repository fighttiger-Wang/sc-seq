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
        }])


if __name__ == "__main__":
    unittest.main()
