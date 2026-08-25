#!/usr/bin/env bash

resolve_workspace_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    if command -v "$PYTHON" >/dev/null 2>&1; then
      command -v "$PYTHON"
      return 0
    fi
    if [[ -x "$PYTHON" ]]; then
      printf '%s\n' "$PYTHON"
      return 0
    fi
    printf 'Error: PYTHON is set but is not an executable command or file: %s\n' "$PYTHON" >&2
    return 127
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return 0
  fi

  printf '%s\n' 'Error: Python 3.10 or newer was not found. Install it or set PYTHON to its executable path.' >&2
  return 127
}
