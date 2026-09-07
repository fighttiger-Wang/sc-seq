#!/usr/bin/env python3
"""Prepare and compile fixed Typst/CeTZ scientific study-design variants."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TYPST_VERSION = "0.13.1"
CETZ_VERSION = "0.3.4"
VARIANTS = {
    "desktop": ("study-design-desktop.typ", 1440, 880, 82, 28),
    "mobile": ("study-design-mobile.typ", 390, 1300, 30, 22),
    "print": ("study-design-print.typ", 842, 595, 42, 17),
}
OPEN_FONT_CANDIDATES = ("Noto Sans SC", "Source Han Sans", "Noto Sans CJK SC")
SAFE_STEM = re.compile(r"^[A-Za-z0-9_-]+$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def validate_spec(spec: dict[str, Any]) -> dict[str, str]:
    if not isinstance(spec, dict):
        raise ValueError("root JSON value must be an object")
    groups = spec.get("groups")
    modules = spec.get("modules")
    comparisons = spec.get("comparisons")
    if not isinstance(groups, list) or len(groups) != 3:
        raise ValueError("the fixed study-design template requires exactly 3 groups")
    if not isinstance(modules, list) or len(modules) != 3:
        raise ValueError("the fixed study-design template requires exactly 3 analysis modules")
    if not isinstance(comparisons, list) or len(comparisons) != 2:
        raise ValueError("the fixed study-design template requires exactly 2 comparison labels")

    values = {
        "FONT": "",
        "TITLE": require_string(spec.get("title"), "title"),
        "MOBILE_TITLE": require_string(spec.get("mobile_title", spec.get("title")), "mobile_title"),
        "SUBTITLE": require_string(spec.get("subtitle"), "subtitle"),
        "BADGE": require_string(spec.get("badge", "研究设计图"), "badge"),
        "SECTION_TITLE": require_string(spec.get("section_title", "样本分组与核心比较"), "section_title"),
        "HUB_LABEL": require_string(spec.get("hub_label", "核心比较框架"), "hub_label"),
        "HUB_LINE_1": require_string(spec.get("hub_lines", [None, None])[0], "hub_lines[0]"),
        "HUB_LINE_2": require_string(spec.get("hub_lines", [None, None])[1], "hub_lines[1]"),
        "HUB_NOTE": require_string(spec.get("hub_note"), "hub_note"),
        "MODULE_SECTION": require_string(spec.get("module_section", "分层分析主线"), "module_section"),
        "OUTCOME": require_string(spec.get("outcome"), "outcome"),
        "FOOTER": require_string(spec.get("footer", "Typst + CeTZ"), "footer"),
        "DESCRIPTION": require_string(spec.get("description"), "description"),
        "CONCEPT_LABEL": require_string(
            spec.get("concept_label", "概念示意 · 根据课题设计绘制 · 非项目实测结果"),
            "concept_label",
        ),
    }
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ValueError(f"groups[{index}] must be an object")
        prefix = f"GROUP_{chr(65 + index)}"
        values[f"{prefix}_TAG"] = require_string(group.get("tag"), f"groups[{index}].tag")
        values[f"{prefix}_TITLE"] = require_string(group.get("title"), f"groups[{index}].title")
        values[f"{prefix}_BODY_1"] = require_string(group.get("body_1"), f"groups[{index}].body_1")
        values[f"{prefix}_BODY_2"] = require_string(group.get("body_2"), f"groups[{index}].body_2")
    for index, comparison in enumerate(comparisons, 1):
        values[f"COMPARISON_{index}"] = require_string(comparison, f"comparisons[{index - 1}]")
    for index, module in enumerate(modules, 1):
        if not isinstance(module, dict):
            raise ValueError(f"modules[{index - 1}] must be an object")
        prefix = f"MODULE_{index}"
        values[f"{prefix}_TAG"] = require_string(module.get("tag"), f"modules[{index - 1}].tag")
        values[f"{prefix}_TITLE"] = require_string(module.get("title"), f"modules[{index - 1}].title")
        values[f"{prefix}_BODY_1"] = require_string(module.get("body_1"), f"modules[{index - 1}].body_1")
        values[f"{prefix}_BODY_2"] = require_string(module.get("body_2"), f"modules[{index - 1}].body_2")
    return values


def typst_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", " ").replace("\n", " ")


def prepare_source(template: Path, output: Path, values: dict[str, str]) -> None:
    document = template.read_text(encoding="utf-8")
    for key, value in values.items():
        document = document.replace(f"__{key}__", typst_escape(value))
    unresolved = sorted(set(re.findall(r"__[A-Z0-9_]+__", document)))
    if unresolved:
        raise ValueError(f"unresolved template fields in {template.name}: {', '.join(unresolved)}")
    output.write_text(document, encoding="utf-8", newline="\n")


def resolve_typst(explicit: Path | None) -> Path | None:
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit)
    configured = os.environ.get("TYPST_BIN")
    if configured:
        candidates.append(Path(configured))
    located = shutil.which("typst") or shutil.which("typst.exe")
    if located:
        candidates.append(Path(located))
    for candidate in candidates:
        expanded = candidate.expanduser().resolve()
        if expanded.is_file():
            return expanded
    return None


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command[:3])}: {detail}")
    return completed


def typst_version(executable: Path) -> str:
    output = run_checked([str(executable), "--version"]).stdout.strip()
    matched = re.search(r"\b(\d+\.\d+\.\d+)\b", output)
    if not matched:
        raise RuntimeError(f"could not parse Typst version from: {output}")
    return matched.group(1)


def select_font(executable: Path, requested: str | None) -> str | None:
    installed = {line.strip() for line in run_checked([str(executable), "fonts"]).stdout.splitlines() if line.strip()}
    candidates = (requested,) if requested else OPEN_FONT_CANDIDATES
    return next((name for name in candidates if name and name in installed), None)


def finalize_svg(raw_path: Path, output_path: Path, title: str, description: str, concept_label: str, label_x: float, label_bottom: float) -> None:
    svg = raw_path.read_text(encoding="utf-8")
    open_end = svg.find(">")
    if open_end < 0 or not svg.lstrip().startswith("<svg"):
        raise ValueError(f"Typst did not produce a supported SVG: {raw_path.name}")
    root_tag = svg[: open_end + 1]
    if "aria-labelledby=" not in root_tag:
        root_tag = root_tag[:-1] + ' role="img" aria-labelledby="diagram-title diagram-desc">'
        svg = root_tag + svg[open_end + 1 :]
        open_end = len(root_tag) - 1
    metadata = (
        f'\n  <title id="diagram-title">{xml_escape(title)}</title>'
        f'\n  <desc id="diagram-desc">{xml_escape(description)}</desc>'
        f'\n  <metadata data-authored-concept="true" data-renderer="typst-{TYPST_VERSION}+cetz-{CETZ_VERSION}" />'
    )
    svg = svg[: open_end + 1] + metadata + svg[open_end + 1 :]
    view_box = re.search(r'viewBox="[^\"]*\s([0-9.]+)\s([0-9.]+)"', svg)
    if not view_box:
        raise ValueError(f"SVG viewBox not found: {raw_path.name}")
    label_y = float(view_box.group(2)) - label_bottom
    closing = svg.rfind("</svg>")
    if closing < 0:
        raise ValueError(f"SVG closing tag not found: {raw_path.name}")
    label = (
        f'\n  <text x="{label_x:g}" y="{label_y:g}" font-family="Noto Sans SC, Source Han Sans, sans-serif" '
        f'font-size="10.5" fill="#5D6A7C">{xml_escape(concept_label)}</text>\n'
    )
    output_path.write_text(svg[:closing] + label + svg[closing:], encoding="utf-8", newline="\n")


def xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--stem", default="scientific-study-design")
    parser.add_argument("--typst", type=Path)
    parser.add_argument("--font-name")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        if not SAFE_STEM.fullmatch(args.stem):
            raise ValueError("--stem must contain only ASCII letters, digits, underscore, or hyphen")
        spec_path = args.spec.expanduser().resolve()
        if not spec_path.is_file():
            raise FileNotFoundError(f"spec does not exist: {spec_path}")
        skill_root = Path(__file__).resolve().parent.parent
        template_root = skill_root / "assets" / "templates" / "typst"
        package_root = skill_root / "assets" / "typst-packages"
        values = validate_spec(json.loads(spec_path.read_text(encoding="utf-8-sig")))
        output_dir = args.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        executable = resolve_typst(args.typst)
        if not args.prepare_only:
            if executable is None:
                print(json.dumps({"status": "fallback_required", "reason": "Typst 0.13.1 executable was not found"}, ensure_ascii=False))
                return 3
            version = typst_version(executable)
            if version != TYPST_VERSION:
                print(json.dumps({"status": "fallback_required", "reason": f"Typst {TYPST_VERSION} is required; found {version}"}, ensure_ascii=False))
                return 3
            font_name = select_font(executable, args.font_name)
            if font_name is None:
                print(json.dumps({"status": "fallback_required", "reason": "No approved open-source Chinese font was found", "candidates": list(OPEN_FONT_CANDIDATES)}, ensure_ascii=False))
                return 3
        else:
            font_name = args.font_name or OPEN_FONT_CANDIDATES[0]
        values["FONT"] = font_name

        manifest: dict[str, Any] = {
            "status": "prepared" if args.prepare_only else "rendered",
            "renderer": f"typst-{TYPST_VERSION}+cetz-{CETZ_VERSION}",
            "font": font_name,
            "variants": {},
        }
        for variant, (template_name, width, height, label_x, label_bottom) in VARIANTS.items():
            source = output_dir / f"{args.stem}.{variant}.typ"
            prepare_source(template_root / template_name, source, values)
            entry: dict[str, Any] = {"source": source.name, "width": width, "height": height, "source_sha256": sha256(source)}
            if not args.prepare_only:
                final_svg = output_dir / f"{args.stem}.{variant}.svg"
                with tempfile.TemporaryDirectory(prefix="scientific-diagram-", dir=output_dir) as temp_name:
                    raw_svg = Path(temp_name) / f"{variant}.svg"
                    run_checked([
                        str(executable), "compile", "--jobs", "1", "--creation-timestamp", "0",
                        "--package-path", str(package_root), str(source), str(raw_svg),
                    ])
                    finalize_svg(raw_svg, final_svg, values["TITLE"], values["DESCRIPTION"], values["CONCEPT_LABEL"], label_x, label_bottom)
                entry.update({"svg": final_svg.name, "svg_sha256": sha256(final_svg), "bytes": final_svg.stat().st_size})
            manifest["variants"][variant] = entry
        manifest_path = output_dir / f"{args.stem}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        manifest["manifest"] = manifest_path.name
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
