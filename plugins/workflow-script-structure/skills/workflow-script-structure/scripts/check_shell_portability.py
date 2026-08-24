#!/usr/bin/env python3
"""Validate or normalize Shell files for Linux/HPC portability."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


UTF8_BOM = b"\xef\xbb\xbf"


def byte_issues(data: bytes) -> list[str]:
    issues: list[str] = []
    if data.startswith(UTF8_BOM):
        issues.append("UTF8_BOM")
    if b"\r" in data:
        issues.append("CR_BYTE")
    if b"\x00" in data:
        issues.append("NUL_BYTE")
    try:
        data.removeprefix(UTF8_BOM).decode("utf-8")
    except UnicodeDecodeError:
        issues.append("INVALID_UTF8")
    if not data.removeprefix(UTF8_BOM).startswith(b"#!"):
        issues.append("MISSING_SHEBANG")
    return issues


def normalize(data: bytes) -> bytes:
    normalized = data.removeprefix(UTF8_BOM)
    normalized = normalized.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Workflow directory to scan recursively")
    parser.add_argument("--fix", action="store_true", help="Remove UTF-8 BOM and convert CR/CRLF to LF")
    parser.add_argument("--require-bash", action="store_true", help="Fail when bash is unavailable")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR root is not a directory: {root}", file=sys.stderr)
        return 2

    shell_files = sorted(path for path in root.rglob("*.sh") if path.is_file())
    failures = 0
    fixed = 0

    for path in shell_files:
        data = path.read_bytes()
        issues = byte_issues(data)
        fixable = set(issues).issubset({"UTF8_BOM", "CR_BYTE"})
        if args.fix and issues and fixable:
            path.write_bytes(normalize(data))
            fixed += 1
            data = path.read_bytes()
            issues = byte_issues(data)

        relative = path.relative_to(root).as_posix()
        if issues:
            failures += 1
            print(f"FAIL {relative}: {','.join(issues)}")
        else:
            print(f"OK   {relative}")

    bash = shutil.which("bash")
    if bash:
        for path in shell_files:
            result = subprocess.run(
                [bash, "-n", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            relative = path.relative_to(root).as_posix()
            if result.returncode:
                failures += 1
                message = result.stderr.strip() or result.stdout.strip()
                print(f"BASH_FAIL {relative}: {message}")
            else:
                print(f"BASH_OK   {relative}")
    else:
        print("BASH_SYNTAX=SKIP (bash not available)")
        if args.require_bash:
            failures += 1

    print(
        f"SUMMARY shell_files={len(shell_files)} fixed={fixed} failures={failures}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
