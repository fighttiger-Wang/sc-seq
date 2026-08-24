#!/usr/bin/env python3
"""Inspect Seurat objects and candidate cluster columns without writing files."""

import argparse
import os
import platform
import shutil
import subprocess
from pathlib import Path


def require_e_input(path):
    resolved = Path(path).resolve()
    if platform.system() == "Windows" and os.path.splitdrive(str(resolved))[0].upper() != "E:":
        raise ValueError(f"Seurat input must be on E: {resolved}")
    if not resolved.exists():
        raise FileNotFoundError(f"Seurat input not found: {resolved}")
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--object-name", default="")
    parser.add_argument("--rscript", default="Rscript")
    args = parser.parse_args()

    input_path = require_e_input(args.input)
    rscript = shutil.which(args.rscript) if args.rscript == "Rscript" else str(Path(args.rscript).resolve())
    if not rscript:
        raise FileNotFoundError("Rscript was not found")
    script = Path(__file__).resolve().with_name("inspect_seurat_object.R")
    command = [rscript, script.as_posix(), "--input", input_path.as_posix()]
    if args.object_name:
        command.extend(["--object-name", args.object_name])
    env = os.environ.copy()
    if platform.system() == "Windows":
        env["LC_ALL"] = "Chinese (Simplified)_China.utf8"
        env["LANG"] = "Chinese (Simplified)_China.utf8"
    completed = subprocess.run(command, cwd=script.parent, env=env, text=True)
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()