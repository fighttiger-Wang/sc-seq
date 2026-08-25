---
name: personal-skill-marketplace-setup
description: Audit, download, install, update, or repair the user's shared workspace-local Codex skill marketplace on Windows or macOS. Use when the user asks to install personal skills on another computer, pull skill updates, repair missing or stale plugins, change the marketplace workspace, diagnose cross-account installation, or verify that the configured source and installed versions match.
---

# Personal Skill Marketplace Setup

Use the bundled cross-platform manager. It treats the source repository as authoritative and never edits an installed cache as source.

```bash
python scripts/setup.py audit
python scripts/setup.py install --marketplace-root <existing-clone>
python scripts/setup.py install --destination <new-clone-path>
python scripts/setup.py update
python scripts/setup.py repair
```

Python 3.10 or newer is required. On Windows, use the actual Python selected by the workspace when `python` is unavailable. On macOS, prefer `python3`. Pass `--codex-cli <full-path>` when `codex` is not in `PATH`.

## Bootstrap boundary

A clean computer cannot invoke this personal skill before any copy of it exists. Do not claim otherwise.

- Preferred first-time path: use ordinary Codex/Git instructions to clone the repository into a user-approved workspace and run its `Setup-PersonalSkillMarketplace.ps1` or `.sh` entrypoint.
- Optional path: the built-in `skill-installer` can install this skill from its GitHub subdirectory, but that creates a temporary bare-skill source. After the full marketplace is installed, report the duplicate-source risk and move the temporary source to a disabled backup only with user approval.
- Once `workspace-local` is installed, use this skill for later audit, update, repair, relocation checks, and account changes.

## Decision rules

1. Classify the request as `audit`, `install`, `update`, or `repair`. Do not perform a network update for an audit or repair unless the user asks.
2. Resolve the source from an explicit path, `CODEX_SHARED_MARKETPLACE_ROOT`, or `$CODEX_HOME/workspace-local.json`. Installed plugin cache paths are not valid source roots.
3. For a first clone, require a user-approved exact destination. There is no universally correct Windows/macOS workspace; drive layout, backup, permissions, free space, and organizational policy vary. Do not silently choose a home, system, cloud-sync, or removable-drive location. Keep the authoritative clone and shared workspace outside `CODEX_HOME`; reject either path when it contains, or is contained by, the Codex home.
4. Before changes, verify and report as facts: repository URL, target path, current branch and commit when available, dirty state, workspace root, Codex home, CLI resolution, plugin count from `skill-pack.json`, and whether network/authentication is required.
5. Stop on a remote mismatch, detached or unexpected branch when a ref was specified, dirty worktree before update, non-fast-forward pull, existing non-marketplace destination, conflicting `workspace-local.json`, ambiguous marketplace registration, or incomplete installed versions. Use `--relocate` only after the user explicitly approves moving the authoritative source; it may replace both the saved location and the configured `workspace-local` marketplace registration. Never use force push, reset, checkout-overwrite, recursive cleanup, `sudo`, Homebrew, Chocolatey, or package-manager installation without separate authorization.
6. Run the repository doctor before installation. After installation, require every plugin under `workspace-local` to be `installed, enabled` at the exact manifest version. Check for installed duplicates from other marketplaces and bare skill directories; report them without deleting.
7. A successful plugin install does not prove R/Python packages, WPS, fonts, containers, remote credentials, or bioinformatics runtimes are available. Keep those as separate dependency findings.
8. Do not call installation transactional. The location marker is written only after all exact plugin versions verify, but a Codex CLI failure can still leave some plugin installs changed and needing `repair`.
9. Distinguish evidence levels in the final report:
   - `Fact`: directly observed command, file, hash, version, path, or status.
   - `Prediction`: expected behavior that still needs validation on the target OS/account.
   - `Recommendation`: a judgment about workspace, backup, update cadence, or risk.
   Do not present Windows-only testing as proof of macOS compatibility.

## Mode behavior

- `audit`: read-only source/config/install diagnosis; no clone, pull, registration, or file writes.
- `install`: use an existing verified clone, or clone the expected repository into the exact approved destination, then validate and install all listed plugins.
- `update`: require a clean verified Git worktree, run ordinary `git pull --ff-only`, then validate and reinstall all plugins. A mutable `main` branch gives current state, not reproducible state; for strict reproduction, record the verified commit and use a reviewed tag or a separately checked-out commit before `install`/`repair`.
- `repair`: do not pull. Re-run doctor and reinstall the exact local versions, preserving the current source checkout.

After any install/update/repair, tell the user to restart Codex and open a new task. Existing tasks may retain the previous skill context.
