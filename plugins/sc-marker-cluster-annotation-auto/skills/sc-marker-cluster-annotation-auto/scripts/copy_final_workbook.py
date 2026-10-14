import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def load_contract_module():
    local = Path(__file__).resolve().parent
    if (local / "qualitative_annotation_workbook.py").is_file():
        if str(local) not in sys.path:
            sys.path.insert(0, str(local))
        # Do not reuse a same-named module imported from a different plugin or
        # shared checkout; the copier must validate with this skill's bundled
        # contract.
        sys.modules.pop("qualitative_annotation_workbook", None)
        spec = importlib.util.spec_from_file_location(
            "qualitative_annotation_workbook", local / "qualitative_annotation_workbook.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot load bundled qualitative workbook contract")
        module = importlib.util.module_from_spec(spec)
        sys.modules["qualitative_annotation_workbook"] = module
        spec.loader.exec_module(module)
        return module
    for parent in Path(__file__).resolve().parents:
        shared = parent / "shared" / "sc-annotation-evidence-core"
        if (shared / "qualitative_annotation_workbook.py").is_file():
            if str(shared) not in sys.path:
                sys.path.insert(0, str(shared))
            import qualitative_annotation_workbook as module
            return module
    raise RuntimeError("Shared qualitative workbook contract module not found")


CONTRACT = load_contract_module()


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
    resolved_inputs = [Path(value).resolve() for value in inputs]
    for input_path in resolved_inputs:
        require_e_drive(input_path, "original input")
        if not input_path.is_file():
            raise FileNotFoundError(f"original input path is missing: {input_path}")
    parents = {input_path.parent for input_path in resolved_inputs}
    if len(parents) != 1:
        raise ValueError(f"destination cannot be inferred from multiple input directories: {sorted(map(str, parents))}")
    return parents.pop()


def default_output_name(directory: Path, timestamp: str | None = None) -> str:
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = directory.name.strip()
    return f"{project_name}_亚群注释结果_{timestamp}.xlsx"


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
    for r in range(2, src_sheet.max_row + 1):
        cluster_val = src_sheet.cell(r, col_cluster).value
        if cluster_val is None:
            continue
        en_val = src_sheet.cell(r, col_en).value or ""
        cn_val = src_sheet.cell(r, col_cn).value or ""
        records.append((str(cluster_val), str(en_val), str(cn_val)))

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

    ws.row_dimensions[1].height = 24
    for col_idx in range(1, 4):
        cell = ws.cell(1, col_idx)
        cell.font = font_header
        cell.alignment = align_center
        cell.fill = header_fill
        cell.border = thin_border

    for r_idx, (c_val, en_val, cn_val) in enumerate(records, 2):
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


def cleanup_legacy_non_timestamped(directory: Path, current_dest: Path, suffix_type: str = "亚群") -> list[str]:
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


def validate_formal_workbook(source: Path) -> dict:
    qa_path = source.with_suffix(".qa.json")
    if not qa_path.is_file():
        raise ValueError(f"formal workbook lacks builder QA sidecar: {qa_path}")
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    if qa.get("status") != "pass":
        raise ValueError(f"formal workbook QA status is not pass: {qa.get('status')}")
    actual_hash = sha256(source)
    if qa.get("workbook_sha256") != actual_hash:
        raise ValueError("formal workbook hash does not match its builder QA sidecar")

    workbook = load_workbook(source, read_only=False, data_only=False)
    expected = ["绘图列表", "注释结果", "详细证据", "细胞类型与文献", "说明与数据来源"]
    if workbook.sheetnames != expected:
        raise ValueError(f"formal workbook violates the five-sheet contract: {workbook.sheetnames}")
    headers = {
        "绘图列表": CONTRACT.PLOT_HEADERS,
        "注释结果": CONTRACT.RESULT_HEADERS,
        "详细证据": CONTRACT.EVIDENCE_HEADERS,
        "细胞类型与文献": CONTRACT.LITERATURE_HEADERS,
        "说明与数据来源": CONTRACT.SOURCE_HEADERS,
    }
    freezes = {"绘图列表": "A2", "注释结果": "D2", "详细证据": "D2", "细胞类型与文献": "B2", "说明与数据来源": "A2"}
    forbidden = {"Confidence", "Quality_score", "置信度", "质量评分", "候选评分", "评分差值"}
    red_rgb = {"FFF8696B", "F8696B"}
    for name in expected:
        sheet = workbook[name]
        observed_headers = [cell.value for cell in sheet[1]]
        if observed_headers != headers[name]:
            raise ValueError(f"{name} header contract mismatch")
        if forbidden.intersection(str(value) for value in observed_headers if value is not None):
            raise ValueError(f"{name} contains forbidden score/confidence headers")
        if sheet.auto_filter.ref is not None:
            raise ValueError(f"{name} must not enable autofilter")
        if str(sheet.freeze_panes) != freezes[name]:
            raise ValueError(f"{name} freeze panes mismatch: {sheet.freeze_panes}")
        for row in sheet.iter_rows():
            if row[0].row > 1 and sheet.row_dimensions[row[0].row].height is None:
                raise ValueError(f"{name} row {row[0].row} lacks fixed height")
            for cell in row:
                if cell.alignment.wrap_text or cell.alignment.shrink_to_fit:
                    raise ValueError(f"{name}!{cell.coordinate} enables wrapping or shrink-to-fit")
                rgb = str(cell.fill.fgColor.rgb or "").upper()
                allowed_red = (
                    (name == "绘图列表" and cell.column == 2 and cell.row > 1)
                    or (name == "注释结果" and cell.column == 2 and cell.row > 1)
                )
                if rgb in red_rgb and not allowed_red:
                    raise ValueError(
                        f"red warning fill is outside 绘图列表/Celltype_EN or 注释结果/中文名称: "
                        f"{name}!{cell.coordinate}"
                    )
    return qa


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy only a validated final annotation workbook to an E-drive destination.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--destination")
    parser.add_argument("--input", action="append", default=[], help="Original input file; repeat for paired inputs to infer their common directory.")
    parser.add_argument("--output-name", help="Explicit destination file name.")
    args = parser.parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    source = Path(args.source).resolve()
    destination_arg = Path(args.destination) if args.destination else infer_destination(args.input)
    require_e_drive(workspace_root, "workspace root")
    require_e_drive(source, "source")
    require_inside(source, workspace_root, "source")
    if source.suffix.lower() != ".xlsx" or not source.is_file():
        raise ValueError(f"source must be an existing .xlsx workbook: {source}")
    qa = validate_formal_workbook(source)
    if not destination_arg.is_absolute():
        raise ValueError(f"destination must be an absolute E-drive path: {destination_arg}")
    require_e_drive(destination_arg, "destination")
    check_dir = destination_arg.parent if destination_arg.suffix.lower() == ".xlsx" else destination_arg
    if has_reparse_component(check_dir):
        raise ValueError(f"destination directory must not contain a junction/reparse point: {check_dir}")

    now_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if destination_arg.suffix.lower() == ".xlsx":
        destination = destination_arg
    else:
        if args.output_name:
            out_name = args.output_name
            if not re.search(r"_\d{8}_\d{6}\.xlsx$", out_name, re.IGNORECASE):
                stem = Path(out_name).stem
                out_name = f"{stem}_{now_ts}.xlsx"
            destination = destination_arg / out_name
        elif re.search(r"_\d{8}_\d{6}\.xlsx$", source.name, re.IGNORECASE):
            destination = destination_arg / source.name
        elif "注释结果" in source.name or source.name in ("output.xlsx", "subcluster.xlsx", "final.xlsx"):
            destination = destination_arg / default_output_name(check_dir, now_ts)
        else:
            destination = destination_arg / source.name

    destination = destination.absolute()
    destination_dir = destination.parent
    if destination.suffix.lower() != ".xlsx":
        raise ValueError(f"destination workbook must end in .xlsx: {destination}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    if has_reparse_component(destination_dir):
        raise ValueError(f"destination directory must not contain a junction/reparse point: {destination_dir}")
    source_hash = sha256(source)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    destination_hash = sha256(destination)
    if source_hash != destination_hash:
        raise RuntimeError("destination hash does not match source after copy")

    cluster_info_path = destination_dir / "cluster注释信息.xlsx"
    export_cluster_info_workbook(destination, cluster_info_path)
    cleaned = cleanup_legacy_non_timestamped(destination_dir, destination, "亚群")

    registration = None
    try:
        records_candidate = source.parent / "annotation_records.json"
        if not records_candidate.is_file():
            records_candidate = source.parent / "records.json"
        evidence_candidate = source.parent / "annotation_evidence_pack.json"
        if not evidence_candidate.is_file():
            evidence_candidate = source.parent / "evidence.json"
        qa_path = source.with_suffix(".qa.json")

        if records_candidate.is_file() and qa_path.is_file():
            for p in Path(__file__).resolve().parents:
                reg_script = p / "shared" / "sc-annotation-case-registry" / "case_registry.py"
                if reg_script.is_file():
                    cmd = [
                        sys.executable, str(reg_script), "register",
                        "--records", str(records_candidate),
                        "--qa", str(qa_path),
                        "--project-dir", str(destination_dir),
                        "--skill-name", "sc-marker-cluster-annotation-auto",
                        "--skill-version", "0.7.8",
                    ]
                    if evidence_candidate.is_file():
                        cmd.extend(["--evidence", str(evidence_candidate)])
                    proc = subprocess.run(cmd, capture_output=True, text=True)
                    if proc.returncode == 0:
                        try:
                            registration = json.loads(proc.stdout)
                        except Exception:
                            registration = {"status": "registered_raw", "stdout": proc.stdout}
                    else:
                        registration = {"status": "failed", "stderr": proc.stderr}
                    break
    except Exception as exc:
        registration = {"status": "exception", "error": str(exc)}

    out_payload = {
        "status": "copied", "source": str(source), "destination": str(destination),
        "cluster_info_destination": str(cluster_info_path),
        "destination_mode": "explicit" if args.destination else "inferred_from_original_inputs",
        "sha256": source_hash, "qa_status": qa.get("status"), "copied_files": 2,
        "qa_sidecar_copied": False,
        "cleaned_non_timestamped": cleaned,
    }
    if registration:
        out_payload["case_registration"] = registration
    print(json.dumps(out_payload, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "needs_delivery_path", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
