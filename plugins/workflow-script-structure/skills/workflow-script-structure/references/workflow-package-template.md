# Workflow Package Template

## Directory Layout

Single submission:

```text
workflow-name/
  00_user_config.sh
  work.sh
  base/
    common_runner.sh
    scripts/
      workflow_impl.R
```

Multiple submissions:

```text
workflow-name/
  00_user_config.sh
  1_prepare_inputs.sh
  2_run_analysis.sh
  3_collect_outputs.sh
  base/
    common_runner.sh
    scripts/
      prepare_inputs.R
      run_analysis.R
      collect_outputs.R
```

Keep bundled reference data in a descriptive implementation directory such as `base/reference/` or `base/marker_db/`.

## Root Configuration

```bash
#!/usr/bin/env bash

# Routine runs should only need edits in this file.
INPUT_PATH="/path/to/input"
RESULT_DIR="Result"

USE_SINGULARITY="1"
R_CMD="Rscript"
SIF_PATH="/path/to/container.sif"
BIND_PATHS="/mnt,/public,/work"

BACKGROUND="0"
```

## Shared Runner

```bash
#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMIT_DIR="${SUBMIT_DIR:-$(pwd)}"
CONFIG_FILE="${CONFIG_FILE:-$ROOT_DIR/00_user_config.sh}"

[[ -f "$CONFIG_FILE" ]] || {
  echo "Config not found: $CONFIG_FILE" >&2
  exit 1
}

# shellcheck disable=SC1090
source "$CONFIG_FILE"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  log "ERROR: $*" >&2
  exit 1
}

ensure_dir() {
  mkdir -p "$1"
}

result_root() {
  if [[ "${RESULT_DIR:-Result}" = /* ]]; then
    printf '%s' "${RESULT_DIR%/}"
  else
    printf '%s/%s' "$SUBMIT_DIR" "${RESULT_DIR%/}"
  fi
}

run_r_in_container() {
  local script_path="$1"
  local log_file="$2"
  shift 2 || true

  if [[ "${USE_SINGULARITY:-1}" =~ ^(1|true|TRUE|yes|YES|y|Y)$ ]]; then
    command -v singularity >/dev/null 2>&1 || fail "singularity not found"
    [[ -f "$SIF_PATH" ]] || fail "SIF not found: $SIF_PATH"
    singularity exec --bind "$BIND_PATHS" "$SIF_PATH" "$R_CMD" "$script_path" "$@" >> "$log_file" 2>&1
  else
    "$R_CMD" "$script_path" "$@" >> "$log_file" 2>&1
  fi
}
```

## Submission Entrypoint

```bash
#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/base/common_runner.sh"

LOG_DIR="$(result_root)/log"
LOG_FILE="$LOG_DIR/work.log"
R_SCRIPT="$SCRIPT_DIR/base/scripts/workflow_impl.R"
ensure_dir "$LOG_DIR"

run_r_in_container "$R_SCRIPT" "$LOG_FILE"
echo "Completed. Log: $LOG_FILE"
```

For multiple submissions, change only the step-specific log and implementation script in each numbered root entrypoint.

## Required Final QA

Run the portability checker on the staging directory and again on the final delivered directory. Use the checker from this skill's `scripts/` directory.

```bash
python /path/to/skill/scripts/check_shell_portability.py /path/to/staging-workflow --fix
python /path/to/skill/scripts/check_shell_portability.py /path/to/staging-workflow
python /path/to/skill/scripts/check_shell_portability.py /path/to/final-workflow
```

The final command must report zero failures. If Bash is unavailable, record `BASH_SYNTAX=SKIP` as a validation limitation and run `bash -n` later on the target cluster before analysis submission.

Also verify:

- every path referenced by root entrypoints exists;
- only the root config contains deployment-specific paths;
- no `.bak`, temporary run directory, alternate entrypoint, or stale path remains;
- implementation files parse with their available runtimes;
- final and staging manifests match after copying.
