#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-$(command -v python3 || command -v python)}"
exec "$PYTHON_BIN" "$ROOT/tools/install_personal_skill_marketplace.py" --marketplace-root "$ROOT" "$@"
