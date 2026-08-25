#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-$(command -v python3 || command -v python)}"
"$PYTHON_BIN" "$ROOT/tools/test_personal_skill_marketplace.py" --marketplace-root "$ROOT"
exec "$PYTHON_BIN" "$ROOT/tools/new_personal_skill_bundle.py" --marketplace-root "$ROOT" "$@"
