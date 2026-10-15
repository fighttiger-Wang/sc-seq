import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_e_drive(path: Path, role: str) -> None:
    if path.drive.upper() != "E:":
        raise ValueError(f"{role} must be an absolute E-drive path: {path}")


def require_inside(path: Path, root: Path, role: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{role} must be inside workspace root {root}: {path}") from exc


def is_reparse(path: Path) -> bool:
    if not path.exists():
        return False
    attrs = getattr(os.stat(path, follow_symlinks=False), "st_file_attributes", 0)
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def has_reparse_component(path: Path) -> bool:
    current = path.absolute()
    while True:
        if is_reparse(current):
            return True
        if current.parent == current:
            return False
        current = current.parent


def infer_destination(inputs: list[str]) -> Path:
    if not inputs:
        raise ValueError("destination cannot be inferred because no original input paths were provided")
    resolved = [Path(value).resolve() for value in inputs]
    for input_path in resolved:
        require_e_drive(input_path, "original input")
        if not input_path.is_file():
            raise FileNotFoundError(f"original input path is missing: {input_path}")
    parents = {path.parent for path in resolved}
    if len(parents) != 1:
        raise ValueError(f"destination cannot be inferred from multiple input directories: {sorted(map(str, parents))}")
    return parents.pop()


def default_output_name(directory: Path, timestamp: str | None = None) -> str:
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = directory.name.strip()
    return f"{project_name}_大类注释结果_{timestamp}.xlsx"


def next_available(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def export_cluster_info_workbook(source_workbook_path: Path, output_info_path: Path) -> Path:
    wb_source = load_workbook(source_workbook_path, data_only=True)
    if "注释结果" not in wb_source.sheetnames:
        raise ValueError(f"Source workbook lacks '注释结果' sheet: {source_workbook_path}")
    src_sheet = wb_source["注释结果"]

    header_row = [cell.value for cell in src_sheet[1]]
    try:
        col_cluster = header_row.index("Cluster") + 1
        col_en = header_row.index("Celltype_EN") + 1
        col_cn = header_row.index("中文名称") + 1
    except ValueError as exc:
        raise ValueError(f"Required column missing in '注释结果' sheet: {exc}")

    records = []
    red_rgb = {"FFF8696B", "F8696B"}
    for r in range(2, src_sheet.max_row + 1):
        cluster_val = src_sheet.cell(r, col_cluster).value
        if cluster_val is None:
            continue
        en_val = src_sheet.cell(r, col_en).value or ""
        cn_val = src_sheet.cell(r, col_cn).value or ""
        is_warning = False
        cn_cell_src = src_sheet.cell(r, col_cn)
        en_cell_src = src_sheet.cell(r, col_en)
        for cell_src in (cn_cell_src, en_cell_src):
            if cell_src.fill and cell_src.fill.fgColor:
                rgb = str(cell_src.fill.fgColor.rgb or "").upper()
                if rgb in red_rgb:
                    is_warning = True
                    break
        records.append((str(cluster_val), str(en_val), str(cn_val), is_warning))

    wb_info = Workbook()
    ws = wb_info.active
    ws.title = "cluster注释信息"

    headers = ["Cluster", "Celltype_EN", "中文名称"]
    ws.append(headers)

    font_header = Font(name="Cambria", size=11, bold=True)
    font_data = Font(name="Cambria", size=11)
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    red_fill = PatternFill(start_color="FFF8696B", end_color="FFF8696B", fill_type="solid")

    ws.row_dimensions[1].height = 24
    for col_idx in range(1, 4):
        cell = ws.cell(1, col_idx)
        cell.font = font_header
        cell.alignment = align_center
        cell.fill = header_fill
        cell.border = thin_border

    for r_idx, (c_val, en_val, cn_val, is_warning) in enumerate(records, 2):
        ws.row_dimensions[r_idx].height = 20
        c_cell = ws.cell(r_idx, 1, value=int(c_val) if c_val.isdigit() else c_val)
        c_cell.font = font_data
        c_cell.alignment = align_center
        c_cell.border = thin_border

        en_cell = ws.cell(r_idx, 2, value=en_val)
        en_cell.font = font_data
        en_cell.alignment = align_left
        en_cell.border = thin_border

        cn_cell = ws.cell(r_idx, 3, value=cn_val)
        cn_cell.font = font_data
        cn_cell.alignment = align_left
        cn_cell.border = thin_border

        if is_warning:
            en_cell.fill = red_fill
            cn_cell.fill = red_fill

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = None

    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            val_len = sum(2 if ord(char) > 127 else 1 for char in val_str)
            if val_len > max_len:
                max_len = val_len
        ws.column_dimensions[col_letter].width = max(14, max_len + 3)

    output_info_path.parent.mkdir(parents=True, exist_ok=True)
    wb_info.save(output_info_path)
    return output_info_path


def cleanup_legacy_non_timestamped(directory: Path, current_dest: Path, suffix_type: str = "大类") -> list[str]:
    cleaned = []
    base_name = directory.name.strip()
    candidates = [
        directory / f"{base_name}_{suffix_type}注释结果.xlsx",
        directory / f"{base_name}{suffix_type}注释结果.xlsx",
    ]
    for cand in candidates:
        if cand.is_file() and cand.resolve() != current_dest.resolve():
            try:
                cand.unlink()
                cleaned.append(str(cand))
            except Exception:
                pass
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy one validated annotation workbook to E: without overwriting.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--destination")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--output-name")
    args = parser.parse_args()

    workspace = Path(args.workspace_root).resolve()
    source = Path(args.source).resolve()
    destination_arg = Path(args.destination) if args.destination else infer_destination(args.input)
    require_e_drive(workspace, "workspace root")
    require_e_drive(source, "source")
    require_inside(source, workspace, "source")
    if source.suffix.lower() != ".xlsx" or not source.is_file():
        raise ValueError(f"source must be an existing .xlsx workbook: {source}")
    if not destination_arg.is_absolute():
        raise ValueError(f"destination must be an absolute E-drive path: {destination_arg}")
    require_e_drive(destination_arg, "destination")

    now_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = destination_arg.parent if destination_arg.suffix.lower() == ".xlsx" else destination_arg
    if args.output_name and Path(args.output_name).name != args.output_name:
        raise ValueError("output name must be a filename")
    if has_reparse_component(directory):
        raise ValueError(f"destination directory must not contain a junction/reparse point: {directory}")

    if destination_arg.suffix.lower() == ".xlsx":
        requested = destination_arg
    else:
        if args.output_name:
            out_name = args.output_name
            if not re.search(r"_\d{8}_\d{6}\.xlsx$", out_name, re.IGNORECASE):
                stem = Path(out_name).stem
                out_name = f"{stem}_{now_ts}.xlsx"
            requested = destination_arg / out_name
        elif re.search(r"_\d{8}_\d{6}\.xlsx$", source.name, re.IGNORECASE):
            requested = destination_arg / source.name
        else:
            requested = destination_arg / default_output_name(directory, now_ts)

    destination = next_available(requested.absolute())
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(source)
    shutil.copy2(source, destination)
    destination_hash = sha256(destination)
    if source_hash != destination_hash:
        raise RuntimeError("destination hash does not match source after copy")

    cluster_info_path = directory / "cluster注释信息.xlsx"
    export_cluster_info_workbook(destination, cluster_info_path)
    cleaned = cleanup_legacy_non_timestamped(directory, destination, "大类")

    print(json.dumps({
        "status": "copied", "source": str(source), "destination": str(destination),
        "cluster_info_destination": str(cluster_info_path),
        "destination_mode": "explicit" if args.destination else "inferred_from_original_inputs",
        "collision_policy": "numbered_no_overwrite", "sha256": source_hash, "copied_files": 2,
        "cleaned_non_timestamped": cleaned,
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "needs_delivery_path", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
