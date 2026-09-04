# Shared Skill Git lifecycle

Use this workflow for every maintained `workspace-local` Skill on Windows or macOS.

## Release identity

The remote repository's stable `main` ref is the only cross-computer release authority. Keep the workflow number (for example `03`) fixed for lookup, and maintain an independent per-Skill visible release version (for example `v3.03`). Record both with the exact Git commit and a content SHA-256. Plugin cachebuster versions are technical installation metadata and must not replace the user-facing release version.

Draft edits belong to the current task's isolated worktree or staging copy. They are testable only through an explicit current-task path and are not registered, installed, published, or callable through `/`. After the test report, ask once for a single explicit authorization covering publication, CI-gated merge, stable verification, and installation. Promotion must be all-or-nothing across the selected Skill's source, manifests, release record, and installation; on a failed gate, retain the previous callable release. Use a PR-only outcome only when the user explicitly limits the request to publication only, PR only, no merge, or no install.

## Why a pull request exists

GitHub is the shared transport, while `main` is the stable release channel. A pull request keeps candidate changes on a `codex/*` branch so that conflicts, changed files, tests, and platform results can be reviewed before every computer consumes them. A PR is not required for Git to function, but it is the safety boundary that prevents an untested edit from immediately becoming the shared version.

Creating or opening a PR is not the same as merging it. Treat a PR as merged only after remote GitHub evidence reports `merged=true` and the remote `main` contains the merge result.

## Start of every edit task

1. Work only in the authoritative repository clone recorded by `workspace-local.json` or `CODEX_SHARED_MARKETPLACE_ROOT`.
2. Run `personal-skill-marketplace-setup` in `preflight` mode once before creating or editing another maintained Skill.
3. If the clone is dirty, detached, ahead, or divergent, stop and resolve it. Never force-pull, reset, or overwrite another computer's changes.
4. If preflight installs an update, restart Codex and open a new task before relying on the updated instructions.

## Existing Skill

Edit the existing plugin under `plugins/<id>`. Preserve its semantic ID and numbered display name unless the user explicitly changes the order. Validate the Skill, plugin, marketplace, and relevant behavior before publication.

## New Skill

Create one new plugin and Skill with the same lowercase ASCII hyphen-case ID. Assign the next unused display number and append it consistently. Before publication, the new ID must exist in all of:

- `plugins/<id>/.codex-plugin/plugin.json`;
- `plugins/<id>/skills/<id>/SKILL.md`;
- `plugins/<id>/skills/<id>/agents/openai.yaml`;
- `skill-pack.json`, with the plugin version and updated `expectedPluginCount`;
- `.agents/plugins/marketplace.json`;
- `.codex-plugin/marketplace.json`.

Both marketplace entries must use `INSTALLED_BY_DEFAULT`, `ON_INSTALL`, `./plugins/<id>`, and a real category. The display name in `plugin.json` and `openai.yaml` must be identical.

## Publish and PR

1. Run `personal-skill-marketplace-setup` in unconfirmed `publish` mode. This is a read-only plan.
2. If the plan reports an unregistered plugin, complete all registries and rerun validation. Do not bypass the error with manual Git commands.
3. Present changed paths, affected plugins, tests, target branch, and whether GitHub authentication is available.
4. Ask once for the full end-to-end release authorization. The question must explicitly cover version update, commit, push, PR creation, CI wait, SHA-pinned merge, stable-main verification, and local cache refresh. One affirmative reply authorizes the complete sequence; do not ask a second merge or installation question. If the user explicitly requests publication only, PR only, no merge, or no install, use the narrower PR-only route.
5. After the combined confirmation, let the setup Skill automatically increment unchanged semantic patch versions, synchronize display names/cachebusters/manifests, test, commit, and push a `codex/*` branch. Never push directly to `main`.
6. Create or reuse a PR through authenticated GitHub CLI/API access. Without authentication, return a compare URL; a merge-authorized run must stop because it cannot verify or merge the PR.
7. Under the single combined authorization, the setup Skill waits for all observed checks and commit statuses to succeed, requires a clean non-draft PR, merges with the exact head SHA, verifies that both release and merge commits are in remote `main`, and refreshes the local cache from verified stable content. It restores an original registration only when that source is clean, on the stable branch, and synchronized. Otherwise it preserves the old source as a work copy and retains/registers a persistent clean stable clone.

## After merge

On the releasing computer, a successful full closeout safely fast-forwards a clean registered stable source and refreshes the complete callable cache from verified stable `main`. It never overwrites or re-registers a dirty, divergent, detached, development, or non-Git source; that source remains a preserved work copy while a persistent clean stable clone becomes the runtime registration. Verify the actual versioned cache directories, cached manifests, and source-to-cache file hashes after final registration settles. On another computer, preflight compares the verified remote stable commit before the first relevant Skill use or edit in that task. When the commit is unchanged it does not download or reinstall anything. When `main` advanced, it performs a fast-forward update and installs affected plugins. Restart Codex after an installed update, then verify that the new task loaded the expected versioned `SKILL.md` path before declaring the release callable.

Machine-local items do not travel through GitHub: clone path, Git credentials, Codex home, marketplace registration, and the managed `AGENTS.md` trigger. Bootstrap configures these separately on every computer.
