#!/usr/bin/env python3
"""Create a cross-platform portable ZIP for the shared marketplace."""

from __future__ import annotations

import argparse
import hashlib
import re
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {".git", "logs", "outputs", "tmp", "__pycache__"}
SECRET_RE = re.compile(r"(^\.env($|\.)|\.pem$|\.key$|credentials|secrets?|\.sqlite3(?:-wal|-shm)?$)", re.I)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def selected_files(root: Path) -> list[Path]:
    result = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED or part.startswith("test_debug") for part in relative.parts):
            continue
        if path.suffix.lower() in {".pyc", ".pyo"} or SECRET_RE.search(path.name):
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def create_bundle(root: Path, output_dir: Path, bundle_name: str | None) -> dict:
    root = root.resolve()
    output_dir = output_dir.resolve()
    name = bundle_name or f"personal-codex-skills-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", name):
        raise ValueError("Bundle name must use letters, digits, dots, underscores, or hyphens")
    files = selected_files(root)
    if not files:
        raise RuntimeError("No files were selected for the bundle")
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{name}.zip"
    files_hash_path = output_dir / f"{name}.files.sha256"
    zip_hash_path = output_dir / f"{name}.zip.sha256"
    hash_lines = [f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in files]
    files_hash_path.write_text("\n".join(hash_lines) + "\n", encoding="utf-8")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo.from_file(path, relative)
            if path.suffix == ".sh":
                info.external_attr = (0o100755 & 0xFFFF) << 16
            with path.open("rb") as handle:
                archive.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        archive.writestr("bundle-files.sha256", "\n".join(hash_lines) + "\n")
    zip_hash = sha256(zip_path)
    zip_hash_path.write_text(f"{zip_hash}  {zip_path.name}\n", encoding="ascii")
    result = {"status": "created", "bundle": str(zip_path), "files": len(files), "sha256": zip_hash}
    print(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace-root", type=Path, default=ROOT)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--bundle-name")
    args = parser.parse_args()
    output = args.output_directory or args.marketplace_root / "outputs"
    create_bundle(args.marketplace_root, output, args.bundle_name)


if __name__ == "__main__":
    main()
