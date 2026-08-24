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
    resolved = [Path(value).resolve() for value in inputs]
    for input_path in resolved:
        require_e_drive(input_path, "original input")
        if not input_path.is_file():
            raise FileNotFoundError(f"original input path is missing: {input_path}")
    parents = {path.parent for path in resolved}
    if len(parents) != 1:
        raise ValueError(f"destination cannot be inferred from multiple input directories: {sorted(map(str, parents))}")
    return parents.pop()


def default_output_name(directory: Path) -> str:
    project_name = directory.name.strip()
    suffix = chr(0x5927) + chr(0x7c7b) + chr(0x6ce8) + chr(0x91ca)
    suffix += chr(0x7ed3) + chr(0x679c)
    suffix += chr(0x2e) + chr(0x78) + chr(0x6c) + chr(0x73) + chr(0x78)
    return project_name + suffix


def next_available(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy one validated annotation workbook to E: without overwriting.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--destination")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument('--output-name')
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
    directory = destination_arg.parent if destination_arg.suffix.lower() == ".xlsx" else destination_arg
    if args.output_name and Path(args.output_name).name != args.output_name:
        raise ValueError('output name must be a filename')
    if has_reparse_component(directory):
        raise ValueError(f"destination directory must not contain a junction/reparse point: {directory}")
    requested = destination_arg if destination_arg.suffix.lower() == ".xlsx" else destination_arg / source.name
    if destination_arg.suffix.lower() != chr(0x2e) + chr(0x78) + chr(0x6c) + chr(0x73) + chr(0x78):
        requested = destination_arg / (args.output_name or default_output_name(directory))
    destination = next_available(requested.absolute())
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(source)
    shutil.copy2(source, destination)
    destination_hash = sha256(destination)
    if source_hash != destination_hash:
        raise RuntimeError("destination hash does not match source after copy")
    print(json.dumps({
        "status": "copied", "source": str(source), "destination": str(destination),
        "destination_mode": "explicit" if args.destination else "inferred_from_original_inputs",
        "collision_policy": "numbered_no_overwrite", "sha256": source_hash, "copied_files": 1,
    }, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"status": "needs_delivery_path", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
