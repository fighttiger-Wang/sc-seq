---
name: personal-skill-marketplace-setup
description: Bootstrap, audit, preflight, install, update, publish, repair, or relocate the user's shared workspace-local Codex skill marketplace on Windows or macOS. Use for deploying personal skills on a new computer, checking for stable updates before using a shared skill, publishing confirmed skill edits through a Git branch and pull request, repairing stale installations, or diagnosing cross-account and duplicate-source problems.
---

# Personal Skill Marketplace Setup

Use `scripts/setup.py` as the cross-platform manager. The Git checkout is authoritative; never edit an installed plugin cache as source.

## Release identity and promotion boundary

The remote Git repository's stable `main` ref is the cross-computer release authority. A local clone is only a working copy of that authority; a Codex plugin cache, a bare skill directory, an account-specific registration, a downloaded archive, or an annotation database is never an authority.

Every maintained Skill has two independent identities:

- a fixed workflow id such as `03` or `04`, used for lookup and ordering;
- an independent user-facing release version such as `v3.03`, used only after the user explicitly approves publication.

The immutable release identity is the tuple `skill id + release version + Git commit + content SHA-256`. A version string without the commit and hash is insufficient evidence of equality.

Unpublished edits are session-local or isolated-worktree candidates. They must not update the stable checkout, any marketplace registry, any Codex cache, any database record marked published, or the `/` callable entry. A test result is not publication consent.

After testing, report the changed files, affected Skill ids, proposed release versions, commit/hash evidence, and risks, then ask whether to publish. Only an explicit affirmative publication decision may promote the candidate, update release metadata, install the matching cache, and make the entry callable. If any synchronization or hash check fails, stop and leave the old callable version intact.

When a local machine or account cannot reach the remote stable ref, report that freshness is unverified; do not infer that a local cache is current. After a successful install or changed preflight, require a Codex restart and a new task before testing `/`.

```bash
python scripts/setup.py bootstrap --destination <approved-clone-path> --workspace-root <approved-workspace>
python scripts/setup.py preflight
python scripts/setup.py publish
python scripts/setup.py publish --confirm-publish [--create-pr]
python scripts/setup.py publish --confirm-publish --confirm-merge --workspace-root <approved-workspace>
python scripts/setup.py audit
python scripts/setup.py repair
```

Use Python 3.10 or newer. On Windows, use the actual workspace runtime when `python` is unavailable. On macOS, prefer `python3`. Pass `--codex-cli <full-path>` when `codex` is not in `PATH`.

## Mode routing

- `bootstrap`: first deployment after a temporary copy of this Skill exists. Require exact user-approved clone and workspace paths; clone, validate, install all plugins, register `workspace-local`, and add the managed synchronization block to the selected workspace `AGENTS.md` without replacing existing content.
- `preflight`: run once per task before first using or editing another `workspace-local` Skill. Fetch the stable ref and compare commits. Do nothing when current; fast-forward and reinstall affected plugins when behind; stop on dirty, detached, unexpected, ahead, or divergent state. If plugins changed, require a Codex restart and new task.
- `publish`: first run without `--confirm-publish` to report changed paths, affected plugins, proposed semantic patch versions, unregistered new-plugin directories, and tests. A new plugin must first be registered by `skill-writing` in `skill-pack.json` and both marketplace manifests. Ask the user for explicit confirmation. After confirmation, create or reuse a `codex/*` branch, automatically increment each affected plugin's patch version unless the candidate already changed it, synchronize display names and `skill-pack.json`, test, commit, push, and create or reuse a PR through authenticated GitHub access. Never push directly to `main`.
- `publish --confirm-publish --confirm-merge`: use only when the user's current request explicitly authorizes both publication and merge. The same request may authorize both; do not ask again merely because they were combined. After pushing, wait until every observed GitHub check/status succeeds, require the PR to be open, non-draft, and cleanly mergeable, merge with the exact head SHA, fetch and verify stable `main`, then refresh the complete local callable cache from a temporary detached stable worktree. Restore the original marketplace registration even when installation fails.
- `audit`: read-only source/config/install diagnosis; no fetch, pull, registration, or writes.
- `audit`: also report the release version, Git commit, content hash, source/cache classification, and whether the installed callable entry exactly matches the remote stable release. Never repair by choosing the newest-looking local copy.
- `install`: install an existing verified checkout, or clone to an exact approved destination. It does not add managed workspace guidance.
- `update`: legacy explicit full update; require a clean worktree, use `git pull --ff-only`, then validate and reinstall all plugins. Prefer `preflight` for routine use.
- `repair`: do not fetch or pull. Validate and reinstall the exact local versions.
- relocation is an explicit install/update option, not an automatic recovery path.

## GitHub transport and merge closeout

Publication uses two separate network paths: Git Smart HTTP for `fetch`/`push`, and the GitHub API for PR creation, status checks, and merge. Diagnose them independently.

When Git cannot reach `github.com` but browser, API, or raw-content requests work:

1. Confirm the remote URL with `git remote -v` and check DNS/HTTPS reachability.
2. On Windows, inspect the user proxy and local listener with `netsh winhttp show proxy`, the Internet Settings proxy values, and a loopback port test. Do not assume WinHTTP and user-level proxy settings are the same.
3. If a verified local proxy is available, set `http.proxy` only in the candidate repository's local Git config, for example `git config --local http.proxy http://127.0.0.1:<port>`. Re-test `git ls-remote origin main` before rerunning publish.
4. Never put credentials in Git config, source files, logs, command output, or handoff records. Reuse the configured credential helper only in memory.

If `gh` is unavailable, use the authenticated GitHub REST API as the fallback. Obtain the GitHub credential through the configured credential helper without printing it, and send API requests through the verified proxy when needed. Use this sequence:

1. `GET /repos/<owner>/<repo>/pulls/<number>` to confirm the PR is open, not draft, and `mergeable_state` is `clean`.
2. `POST /repos/<owner>/<repo>/pulls` to create the PR when no PR exists for the pushed `codex/*` branch; capture only its number and URL.
3. Merge only when the current user request explicitly authorizes merge. That authorization may be combined with publication in one request. Use `PUT /repos/<owner>/<repo>/pulls/<number>/merge` with the exact PR head SHA, then require `merged=true` and record the returned merge commit SHA.
4. Verify the remote stable channel after merging. Prefer `git fetch origin main` through the verified proxy and confirm the release commit is an ancestor of `origin/main`. If Git transport is flaky but the API works, query the PR's `merged`, `merged_at`, `merge_commit_sha`, and the repository `main` commit through the API; never rely on a stale local `origin/main` ref.
5. Only after stable verification tell the user the release is merged. If the PR is merely open, provide the PR URL and state that stable `main` is unchanged.

Record these as separate facts: branch pushed, PR created, PR merged, merge commit, stable `main` verification, and local installation sync. A successful push or merge API response alone does not prove that the local callable cache is updated.

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
4. `--confirm-publish` authorizes creating a development branch, version updates, tests, commit, push, and PR creation only for the reported marketplace changes. Merging additionally requires `--confirm-merge`, backed by an explicit current user request. Neither flag authorizes changing repository rules, deleting branches, force operations, or bypassing failed checks.
5. A pull request is a candidate release, not a synchronization result. Treat it as merged only when remote GitHub evidence reports the merge and the remote stable ref contains it. Other computers update from the stable ref, not from an open PR branch.
6. A passing doctor, unit test, or GitHub Actions run proves only those checks. It does not prove scientific interpretation, customer-facing output, R/Python packages, WPS, fonts, containers, credentials, or remote runtimes.
7. After install, update, repair, bootstrap, or a preflight that changed installed plugins, tell the user to restart Codex and open a new task.
8. Never batch-update or infer a coupled release for `sc-major-celltype-annotation-auto` and `sc-marker-cluster-annotation-auto`. They are independent Skills; update and publish only the explicitly named Skill(s). Do not invoke annotation knowledge-base publication as a side effect unless the user explicitly includes that scope.
9. Every maintained plugin's `plugin.json.interface.displayName` and `agents/openai.yaml.interface.display_name` must end with the same technical package version, rendered as `vX.Y.Z` before any `+codex...` cachebuster suffix. Audit must report a mismatch as a release failure; do not silently repair it from a cache.
10. The full release closeout order is fixed: semantic version increment, metadata synchronization, local tests, branch/commit/push, PR creation or reuse, CI success, clean mergeability, SHA-pinned merge, stable-main verification, stable preflight/doctor, cache refresh, registration restoration, and restart notice. Stop at the first failed gate and never report later stages as complete.

## Managed synchronization guidance

Bootstrap writes a marked block into the selected workspace `AGENTS.md`. The block instructs Codex to run preflight once per task before another shared Skill, excludes this setup Skill to prevent recursion, stops after an installed update, and asks before publishing changed marketplace files. Preserve all content outside the marked block.

The guidance is local to that workspace and computer. The repository, Actions, versions, and policy are shared through GitHub; clone paths, Git credentials, Codex registration, and the managed guidance installation are machine-local.

## Evidence in reports

Separate:

- `Fact`: observed path, command, branch, commit, dirty state, plugin version, or enabled status.
- `Prediction`: behavior still needing validation on the other operating system or account.
- `Recommendation`: workspace, backup, testing, or release-policy judgment.
