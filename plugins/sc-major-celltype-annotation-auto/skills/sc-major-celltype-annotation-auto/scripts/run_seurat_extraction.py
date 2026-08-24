#!/usr/bin/env python3
"""Launch R extraction with Windows UTF-8 locale and E-drive checks."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def require_e(path, role, must_exist=False):
    resolved = Path(path).resolve()
    if platform.system() == "Windows" and os.path.splitdrive(str(resolved))[0].upper() != "E:":
        raise ValueError(f"{role} must be on E: {resolved}")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"{role} not found: {resolved}")
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cluster-column", required=True)
    parser.add_argument("--object-name", default="")
    parser.add_argument("--assay", default="RNA")
    parser.add_argument("--slot", default="data")
    parser.add_argument("--min-pct", default="0.1")
    parser.add_argument("--logfc-threshold", default="0.25")
    parser.add_argument("--rscript", default="Rscript")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    input_path = require_e(args.input, "Seurat input", must_exist=True)
    output_dir = require_e(args.output_dir, "extraction output")
    output_dir.mkdir(parents=True, exist_ok=True)
    rscript = shutil.which(args.rscript) if args.rscript == "Rscript" else str(Path(args.rscript).resolve())
    if not rscript:
        raise FileNotFoundError("Rscript was not found")
    script = Path(__file__).resolve().with_name("extract_from_seurat.R")
    command = [rscript, script.as_posix(), "--input", input_path.as_posix(), "--output-dir", output_dir.as_posix(), "--cluster-column", args.cluster_column, "--assay", args.assay, "--slot", args.slot, "--min-pct", args.min_pct, "--logfc-threshold", args.logfc_threshold]
    if args.object_name:
        command.extend(["--object-name", args.object_name])
    env = os.environ.copy()
    env["CODEX_PYTHON"] = str(Path(args.python).resolve())
    if platform.system() == "Windows":
        env["LC_ALL"] = "Chinese (Simplified)_China.utf8"
        env["LANG"] = "Chinese (Simplified)_China.utf8"
    completed = subprocess.run(command, cwd=script.parent, env=env, text=True)
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
