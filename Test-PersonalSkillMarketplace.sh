#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$ROOT/tools/resolve-python.sh"
PYTHON_BIN="$(resolve_workspace_python)"
exec "$PYTHON_BIN" "$ROOT/tools/test_personal_skill_marketplace.py" --marketplace-root "$ROOT" "$@"
