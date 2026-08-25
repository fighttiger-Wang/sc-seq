---
name: personal-skill-marketplace-setup
description: Bootstrap, audit, preflight, install, update, publish, repair, or relocate the user's shared workspace-local Codex skill marketplace on Windows or macOS. Use for deploying personal skills on a new computer, checking for stable updates before using a shared skill, publishing confirmed skill edits through a Git branch and pull request, repairing stale installations, or diagnosing cross-account and duplicate-source problems.
---

# Personal Skill Marketplace Setup

Use `scripts/setup.py` as the cross-platform manager. The Git checkout is authoritative; never edit an installed plugin cache as source.

```bash
python scripts/setup.py bootstrap --destination <approved-clone-path> --workspace-root <approved-workspace>
python scripts/setup.py preflight
python scripts/setup.py publish
python scripts/setup.py publish --confirm-publish [--create-pr]
python scripts/setup.py audit
python scripts/setup.py repair
```

Use Python 3.10 or newer. On Windows, use the actual workspace runtime when `python` is unavailable. On macOS, prefer `python3`. Pass `--codex-cli <full-path>` when `codex` is not in `PATH`.

## Mode routing

- `bootstrap`: first deployment after a temporary copy of this Skill exists. Require exact user-approved clone and workspace paths; clone, validate, install all plugins, register `workspace-local`, and add the managed synchronization block to the selected workspace `AGENTS.md` without replacing existing content.
- `preflight`: run once per task before first using or editing another `workspace-local` Skill. Fetch the stable ref and compare commits. Do nothing when current; fast-forward and reinstall affected plugins when behind; stop on dirty, detached, unexpected, ahead, or divergent state. If plugins changed, require a Codex restart and new task.
- `publish`: first run without `--confirm-publish` to report changed paths, affected plugins, and tests. Ask the user for explicit confirmation. After confirmation, create or reuse a `codex/*` branch, update affected plugin cachebusters and `skill-pack.json`, test, commit, push, and optionally create a PR with authenticated GitHub CLI. Never push directly to `main`.
- `audit`: read-only source/config/install diagnosis; no fetch, pull, registration, or writes.
- `install`: install an existing verified checkout, or clone to an exact approved destination. It does not add managed workspace guidance.
- `update`: legacy explicit full update; require a clean worktree, use `git pull --ff-only`, then validate and reinstall all plugins. Prefer `preflight` for routine use.
- `repair`: do not fetch or pull. Validate and reinstall the exact local versions.
- relocation is an explicit install/update option, not an automatic recovery path.

## Clean-computer bootstrap boundary

A clean computer cannot invoke a Skill that has not been installed. Do not claim one-step self-bootstrap from nothing.

1. Use the built-in `skill-installer` to install this GitHub subdirectory temporarily:

   `plugins/personal-skill-marketplace-setup/skills/personal-skill-marketplace-setup`

2. Restart Codex and open a new task.
3. Invoke this Skill in `bootstrap` mode with exact approved paths.
4. After all marketplace plugins verify, report the temporary bare-skill duplicate. Move it to a recoverable `skills.disabled` backup only after explicit approval, using `--disable-bootstrap-copy`.

The bootstrap cannot log the user into GitHub, install Git/Python with an OS package manager, guess a Codex.app internal path, or silently choose a home/system/cloud-sync directory.

## Safety rules

1. Resolve the source from an explicit path, `CODEX_SHARED_MARKETPLACE_ROOT`, or `$CODEX_HOME/workspace-local.json`. Reject installed cache paths as source.
2. Keep the authoritative clone and shared workspace outside `CODEX_HOME`; reject overlapping locations, filesystem roots, home directories, nonempty unrelated destinations, remote mismatches, detached heads, unexpected refs, and conflicting location markers.
3. Never use force push, reset, checkout-overwrite, recursive cleanup, `sudo`, Homebrew, Chocolatey, or another package manager without separate authorization.
4. A publish confirmation authorizes creating a development branch, commit, and push only for the reported marketplace changes. It does not authorize merging `main`, changing repository rules, deleting branches, or bypassing failed checks.
5. A passing doctor, unit test, or GitHub Actions run proves only those checks. It does not prove scientific interpretation, customer-facing output, R/Python packages, WPS, fonts, containers, credentials, or remote runtimes.
6. After install, update, repair, bootstrap, or a preflight that changed installed plugins, tell the user to restart Codex and open a new task.

## Managed synchronization guidance

Bootstrap writes a marked block into the selected workspace `AGENTS.md`. The block instructs Codex to run preflight once per task before another shared Skill, excludes this setup Skill to prevent recursion, stops after an installed update, and asks before publishing changed marketplace files. Preserve all content outside the marked block.

The guidance is local to that workspace and computer. The repository, Actions, versions, and policy are shared through GitHub; clone paths, Git credentials, Codex registration, and the managed guidance installation are machine-local.

## Evidence in reports

Separate:

- `Fact`: observed path, command, branch, commit, dirty state, plugin version, or enabled status.
- `Prediction`: behavior still needing validation on the other operating system or account.
- `Recommendation`: workspace, backup, testing, or release-policy judgment.
