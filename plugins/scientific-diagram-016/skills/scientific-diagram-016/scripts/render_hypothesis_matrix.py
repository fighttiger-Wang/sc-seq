#!/usr/bin/env python3

import argparse
import json
import re
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

WIDTH = 1600
MARGIN = 56
LABEL_WIDTH = 355
TITLE_HEIGHT = 150
HEADER_HEIGHT = 112
MIN_ROW_HEIGHT = 118
LINE_HEIGHT = 28
FOOTER_LINE_HEIGHT = 28

GROUP_STYLES = [
    ("#F7F8FA", "#AEB9C7", "#465568"),
    ("#FFF3F0", "#D9A19A", "#9B2C2C"),
    ("#F1F7F3", "#A9C2B0", "#3F6F52"),
    ("#EEF6FC", "#9BB9D6", "#2B6CB0"),
]
ROW_ACCENTS = ["#2B6CB0", "#A65E00", "#3F6F52", "#B42318", "#6B4E9B", "#357A77"]


def qname(name):
    return f"{{{SVG_NS}}}{name}"


def display_units(text):
    total = 0
    for char in text:
        total += 2 if unicodedata.east_asian_width(char) in {"W", "F", "A"} else 1
    return total


def wrap_text(text, max_units):
    text = re.sub(r"\s+", " ", str(text).strip())
    if not text:
        return []
    lines, current, units = [], "", 0
    for char in text:
        char_units = display_units(char)
        if current and units + char_units > max_units:
            lines.append(current.rstrip())
            current, units = "", 0
        current += char
        units += char_units
    if current.strip():
        lines.append(current.strip())
    return lines


def add_text(parent, x, y, lines, size, fill="#1E2A3A", weight="400", anchor="start", line_height=None):
    if not lines:
        return
    line_height = line_height or int(size * 1.35)
    text = ET.SubElement(parent, qname("text"), {
        "x": str(round(x, 2)),
        "y": str(round(y, 2)),
        "font-size": str(size),
        "font-weight": str(weight),
        "fill": fill,
        "text-anchor": anchor,
        "font-family": '"Noto Sans SC", "Source Han Sans", "Noto Sans CJK SC", "PingFang SC", sans-serif',
    })
    for index, line in enumerate(lines):
        attrs = {"x": str(round(x, 2)), "dy": "0" if index == 0 else str(line_height)}
        span = ET.SubElement(text, qname("tspan"), attrs)
        span.text = line


def require_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def validate_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError("Root JSON value must be an object")
    title = require_string(spec.get("title"), "title")
    groups = spec.get("groups")
    rows = spec.get("rows")
    if not isinstance(groups, list) or not 2 <= len(groups) <= 4:
        raise ValueError("groups must contain 2 to 4 items")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 6:
        raise ValueError("rows must contain 1 to 6 items")
    for gi, group in enumerate(groups):
        if not isinstance(group, dict):
            raise ValueError(f"groups[{gi}] must be an object")
        require_string(group.get("name"), f"groups[{gi}].name")
    for ri, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"rows[{ri}] must be an object")
        require_string(row.get("label"), f"rows[{ri}].label")
        states = row.get("states")
        if not isinstance(states, list) or len(states) != len(groups):
            raise ValueError(f"rows[{ri}].states must match the group count")
        for si, state in enumerate(states):
            require_string(state, f"rows[{ri}].states[{si}]")
    return title, groups, rows


def render(spec):
    title, groups, rows = validate_spec(spec)
    content_width = WIDTH - 2 * MARGIN
    group_width = (content_width - LABEL_WIDTH) / len(groups)
    state_units = max(12, int(group_width / 14))
    label_units = max(18, int(LABEL_WIDTH / 13))

    prepared_rows = []
    for row in rows:
        label_lines = wrap_text(row["label"], label_units)
        note_lines = wrap_text(row.get("note", ""), label_units + 6)
        state_lines = [wrap_text(state, state_units) for state in row["states"]]
        max_lines = max([len(label_lines) + (1 if note_lines else 0)] + [len(lines) for lines in state_lines])
        row_height = max(MIN_ROW_HEIGHT, 48 + max_lines * LINE_HEIGHT)
        prepared_rows.append((row, label_lines, note_lines, state_lines, row_height))

    footnotes = []
    for note in spec.get("footnotes", []):
        footnotes.extend(wrap_text(require_string(note, "footnotes[]"), 112))
    footer_height = 40 + max(1, len(footnotes)) * FOOTER_LINE_HEIGHT
    height = TITLE_HEIGHT + HEADER_HEIGHT + sum(item[4] for item in prepared_rows) + footer_height + MARGIN

    root = ET.Element(qname("svg"), {
        "width": str(WIDTH),
        "height": str(height),
        "viewBox": f"0 0 {WIDTH} {height}",
        "role": "img",
        "aria-labelledby": "title desc",
    })
    title_el = ET.SubElement(root, qname("title"), {"id": "title"})
    title_el.text = title
    desc_el = ET.SubElement(root, qname("desc"), {"id": "desc"})
    desc_el.text = spec.get("subtitle") or "Qualitative scientific comparison framework."

    ET.SubElement(root, qname("rect"), {
        "x": "1", "y": "1", "width": str(WIDTH - 2), "height": str(height - 2),
        "rx": "18", "fill": "#FFFFFF", "stroke": "#D7DEE7", "stroke-width": "2"
    })

    add_text(root, MARGIN + 8, 62, wrap_text(title, 58), 34, "#8B0000", "700")
    subtitle = spec.get("subtitle", "")
    add_text(root, MARGIN + 8, 108, wrap_text(subtitle, 108), 18, "#5F6F82", "400")

    disclaimer = spec.get("disclaimer", "")
    if disclaimer:
        box_width = min(390, max(250, display_units(disclaimer) * 10 + 44))
        box_x = WIDTH - MARGIN - box_width
        ET.SubElement(root, qname("rect"), {
            "x": str(box_x), "y": "30", "width": str(box_width), "height": "44",
            "rx": "7", "fill": "#FFF1EE", "stroke": "#D9A19A", "stroke-width": "1.4"
        })
        add_text(root, box_x + box_width / 2, 59, [disclaimer], 18, "#B42318", "600", "middle")

    header_y = TITLE_HEIGHT
    ET.SubElement(root, qname("rect"), {
        "x": str(MARGIN), "y": str(header_y), "width": str(LABEL_WIDTH), "height": str(HEADER_HEIGHT),
        "rx": "10", "fill": "#F7F8FA", "stroke": "#D7DEE7", "stroke-width": "1.3"
    })
    add_text(root, MARGIN + 26, header_y + 49, ["观察维度"], 22, "#1E2A3A", "700")
    add_text(root, MARGIN + 26, header_y + 79, ["定性预期，不编码数值"], 16, "#5F6F82", "400")

    for index, group in enumerate(groups):
        x = MARGIN + LABEL_WIDTH + index * group_width
        fill, stroke, accent = GROUP_STYLES[index]
        ET.SubElement(root, qname("rect"), {
            "x": str(round(x + 8, 2)), "y": str(header_y), "width": str(round(group_width - 16, 2)),
            "height": str(HEADER_HEIGHT), "rx": "10", "fill": fill, "stroke": stroke, "stroke-width": "1.4"
        })
        name_lines = wrap_text(group["name"], max(12, int(group_width / 13)))
        name_y = header_y + 45 - max(0, len(name_lines) - 1) * 12
        add_text(root, x + group_width / 2, name_y, name_lines, 24, accent, "700", "middle", 29)
        subtitle_lines = wrap_text(group.get("subtitle", ""), max(14, int(group_width / 11)))
        add_text(root, x + group_width / 2, header_y + 86, subtitle_lines[:1], 16, "#5F6F82", "400", "middle")

    y = header_y + HEADER_HEIGHT + 16
    for ri, (row, label_lines, note_lines, state_lines, row_height) in enumerate(prepared_rows):
        bg = "#FAFBFC" if ri % 2 == 0 else "#FFFFFF"
        ET.SubElement(root, qname("rect"), {
            "x": str(MARGIN), "y": str(y), "width": str(content_width), "height": str(row_height),
            "rx": "10", "fill": bg
        })
        accent = ROW_ACCENTS[ri]
        ET.SubElement(root, qname("rect"), {
            "x": str(MARGIN + 10), "y": str(y + 20), "width": "7", "height": str(row_height - 40),
            "rx": "3", "fill": accent
        })
        label_start = y + 42
        add_text(root, MARGIN + 36, label_start, label_lines, 21, "#1E2A3A", "600", "start", 28)
        if note_lines:
            note_y = label_start + len(label_lines) * 28 + 4
            add_text(root, MARGIN + 36, note_y, note_lines[:1], 16, "#5F6F82", "400")

        for gi, lines in enumerate(state_lines):
            x = MARGIN + LABEL_WIDTH + gi * group_width
            fill, stroke, group_accent = GROUP_STYLES[gi]
            cell_x = x + 22
            cell_y = y + 22
            cell_w = group_width - 44
            cell_h = row_height - 44
            ET.SubElement(root, qname("rect"), {
                "x": str(round(cell_x, 2)), "y": str(round(cell_y, 2)), "width": str(round(cell_w, 2)),
                "height": str(round(cell_h, 2)), "rx": "10", "fill": fill, "stroke": stroke, "stroke-width": "1.4"
            })
            text_y = cell_y + cell_h / 2 - (len(lines) - 1) * 14 + 8
            add_text(root, cell_x + cell_w / 2, text_y, lines, 20, group_accent, "600", "middle", 28)
        y += row_height

    footer_y = y + 22
    ET.SubElement(root, qname("line"), {
        "x1": str(MARGIN), "y1": str(footer_y - 12), "x2": str(WIDTH - MARGIN), "y2": str(footer_y - 12),
        "stroke": "#D7DEE7", "stroke-width": "1.2"
    })
    if footnotes:
        add_text(root, MARGIN + 8, footer_y + 16, footnotes, 17, "#5F6F82", "400", "start", FOOTER_LINE_HEIGHT)

    return ET.tostring(root, encoding="unicode")


def main():
    parser = argparse.ArgumentParser(description="Render a qualitative scientific hypothesis matrix as SVG.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.input.read_text(encoding="utf-8"))
    svg = render(spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "bytes": len(svg.encode("utf-8")), "rows": len(spec["rows"]), "groups": len(spec["groups"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
