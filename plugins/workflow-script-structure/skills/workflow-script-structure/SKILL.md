---
name: workflow-script-structure
description: Standardize and audit runnable workflow code packages by separating callable implementation code, editable parameters, and job submission scripts, while enforcing Linux/HPC Shell portability. Use when Codex creates, refactors, packages, or verifies bioinformatics/HPC/Singularity/Apptainer workflows; when SIF_PATH and BIND_PATHS must remain user-editable; or when cluster errors indicate CRLF/BOM problems such as invalid pipefail, bad interpreter, or $'\r'.
---

# Workflow Script Structure

Create repeatable workflow packages with one parameter surface, clear submission entrypoints, reusable implementation code, and Linux-safe Shell files.

## Required Separation

Organize deliverables into three layers:

1. **Callable code**: Put reusable implementation and helpers under `base/` or `base/scripts/`. Do not make these the routine user edit surface.
2. **Parameters**: Keep one editable root config, normally `00_user_config.sh`. Put input/output paths, analysis options, `SIF_PATH`, and `BIND_PATHS` here.
3. **Task submission**: Keep only human-submitted entrypoints at the workflow root. Each entrypoint sources the parameter layer and calls implementation code.

Do not hard-code deployment-specific container or bind paths in callable code.

## Submission Naming

- For one human submission, use root-level `work.sh`.
- For multiple submissions, use numbered root scripts in authoritative execution order, such as `1_prepare_inputs.sh`, `2_run_analysis.sh`, and `3_collect_outputs.sh`.
- Do not mix a primary `work.sh` with numbered primary entrypoints. A convenience wrapper must be clearly identified as optional.
- Move internal rerun, helper, and debug entrypoints under `base/`; do not leave them beside the human submission scripts.

## Shell Pattern

Prefer Bash entrypoints:

```bash
#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || exec bash "$0" "$@"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/base/common_runner.sh"
```

Route container execution through a shared helper and pass configurable bind paths explicitly:

```bash
singularity exec --bind "$BIND_PATHS" "$SIF_PATH" "$R_CMD" "$script_path" "$@"
```

## Mandatory Shell Portability Gate

Treat line endings and encoding as release-blocking requirements for every `.sh` file:

1. Store Shell files as UTF-8 without BOM and with Unix LF line endings.
2. Reject any carriage-return byte (`CR`, `0x0D`), including CRLF and stray CR. Bash otherwise reads values such as `pipefail\r` and fails on the cluster.
3. Normalize after every Windows-side generation, patch, copy, conversion, or final delivery. Do not assume a staging check remains valid after copying files.
4. Run the bundled checker against both the staging package and the final delivered directory:

```bash
python scripts/check_shell_portability.py /path/to/workflow
```

Use `--fix` only when normalization is authorized, then rerun without `--fix`:

```bash
python scripts/check_shell_portability.py /path/to/workflow --fix
python scripts/check_shell_portability.py /path/to/workflow
```

5. When Bash is available, also run `bash -n` on every `.sh`. The checker does this automatically. If Bash is unavailable, report that limitation explicitly; never claim Shell syntax validation passed solely from byte checks.
6. Do not hand off a workflow while the checker reports BOM, CR, invalid UTF-8, NUL bytes, missing shebangs, or Bash syntax errors.

## Structure Audit

When refactoring an existing package:

1. Inventory every file and build the active call graph from root entrypoints.
2. Separate active dependencies from backups, example configs, alternate entrypoints, and superseded implementations.
3. Preserve a recoverable E-drive backup before deleting material files.
4. Remove only files proven unreachable from the official entrypoints or explicitly obsolete.
5. Update all moved-path references, logs, configuration defaults, and concise handoff documentation.
6. Re-scan the final directory for stale paths, backup suffixes, deployment hard-coding, missing dependencies, and Shell portability.

## Quality Bar

- Make `00_user_config.sh` the only routine edit surface.
- Explain user-facing parameters with short comments.
- Resolve relative paths consistently from the submission directory or workflow root.
- Write logs under the configured result directory, such as `Result/log/`.
- Validate required inputs early with clear errors.
- Keep submission scripts small and move reusable logic into `base/`.
- Parse or compile implementation languages when runtimes are available.
- Compare the final delivery manifest with the validated staging manifest.
- Include a concise README only when the package needs human handoff instructions.

## Template Reference

Read `references/workflow-package-template.md` for layouts, starter snippets, and the required final QA sequence.
