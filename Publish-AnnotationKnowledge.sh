#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-$(command -v python3 || command -v python)}"
exec "$PYTHON_BIN" "$ROOT/tools/publish_annotation_knowledge.py" --marketplace-root "$ROOT" "$@"
