#!/usr/bin/env python3
"""Run static integrity checks on a generated standalone report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.internal_links: list[str] = []
        self.external_links: list[str] = []
        self.image_sources: list[str] = []
        self.image_alts: list[str | None] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.dialogs = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            href = values["href"] or ""
            if href.startswith("#"):
                self.internal_links.append(href[1:])
            elif href.startswith(("http://", "https://")):
                self.external_links.append(href)
        elif tag == "img":
            if "src" in values:
                self.image_sources.append(values.get("src") or "")
            self.image_alts.append(values.get("alt"))
        elif tag == "link" and values.get("rel") == "stylesheet":
            self.stylesheets.append(values.get("href") or "")
        elif tag == "script" and values.get("src"):
            self.scripts.append(values.get("src") or "")
        elif tag == "dialog":
            self.dialogs += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = args.report.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if report.drive.upper() != "E:":
            raise ValueError(f"Report must be on the E drive: {report}")
        raw = report.read_bytes()
        document = raw.decode("utf-8")
        parsed = ReportParser()
        parsed.feed(document)

        if not document.lstrip().lower().startswith("<!doctype html>"):
            errors.append("missing HTML5 doctype")
        if '<meta charset="utf-8">' not in document.lower():
            errors.append("missing UTF-8 charset declaration")
        if re.search(r"\{\{[A-Z_]+\}\}", document):
            errors.append("possible unresolved template placeholder")
        duplicates = sorted({value for value in parsed.ids if parsed.ids.count(value) > 1})
        if duplicates:
            errors.append("duplicate ids: " + ", ".join(duplicates))
        missing_targets = sorted({target for target in parsed.internal_links if target and target not in parsed.ids and target != "top"})
        if missing_targets:
            errors.append("internal links without targets: " + ", ".join(missing_targets))
        if any(not source.startswith("data:image/") for source in parsed.image_sources):
            errors.append("one or more images are not embedded data URIs")
        if any(not alt or not alt.strip() for alt in parsed.image_alts):
            errors.append("one or more images have empty alt text")
        if parsed.stylesheets:
            errors.append("external stylesheets present: " + ", ".join(parsed.stylesheets))
        if parsed.scripts:
            errors.append("external scripts present: " + ", ".join(parsed.scripts))
        for url in parsed.external_links:
            parsed_url = urlparse(url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                errors.append(f"invalid external citation URL: {url}")
        if parsed.image_sources and parsed.dialogs != 1:
            warnings.append(f"expected one image viewer dialog, found {parsed.dialogs}")
        if "linear-gradient" in document or "radial-gradient" in document:
            warnings.append("gradient detected; accepted visual system normally prohibits gradients")
        if "#17365d" not in document.lower() or "#f4f6f8" not in document.lower():
            warnings.append("expected navy/light-gray design tokens not found")
        if len(raw) > 150 * 1024 * 1024:
            warnings.append("report exceeds 150 MB and may be slow to transfer or open")
        if not re.search(r"未重新计算统计检验|existing statistical", document, flags=re.I):
            warnings.append("the default existing-statistics limitation was not found")

        result = {
            "report": str(report),
            "bytes": len(raw),
            "sections": len(parsed.ids),
            "embedded_images": len(parsed.image_sources),
            "external_citation_links": len(parsed.external_links),
            "errors": errors,
            "warnings": warnings,
            "static_result": "passed" if not errors else "failed",
            "visual_qa": "not performed by this static validator",
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0 if not errors else 1
    except Exception as exc:
        sys.stderr.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
