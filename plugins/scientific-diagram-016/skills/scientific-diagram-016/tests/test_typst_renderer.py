#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render_typst_variants.py"
SPEC = Path(__file__).resolve().parent / "study-design-example.json"


class TypstRendererTests(unittest.TestCase):
    def test_prepare_only_creates_three_clean_sources(self):
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(SPEC), str(output), "--stem", "qa", "--prepare-only"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["status"], "prepared")
            self.assertEqual(set(result["variants"]), {"desktop", "mobile", "print"})
            for variant in result["variants"]:
                source = output / f"qa.{variant}.typ"
                self.assertTrue(source.is_file())
                self.assertNotRegex(source.read_text(encoding="utf-8"), r"__[A-Z0-9_]+__")

    def test_invalid_stem_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(SPEC), temp_name, "--stem", "bad stem", "--prepare-only"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
