import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy only a validated final annotation workbook to an E-drive destination.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--destination")
    parser.add_argument("--input", action="append", default=[], help="Original input file; repeat for paired inputs to infer their common directory.")
    args = parser.parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    source = Path(args.source).resolve()
    destination_arg = Path(args.destination) if args.destination else infer_destination(args.input)
    require_e_drive(workspace_root, "workspace root")
    require_e_drive(source, "source")
    require_inside(source, workspace_root, "source")
    if source.suffix.lower() != ".xlsx" or not source.is_file():
        raise ValueError(f"source must be an existing .xlsx workbook: {source}")
    if not destination_arg.is_absolute():
        raise ValueError(f"destination must be an absolute E-drive path: {destination_arg}")
    require_e_drive(destination_arg, "destination")
    check_dir = destination_arg.parent if destination_arg.suffix.lower() == ".xlsx" else destination_arg
    if has_reparse_component(check_dir):
        raise ValueError(f"destination directory must not contain a junction/reparse point: {check_dir}")
    destination = destination_arg if destination_arg.suffix.lower() == ".xlsx" else destination_arg / source.name
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
    print(json.dumps({
        "status": "copied", "source": str(source), "destination": str(destination),
        "destination_mode": "explicit" if args.destination else "inferred_from_original_inputs",
        "sha256": source_hash, "copied_files": 1,
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "needs_delivery_path", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
