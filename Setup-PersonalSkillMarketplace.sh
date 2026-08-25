#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$ROOT/tools/resolve-python.sh"
PYTHON_BIN="$(resolve_workspace_python)"
MODE="${1:-install}"
if [[ $# -gt 0 ]]; then shift; fi
exec "$PYTHON_BIN" "$ROOT/plugins/personal-skill-marketplace-setup/skills/personal-skill-marketplace-setup/scripts/setup.py" "$MODE" --marketplace-root "$ROOT" "$@"
