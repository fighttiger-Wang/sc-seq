#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

FORBIDDEN_TAGS = {"script", "foreignObject", "iframe", "audio", "video"}
EVENT_RE = re.compile(r"^on[a-z]+$", re.I)
CONCEPT_LABELS = ("概念示意", "非项目实测结果", "非数据结果")


def local_name(name):
    return name.rsplit("}", 1)[-1]


def validate(path, require_concept_label=False):
    errors, warnings = [], []
    raw = path.read_text(encoding="utf-8")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return [f"SVG XML parse failed: {exc}"], warnings, {}

    if local_name(root.tag) != "svg":
        errors.append("Root element is not <svg>")
    if not root.attrib.get("viewBox"):
        errors.append("Missing viewBox")

    tags = [local_name(element.tag) for element in root.iter()]
    for tag in FORBIDDEN_TAGS:
        if tag in tags:
            errors.append(f"Forbidden element: <{tag}>")

    title_count = tags.count("title")
    desc_count = tags.count("desc")
    text_count = tags.count("text")
    if title_count < 1:
        errors.append("Missing <title>")
    if desc_count < 1:
        errors.append("Missing <desc>")
    if text_count < 1:
        errors.append("No real SVG <text> elements found")

    for element in root.iter():
        for attr, value in element.attrib.items():
            name = local_name(attr)
            if EVENT_RE.match(name):
                errors.append(f"Event attribute is forbidden: {name}")
            if name in {"href", "src"}:
                parsed = urlparse(value)
                if parsed.scheme in {"http", "https", "file", "data"} or value.startswith("//"):
                    errors.append(f"External or embedded resource is forbidden: {value[:80]}")

    all_text = " ".join("".join(element.itertext()) for element in root.iter() if local_name(element.tag) == "text")
    if require_concept_label and not any(label in all_text for label in CONCEPT_LABELS):
        errors.append("Required visible concept/non-data label was not found")

    if "linearGradient" in tags or "radialGradient" in tags:
        warnings.append("Gradient detected; restrained flat fills are preferred")
    if len(raw.encode("utf-8")) > 2_000_000:
        warnings.append("SVG is larger than 2 MB")

    metrics = {
        "bytes": len(raw.encode("utf-8")),
        "text_elements": text_count,
        "title_elements": title_count,
        "desc_elements": desc_count,
    }
    return sorted(set(errors)), sorted(set(warnings)), metrics


def main():
    parser = argparse.ArgumentParser(description="Validate a self-contained scientific SVG.")
    parser.add_argument("svg", type=Path)
    parser.add_argument("--require-concept-label", action="store_true")
    args = parser.parse_args()
    errors, warnings, metrics = validate(args.svg, args.require_concept_label)
    result = {"file": str(args.svg.resolve()), "valid": not errors, "errors": errors, "warnings": warnings, "metrics": metrics}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
