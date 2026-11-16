#!/usr/bin/env python3

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RENDER = ROOT / "scripts" / "render_report.py"
VALIDATE = ROOT / "scripts" / "validate_report.py"


def write_svg(path: Path, width: int, height: int, label: str) -> None:
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<title>{label}</title><desc>responsive test</desc><rect width="100%" height="100%" fill="#fff"/>'
        f'<text x="10" y="24">{label} · 概念示意 · 非项目实测结果</text></svg>',
        encoding="utf-8",
    )


class ResponsiveFigureTests(unittest.TestCase):
    def test_three_variants_are_embedded_and_validated(self):
        with tempfile.TemporaryDirectory() as temp_name:
            folder = Path(temp_name)
            write_svg(folder / "desktop.svg", 1440, 880, "desktop")
            write_svg(folder / "mobile.svg", 390, 1300, "mobile")
            write_svg(folder / "print.svg", 842, 595, "print")
            spec = {
                "title": "响应式图件测试",
                "output_stem": "responsive-figure-test",
                "base_dir": ".",
                "summary": {"lead": "测试", "findings": [{"text": "测试", "evidence": "fixture"}]},
                "sections": [
                    {
                        "id": "figure-test",
                        "title": "图件",
                        "blocks": [
                            {
                                "type": "image",
                                "path": "desktop.svg",
                                "mobile_path": "mobile.svg",
                                "print_path": "print.svg",
                                "alt": "三种版式测试图",
                                "title": "测试图",
                                "caption": "测试",
                                "authored_concept": True,
                                "layout": "wide"
                            }
                        ]
                    }
                ],
                "conclusion": "测试",
                "footer": "未重新计算统计检验。"
            }
            spec_path = folder / "spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            rendered = subprocess.run([sys.executable, str(RENDER), str(spec_path), "--temp-dir", str(folder)], capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            report = Path(json.loads(rendered.stdout)["output"])
            document = report.read_text(encoding="utf-8")
            self.assertIn("<picture", document)
            self.assertIn("currentSrc", document)
            self.assertEqual(document.count('data-report-asset="true"'), 3)
            validated = subprocess.run([sys.executable, str(VALIDATE), str(report)], capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
            result = json.loads(validated.stdout)
            self.assertEqual([item["role"] for item in result["embedded_assets"]], ["mobile", "desktop", "print"])


if __name__ == "__main__":
    unittest.main()
