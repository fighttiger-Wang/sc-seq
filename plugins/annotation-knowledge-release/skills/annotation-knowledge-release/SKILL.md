---
name: annotation-knowledge-release
description: Release and push the approved shared single-cell annotation knowledge base, synchronizing the major-celltype and subcluster annotation plugins with validation, regression tests, packaging, and cross-platform installation. Use when the user asks to 更新/发布/同步注释知识库、修复大类与亚类数据库错配、重新打包安装或推送这些知识更新到 GitHub.
---

# Annotation Knowledge Release

Operate on the source marketplace, never on an installed plugin cache. Locate it with the bundled helper:

```bash
python scripts/release.py --print-root
```

The canonical source is `<marketplace>/shared/sc-annotation-evidence-core`. The major and subcluster plugin copies are generated snapshots. Never edit those snapshots independently, and never commit the live case-registry SQLite, WAL, or SHM files.

## Release workflow

1. Resolve the marketplace and verify that its Git remote is the intended repository. Preserve unrelated user changes; stop if they overlap this release and cannot be separated safely.
2. For a read-only audit, run `python scripts/release.py --check-only`.
3. For a release, run `python scripts/release.py`. On Windows it uses `Publish-AnnotationKnowledge.ps1`; on macOS/Linux it uses the shared Python publisher. Pass `--source <approved-json>` only when the user names a specific approved bundle.
4. Require all version, SHA-256, snapshot, regression, doctor, packaging, and install gates to pass. Do not weaken or bypass a failed gate merely to publish.
5. Inspect `git diff`, `git diff --check`, and the staged file list. Exclude `tmp`, `outputs`, SQLite files, secrets, customer data, and machine-specific paths.
6. If the user asked to push, create one ordinary commit describing the release and run a normal push to the checked branch. Never force push. Verify the remote branch resolves to the local commit.
7. Report the commit, knowledge-base version and hash, plugin versions, test results, and portable ZIP hash. Tell the user to restart Codex and open a new task.

If the user asked only to check or prepare, stop before commit/push. A request such as “更新知识库并推送到 GitHub” explicitly authorizes the ordinary commit and push after validation; it does not authorize force push, history rewriting, or publishing an unapproved live case database.

## Cross-platform behavior

- Windows: PowerShell 7 or Windows PowerShell plus the repository `.ps1` entrypoints.
- macOS/Linux: Python 3 plus the repository `.sh`/Python entrypoints. The installer records the source path in `~/.codex/workspace-local.json`, so later tasks can locate the clone without a fixed drive or username.
- If `codex` is not in `PATH`, pass its full path through `--codex-cli`; do not guess an unavailable executable.
