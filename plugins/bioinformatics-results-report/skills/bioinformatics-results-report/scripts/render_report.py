#!/usr/bin/env python3
"""Render a structured report specification into a versioned standalone HTML file."""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SAFE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SAFE_STEM = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}


def discover_workspace_root() -> Path:
    configured = os.environ.get("CODEX_SHARED_WORKSPACE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    for parent in Path(__file__).resolve().parents:
        if (parent / "skill-pack.json").is_file():
            return parent.parent
    return Path.cwd().resolve()


def ensure_e_drive(path: Path, kind: str) -> Path:
    resolved = path.resolve()
    if resolved.drive.upper() != "E:":
        raise ValueError(f"{kind} must be on the E drive: {resolved}")
    return resolved


def text(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def citations(items: list[dict[str, Any]] | None) -> str:
    if not items:
        return ""
    links = []
    for item in items:
        label = str(item.get("label", "文献依据")).strip()
        url = str(item.get("url", "")).strip()
        if not valid_url(url):
            raise ValueError(f"Citation URL must be an absolute http(s) URL: {url!r}")
        links.append(f'<a class="citation" href="{text(url)}" target="_blank" rel="noopener noreferrer">{text(label)}</a>')
    return '<span class="citations" aria-label="文献依据">' + "".join(links) + "</span>"


def resolve_source(raw_path: str, base_dir: Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    candidate = ensure_e_drive(candidate, "Figure source")
    if not candidate.is_file():
        raise FileNotFoundError(f"Figure source not found: {candidate}")
    if candidate.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"Unsupported figure type: {candidate.suffix}")
    return candidate


def pdf_page_to_png(path: Path, page: int, temp_dir: Path) -> Path:
    if page < 1:
        raise ValueError("pdf_page is 1-based and must be at least 1")
    executable_value = shutil.which("pdftoppm") or shutil.which("pdftoppm.cmd")
    if not executable_value:
        raise RuntimeError("PDF rendering requires pdftoppm, but it is not available in PATH")
    executable = Path(executable_value)
    if executable.suffix.lower() == ".cmd":
        candidates = []
        if len(executable.parents) >= 3:
            candidates.append(executable.parents[2] / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe")
        if len(executable.parents) >= 2:
            candidates.append(executable.parents[1] / "Library" / "bin" / "pdftoppm.exe")
        executable = next((candidate for candidate in candidates if candidate.is_file()), executable)
    prefix = temp_dir / "pdf-page"
    command = [str(executable), "-f", str(page), "-l", str(page), "-singlefile", "-png", "-r", "180", str(path), str(prefix)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"pdftoppm failed for {path.name} page {page}: {detail}")
    output = prefix.with_suffix(".png")
    if not output.is_file():
        raise RuntimeError(f"pdftoppm did not create the expected page image: {output}")
    return output


def optimize_image(path: Path, max_dimension: int, temp_dir: Path, pdf_page: int = 1) -> tuple[str, int, int]:
    working = pdf_page_to_png(path, pdf_page, temp_dir) if path.suffix.lower() == ".pdf" else path
    with Image.open(working) as source:
        source.load()
        image = source.copy()
    width, height = image.size
    longest = max(width, height)
    if longest > max_dimension:
        ratio = max_dimension / longest
        image = image.resize((max(1, round(width * ratio)), max(1, round(height * ratio))), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    suffix = working.suffix.lower()
    has_alpha = image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
    if suffix in {".jpg", ".jpeg"} and not has_alpha:
        image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True, progressive=True)
        mime = "image/jpeg"
    else:
        if image.mode not in {"RGB", "RGBA", "L", "LA", "P"}:
            image = image.convert("RGBA" if has_alpha else "RGB")
        image.save(output, format="PNG", optimize=True, compress_level=9)
        mime = "image/png"
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}", image.width, image.height


def render_figure(item: dict[str, Any], base_dir: Path, max_dimension: int, temp_dir: Path) -> str:
    source = resolve_source(str(item.get("path", "")), base_dir)
    data_uri, width, height = optimize_image(source, max_dimension, temp_dir, int(item.get("pdf_page", 1)))
    alt = str(item.get("alt", "")).strip()
    if not alt:
        raise ValueError(f"Figure requires a meaningful alt description: {source.name}")
    layout = str(item.get("layout", "normal"))
    if layout not in {"normal", "wide"}:
        raise ValueError(f"Unknown figure layout: {layout}")
    figure_class = "figure-wide" if layout == "wide" else ""
    title_value = str(item.get("title", source.stem)).strip()
    caption = str(item.get("caption", "")).strip()
    source_label = str(item.get("source", source.name)).strip()
    return (
        f'<figure class="{figure_class}"><div class="figure-media">'
        f'<button type="button" data-image-viewer aria-label="放大查看：{text(title_value)}">'
        f'<img src="{data_uri}" alt="{text(alt)}" width="{width}" height="{height}" loading="lazy"></button></div>'
        f'<figcaption><strong>{text(title_value)}</strong><span>{text(caption)}</span>'
        f'<small class="source">来源：{text(source_label)}</small></figcaption></figure>'
    )


def render_table(block: dict[str, Any]) -> str:
    columns = block.get("columns") or []
    rows = block.get("rows") or []
    if not columns:
        raise ValueError("Table block requires columns")
    header = "".join(f"<th scope=\"col\">{text(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(f"Table row length {len(row)} does not match {len(columns)} columns")
        body_rows.append("<tr>" + "".join(f"<td>{text(cell)}</td>" for cell in row) + "</tr>")
    title_html = f'<div class="table-title">{text(block.get("title"))}</div>' if block.get("title") else ""
    note_html = f'<div class="table-note">{text(block.get("note"))}</div>' if block.get("note") else ""
    return f'{title_html}<div class="table-wrap"><table><thead><tr>{header}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>{note_html}'


def render_block(block: dict[str, Any], base_dir: Path, max_dimension: int, temp_dir: Path) -> str:
    block_type = str(block.get("type", ""))
    if block_type == "paragraph":
        return f'<p>{text(block.get("text"))}{citations(block.get("citations"))}</p>'
    if block_type == "heading":
        return f'<h3>{text(block.get("text"))}</h3>'
    if block_type == "callout":
        tone = str(block.get("tone", "info"))
        if tone not in {"info", "warning", "danger", "success"}:
            raise ValueError(f"Unknown callout tone: {tone}")
        title_html = f'<strong>{text(block.get("title"))}</strong>' if block.get("title") else ""
        return f'<div class="callout {tone}">{title_html}<p>{text(block.get("text"))}{citations(block.get("citations"))}</p></div>'
    if block_type == "findings":
        cards = []
        for item in block.get("items") or []:
            cards.append(
                f'<div class="insight"><span class="value">{text(item.get("value"))}</span>'
                f'<strong>{text(item.get("title"))}</strong><p>{text(item.get("text"))}</p></div>'
            )
        return '<div class="insight-grid">' + "".join(cards) + "</div>"
    if block_type == "list":
        tag = "ol" if block.get("ordered") else "ul"
        return f'<{tag}>' + "".join(f"<li>{text(item)}</li>" for item in block.get("items") or []) + f'</{tag}>'
    if block_type == "image":
        return render_figure(block, base_dir, max_dimension, temp_dir)
    if block_type == "image-grid":
        images = block.get("images") or []
        if not images:
            raise ValueError("image-grid requires at least one image")
        css_class = "figure-grid single" if len(images) == 1 else "figure-grid"
        return f'<div class="{css_class}">' + "".join(render_figure(item, base_dir, max_dimension, temp_dir) for item in images) + "</div>"
    if block_type == "table":
        return render_table(block)
    raise ValueError(f"Unsupported block type: {block_type!r}")


def render_summary(summary: dict[str, Any]) -> str:
    parts = ['<section class="section" id="summary"><div class="section-eyebrow">核心摘要</div><h2>主要结论与证据边界</h2>']
    if summary.get("lead"):
        parts.append(f'<p class="lead">{text(summary.get("lead"))}</p>')
    findings = summary.get("findings") or []
    if findings:
        parts.append('<div class="insight-grid">')
        for index, finding in enumerate(findings, 1):
            parts.append(f'<div class="insight"><span class="value">{index:02d}</span><strong>核心发现</strong><p>{text(finding)}</p></div>')
        parts.append("</div>")
    limitations = summary.get("limitations") or []
    if limitations:
        parts.append('<div class="callout warning"><strong>优先阅读的证据限制</strong><ul>')
        parts.extend(f"<li>{text(item)}</li>" for item in limitations)
        parts.append("</ul></div>")
    parts.append('<a class="back" href="#top">返回顶部</a></section>')
    return "".join(parts)


def next_output_path(folder: Path, stem: str) -> Path:
    clean = SAFE_STEM.sub("_", stem).strip(" ._")
    if not clean:
        raise ValueError("output_stem becomes empty after filename sanitization")
    for version in range(1, 1000):
        candidate = folder / f"{clean}_v{version:03d}.html"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"No free version number remains for {clean}")


def render(spec: dict[str, Any], spec_path: Path, template_path: Path, max_dimension: int, temp_root: Path) -> tuple[str, Path]:
    base_dir_value = spec.get("base_dir")
    base_dir = ensure_e_drive(Path(base_dir_value) if base_dir_value else spec_path.parent, "Base directory")
    if not base_dir.is_dir():
        raise ValueError(f"Base directory does not exist: {base_dir}")
    title_value = str(spec.get("title", "")).strip()
    if not title_value:
        raise ValueError("Report title is required")
    project_label = str(spec.get("project_label", "项目结果报告")).strip()
    sections = spec.get("sections") or []
    seen_ids = {"summary", "conclusion"}
    toc = ['<li><a href="#summary">核心摘要</a></li>']
    section_html = []
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bioinfo-report-", dir=temp_root) as temp_name:
        temp_dir = Path(temp_name)
        for section in sections:
            section_id = str(section.get("id", ""))
            if not SAFE_ID.fullmatch(section_id):
                raise ValueError(f"Section id must be ASCII lower-case hyphen-case: {section_id!r}")
            if section_id in seen_ids:
                raise ValueError(f"Duplicate or reserved section id: {section_id}")
            seen_ids.add(section_id)
            section_title = str(section.get("title", "")).strip()
            if not section_title:
                raise ValueError(f"Section {section_id} requires a title")
            toc.append(f'<li><a href="#{text(section_id)}">{text(section_title)}</a></li>')
            parts = [f'<section class="section" id="{text(section_id)}">']
            if section.get("eyebrow"):
                parts.append(f'<div class="section-eyebrow">{text(section.get("eyebrow"))}</div>')
            parts.append(f'<h2>{text(section_title)}</h2>')
            if section.get("lead"):
                parts.append(f'<p class="lead">{text(section.get("lead"))}</p>')
            for block in section.get("blocks") or []:
                parts.append(render_block(block, base_dir, max_dimension, temp_dir))
            parts.append('<a class="back" href="#top">返回顶部</a></section>')
            section_html.append("".join(parts))
    toc.append('<li><a href="#conclusion">综合结论</a></li>')

    meta = "".join(f'<span class="chip">{text(item.get("label"))}：{text(item.get("value"))}</span>' for item in spec.get("meta") or [])
    kpis = "".join(
        f'<div class="kpi"><strong>{text(item.get("value"))}</strong><span>{text(item.get("label"))}</span></div>'
        for item in (spec.get("kpis") or [])
    )
    hero = (
        f'<header class="hero"><div class="eyebrow">{text(project_label)}</div><h1>{text(title_value)}</h1>'
        f'<p>{text(spec.get("subtitle", "基于既有统计结果与可核查文献的综合判读"))}</p><div class="hero-meta">{meta}</div></header>'
    )
    content = [hero]
    if kpis:
        content.append(f'<div class="kpis" aria-label="项目概览">{kpis}</div>')
    content.append(render_summary(spec.get("summary") or {}))
    content.extend(section_html)
    content.append(
        f'<section class="section" id="conclusion"><div class="section-eyebrow">综合判断</div><h2>结论、转化意义与后续验证</h2>'
        f'<div class="conclusion">{text(spec.get("conclusion", ""))}</div><a class="back" href="#top">返回顶部</a></section>'
    )
    content.append(f'<footer class="foot">{text(spec.get("footer", "基于用户提供的既有统计结果生成；未重新计算统计检验。"))}</footer>')

    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": text(title_value),
        "{{PROJECT_LABEL}}": text(project_label),
        "{{TOC}}": "".join(toc),
        "{{CONTENT}}": "".join(content),
    }
    for marker, value in replacements.items():
        if marker not in template:
            raise ValueError(f"Template is missing marker {marker}")
        template = template.replace(marker, value)
    if re.search(r"\{\{[A-Z_]+\}\}", template):
        raise ValueError("Template contains unresolved placeholders")
    output = next_output_path(base_dir, str(spec.get("output_stem", title_value)))
    return template, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--template", type=Path, default=Path(__file__).resolve().parent.parent / "assets" / "report-shell.html")
    parser.add_argument("--max-dimension", type=int, default=2400)
    parser.add_argument("--temp-dir", type=Path, default=discover_workspace_root() / "tmp")
    args = parser.parse_args()
    try:
        spec_path = ensure_e_drive(args.spec, "Report specification")
        template_path = ensure_e_drive(args.template, "Template")
        temp_root = ensure_e_drive(args.temp_dir, "Temporary directory")
        if args.max_dimension < 1200 or args.max_dimension > 5000:
            raise ValueError("--max-dimension must be between 1200 and 5000")
        spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
        rendered, output = render(spec, spec_path, template_path, args.max_dimension, temp_root)
        output.write_text(rendered, encoding="utf-8", newline="\n")
        sys.stdout.write(json.dumps({"output": str(output), "bytes": output.stat().st_size}, ensure_ascii=False) + "\n")
        return 0
    except Exception as exc:
        sys.stderr.write(json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
