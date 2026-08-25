#!/usr/bin/env python3
"""Locate the workspace-local source marketplace and invoke its publisher."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def is_marketplace(path: Path) -> bool:
    return (path / "skill-pack.json").is_file() and (path / "tools" / "publish_annotation_knowledge.py").is_file()


def locate() -> Path:
    candidates = []
    configured = os.environ.get("CODEX_SHARED_MARKETPLACE_ROOT")
    if configured:
        candidates.append(Path(configured).expanduser())
    markers = [Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser() / "workspace-local.json", Path.home() / ".codex" / "workspace-local.json"]
    for marker in dict.fromkeys(markers):
        if marker.is_file():
            value = json.loads(marker.read_text(encoding="utf-8")).get("marketplaceRoot")
            if value:
                candidates.append(Path(value).expanduser())
    for start in (Path.cwd(), Path(__file__).resolve()):
        cursor = start if start.is_dir() else start.parent
        candidates.extend([cursor, *cursor.parents])
    for candidate in candidates:
        resolved = candidate.resolve()
        if is_marketplace(resolved):
            return resolved
    raise FileNotFoundError("workspace-local source marketplace was not found. Clone the repository and run its installer first.")


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--print-root", action="store_true")
    known, remaining = parser.parse_known_args()
    root = locate()
    if known.print_root:
        print(root)
        return
    if os.name == "nt":
        script = root / "Publish-AnnotationKnowledge.ps1"
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
        translations = {"--check-only": "-CheckOnly", "--skip-tests": "-SkipTests", "--skip-bundle": "-SkipBundle", "--skip-install": "-SkipInstall", "--source": "-SourceKnowledgeBase", "--codex-cli": "-CodexCli"}
        index = 0
        while index < len(remaining):
            token = remaining[index]
            command.append(translations.get(token, token))
            index += 1
    else:
        command = [sys.executable, str(root / "tools" / "publish_annotation_knowledge.py"), "--marketplace-root", str(root), *remaining]
    raise SystemExit(subprocess.run(command, cwd=root).returncode)


if __name__ == "__main__":
    main()
