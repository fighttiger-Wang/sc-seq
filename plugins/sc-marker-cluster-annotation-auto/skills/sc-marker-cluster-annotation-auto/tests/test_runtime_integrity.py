"""Regressions for unsupported identity gates and an isolated plugin install."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import qualitative_evidence_core as core
import build_annotation_workbook as builder


class IdentityGateTests(unittest.TestCase):
    def evaluate(self, supported=False, branch=True, conflict=False, program=None):
        metric = {"gene": "ANCHOR", "review": supported, "strong": supported}
        negative = {"gene": "EXCLUSION", "review": conflict, "strong": conflict}
        def gene_metric(gene, *args):
            return {**(negative if gene == "EXCLUSION" else metric), "gene": gene}
        with patch.object(core, "gene_metric", side_effect=gene_metric), \
             patch.object(core, "_identity_branch_gate", return_value={"passed": branch, "assessed": True, "rule_id": "branch"}), \
             patch.object(core, "_identity_program_gate", return_value=program or {"passed": True, "assessed": False, "required": False, "rule_id": ""}), \
             patch.object(core, "_absolute_program_gate", return_value={"required": False}), \
             patch.object(core, "_mutually_exclusive_program_gate", return_value={"passed": True}):
            return core._evaluate_panel("Test", {"core": ["ANCHOR", "ANCHOR2"], "negative": ["EXCLUSION"]}, "0", {}, ["0", "1"], {}, True, {}, set())

    def test_no_rule_cannot_supply_missing_identity(self):
        self.assertEqual(self.evaluate()["identity_anchor_gate"], "不通过")
        self.assertEqual(self.evaluate()["program_gate"], "不通过")

    def test_no_rule_cannot_override_failed_branch(self):
        self.assertEqual(self.evaluate(supported=True, branch=False)["program_gate"], "不通过")

    def test_no_rule_cannot_override_exclusion(self):
        self.assertEqual(self.evaluate(supported=True, conflict=True)["exclusion_gate"], "不通过")

    def test_applicable_passed_program_can_resolve_boundary(self):
        result = self.evaluate(branch=False, conflict=True, program={"passed": True, "assessed": True, "required": True, "rule_id": "validated_boundary"})
        self.assertEqual(result["program_gate"], "通过")

    def test_failed_or_unassessed_program_cannot_rescue(self):
        for assessed, passed in [(False, True), (True, False)]:
            self.assertEqual(self.evaluate(program={"rule_id": "boundary", "assessed": assessed, "passed": passed})["program_gate"], "不通过")

    def test_coherent_panel_still_passes_without_special_rule(self):
        self.assertEqual(self.evaluate(supported=True)["program_gate"], "通过")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bundled_snapshot_is_complete(skill):
    """Validate package-local snapshot payloads when no source checkout exists."""
    manifest = json.loads((skill / "references" / "annotation-evidence-core.snapshot.json").read_text(encoding="utf-8"))
    for source_name, expected in manifest.get("files", {}).items():
        if source_name.startswith("knowledge-base/"):
            path = skill / "references" / Path(source_name).name
        elif source_name.endswith((".json", ".md")):
            path = skill / "references" / Path(source_name).name
        else:
            path = skill / "scripts" / source_name
        assert path.is_file() and sha256(path) == expected, f"Bundled snapshot mismatch: {path}"
    for source_name, item in manifest.get("plugin_additions", {}).items():
        path = skill / item["folder"] / item["filename"]
        assert path.is_file() and sha256(path) == item["sha256"], f"Bundled addition mismatch: {source_name}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(IdentityGateTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    bad_evidence = {
        "qualitative_annotation_evidence": {
            "0": {
                "candidate_program_audits": [
                    {
                        "label": "Unsupported",
                        "program_gate": "通过",
                        "required_identity_anchors": 2,
                        "supporting_core": [],
                        "identity_program_audit": {"rule_id": "", "assessed": False, "passed": False},
                    }
                ]
            }
        }
    }
    try:
        builder.validate_candidate_semantics(bad_evidence)
    except ValueError as exc:
        assert "program_gate=通过" in str(exc)
    else:
        raise AssertionError("Contradictory program_gate=通过 without core evidence was accepted")
    valid_evidence = {
        "qualitative_annotation_evidence": {
            "0": {
                "candidate_program_audits": [
                    {
                        "label": "Supported",
                        "program_gate": "通过",
                        "required_identity_anchors": 2,
                        "supporting_core": [
                            {"gene": "A", "review": True},
                            {"gene": "B", "review": True},
                        ],
                        "identity_program_audit": {"rule_id": "", "assessed": False, "passed": False},
                    }
                ]
            }
        }
    }
    builder.validate_candidate_semantics(valid_evidence)
    isolated = work / "isolated_plugin" / "skills" / SKILL.name
    shutil.copytree(SKILL, isolated, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    code = "import pathlib,sys; sys.path.insert(0,sys.argv[1]); import prepare_annotation as p; import qualitative_evidence_core as c; assert pathlib.Path(c.__file__).parent==pathlib.Path(sys.argv[1]); assert p.resolve_parent_population('Endothelial')=='Endothelial_cell'; assert p.resolve_parent_population('endothelial cell')=='Endothelial_cell'; assert p.resolve_parent_population('T_cell')=='T_cell'; assert p.resolve_parent_population('unknown parent')=='unknown parent'; print('isolated runtime and parent aliases: pass')"
    subprocess.run([sys.executable, "-c", code, str(isolated / "scripts")], cwd=work, check=True)
    contract = isolated / "references" / "annotation-universal-contract.md"
    assert contract.is_file(), "Installed plugin must contain its required contract"
    assert "references/annotation-universal-contract.md" in (isolated / "SKILL.md").read_text(encoding="utf-8")
    marketplace = next((parent for parent in SKILL.parents if (parent / "skill-pack.json").is_file()), None)
    if marketplace:
        spec = importlib.util.spec_from_file_location("snapshot_sync", marketplace / "tools" / "sync_annotation_evidence_core.py")
        sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sync)
        sync.synchronize(check=True, skill_ids=[SKILL.name])
        # A copied install must reject changed payloads and stale shared bases.
        sync.TARGETS = (isolated,)
        sync.synchronize(check=True, skill_ids=[SKILL.name])
        payload = isolated / "scripts" / "qualitative_evidence_core.py"
        original = payload.read_bytes()
        payload.write_bytes(original + b"\n# tampered\n")
        try:
            sync.synchronize(check=True, skill_ids=[SKILL.name])
        except RuntimeError as exc:
            assert "override hash mismatch" in str(exc)
        else:
            raise AssertionError("Tampered override accepted")
        finally:
            payload.write_bytes(original)
        manifest = isolated / "references" / "annotation-evidence-core.snapshot.json"
        original_manifest = manifest.read_bytes()
        data = json.loads(original_manifest)
        data["plugin_overrides"]["qualitative_annotation_workbook.py"]["base_sha256"] = "0" * 64
        manifest.write_text(json.dumps(data), encoding="utf-8")
        try:
            sync.synchronize(check=True, skill_ids=[SKILL.name])
        except RuntimeError as exc:
            assert "Shared base changed" in str(exc)
        else:
            raise AssertionError("Stale shared base accepted")
        finally:
            manifest.write_bytes(original_manifest)
    else:
        bundled_snapshot_is_complete(SKILL)
        bundled_snapshot_is_complete(isolated)
    print(json.dumps({"status": "pass", "checks": result.testsRun + 10, "work_dir": str(work)}))


if __name__ == "__main__":
    main()
