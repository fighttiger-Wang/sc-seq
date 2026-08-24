import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import case_registry as registry


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = self.root / "store"
        self.project = self.root / "N999_annotation_20260819"
        self.project.mkdir()
        self.kb = self.root / "kb.json"
        self.kb.write_text(json.dumps({
            "schema_version": "2.0.0", "knowledge_base_version": "2.7.0", "ontology": [
                {"cell_id": "Cell", "parent_id": "", "proposed_status": "Approve"},
                {"cell_id": "T_cell", "parent_id": "Cell", "proposed_status": "Approve"}
            ], "marker_panels": [{"cell_id": "T_cell", "approval_status": "Approve"}],
            "evidence_sources": [], "aliases": [], "tissue_modules": [], "state_rules": [],
            "decision_rules": [], "legacy_migration": []
        }), encoding="utf-8")
        conn = registry.ensure_store(self.store, self.kb); conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def write_case(self):
        records = [{"cluster_id": "0", "stable_id": "T_cell", "label_basis": "canonical_subtype",
                    "supporting_markers": "CD3D;CD3E;TRAC", "conflicting_markers": "",
                    "parent_path": ["Cell", "T_cell"], "confidence": "high", "quality_score": 90,
                    "mixed_or_doublet": False, "ontology_node_kind": "identity"}]
        qa = {"status": "pass", "record_count": 1, "annotation_evidence_policy": {
            "knowledge_base_source": "E:/cache/sc-major-celltype-annotation-auto/0.2.2+codex.1/skills/x.json",
            "species": "Mouse", "tissue": "spleen"}}
        rp, qp = self.project / "annotation_records.json", self.project / "result.qa.json"
        rp.write_text(json.dumps(records), encoding="utf-8"); qp.write_text(json.dumps(qa), encoding="utf-8")
        return rp, qp

    def test_registration_is_idempotent(self):
        rp, qp = self.write_case()
        first = registry.register_case(self.store, rp, qp, project_dir=self.project)
        second = registry.register_case(self.store, rp, qp, project_dir=self.project)
        self.assertEqual(first["status"], "registered")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(registry.status(self.store)["case_count"], 1)

    def test_existing_identity_stays_approved(self):
        rp, qp = self.write_case()
        registry.register_case(self.store, rp, qp, project_dir=self.project)
        conn = registry.connect(self.store)
        stage = conn.execute("SELECT stage FROM identity_status WHERE identity_id='T_cell'").fetchone()[0]
        conn.close()
        self.assertEqual(stage, "approved")

    def test_clean_cluster_counts_when_same_identity_has_mixed_cluster(self):
        records = [
            {"cluster_id": "0", "stable_id": "New_cell", "label_basis": "validated_external_candidate",
             "supporting_markers": "GENEA;GENEB", "parent_path": ["Cell", "T_cell", "New_cell"],
             "quality_score": 80, "mixed_or_doublet": False},
            {"cluster_id": "1", "stable_id": "New_cell", "label_basis": "validated_external_candidate",
             "supporting_markers": "GENEA;GENEC", "parent_path": ["Cell", "T_cell", "New_cell"],
             "quality_score": 40, "mixed_or_doublet": True}
        ]
        observations = registry.group_observations(records, {"species": "Mouse"})
        self.assertEqual(observations[0]["eligible"], 1)
        self.assertEqual(observations[0]["cluster_count"], 1)
        self.assertNotIn("GENEC", observations[0]["supporting"])

    def test_empirical_marker_update_adds_and_downweights_without_deletion(self):
        kb = {"marker_panels": [{"cell_id": "T_cell", "target_species": "Mouse", "approval_status": "Approve",
                                  "core_markers": "CD3D;BADCORE", "supportive_markers": "TRAC"}]}
        summary = {"identity_id": "T_cell", "marker_stats_by_species": {"Mouse": {
            "case_count": 5, "support_frequency": {"CD3E": 1.0}, "conflict_frequency": {"BADCORE": 0.8}}}}
        policy = registry.load_json(registry.DEFAULT_POLICY)
        changes = registry.apply_empirical_marker_updates(kb, summary, policy)
        panel = kb["marker_panels"][0]
        self.assertTrue(changes)
        self.assertIn("CD3E", panel["supportive_markers"])
        self.assertNotIn("BADCORE", panel["core_markers"])
        self.assertIn("BADCORE", panel["supportive_markers"])
        self.assertIn("BADCORE", panel["deprecated_markers"])


if __name__ == "__main__":
    unittest.main()
