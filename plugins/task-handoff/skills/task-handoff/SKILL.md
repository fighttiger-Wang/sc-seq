---
name: task-handoff
description: Maintain centralized, cross-session continuity records for named projects, software, codebases, and skills. Use when the user says continue, iterate, resume, found another problem, pick up previous work, pause, hand off, checkpoint, or asks to list, inspect, alias, merge, migrate, audit, or roll back handoff records; also use before the final response after substantive work on a stable named object so its record is created or updated automatically. Supports Chinese triggers such as “继续迭代”“接着上次”“又发现问题”“先停下”“写交接”。
---

# Task Handoff

Maintain the centralized store at `<shared-workspace-root>\.codex-handoff`. Resolve the workspace from `CODEX_SHARED_WORKSPACE_ROOT`; when running from the source marketplace, it is the parent directory of the marketplace. Do not create new project-root `HANDOFF.md` files.

Use the bundled Python script on Windows, macOS, and Linux:

```bash
python scripts/handoff_store.py <command> <arguments>
```

On Windows, the existing `handoff-store.ps1` remains a compatibility entrypoint. Prefer Python for new automation so the same commands work after cloning to macOS. Use the actual directory containing this selected `SKILL.md`; never reconstruct a user-profile cache path or assume a fixed drive layout. The installer writes `~/.codex/workspace-local.json`, which the Python entrypoint uses when environment variables are unavailable.

Read [store-format.md](references/store-format.md) before migration, merge, rollback, repair, or direct store editing.

## Start or Resume

1. Decide whether the task has a stable identity: named project, software product, codebase, or skill. Do not register anonymous one-off work.
2. Detect continuation intent such as continue, resume, iterate, another problem, or pick up previous work.
3. Resolve the object using its explicit name first, then aliases, skill ID, and absolute path anchors:

```bash
python scripts/handoff_store.py resolve --query '<name-or-path>'
```

4. If resolution returns multiple candidates or no candidate while similar objects exist, stop and ask the user. Never guess.
5. For one unique match, run `show`, read `CURRENT.md`, and verify relevant repository/filesystem reality before relying on it. Treat the record as potentially stale evidence.
6. Record the loaded revision. It is required as `-ExpectedRevision` during the final update.

For a new stable object, continue the task without creating a record immediately. Register and create the first record only after substantive work has produced useful facts.

## Update Before the Final Response

Update once, immediately before the final response, when any of these is true:

- substantive work completed;
- testing failed with reusable evidence;
- work is explicitly blocked;
- the user says to pause or stop.

Do not update for ordinary discussion, clarification, planning without implementation, or intermediate progress messages. A forced process termination, crash, or power loss cannot be recorded.

Write a concise UTF-8 Markdown file with exactly these sections:

```markdown
# <canonical name> continuity

> Status: completed | failed | blocked | paused | in-progress
> Updated: <absolute local timestamp with timezone>
> Revision basis: <loaded revision or new>

## Goal
## Changes
## Verification
## Open issues
## Pitfalls
```

Only include goals, material changes, verification evidence, unresolved issues, and actionable pitfalls. Do not paste chat transcripts, long diffs, secrets, credentials, customer data, or irrelevant command logs.

For an existing object:

```bash
python scripts/handoff_store.py commit --id '<id>' --content-path '<draft.md>' --expected-revision <loaded-revision> --status '<status>'
```

For a new object, register first with canonical name, type, aliases, and absolute anchors, then commit with expected revision `0`.

If the expected revision no longer matches, another task updated the same object. Stop and ask the user; never overwrite or auto-merge.

After committing, run `show` and verify that the reported revision, current content, and strongest remaining issue agree. The store retains at most 30 history entries per object.

## Evidence Rules

- Prefer repository and filesystem evidence over conversation claims or old records.
- Never claim a change, test, commit, push, or delivery without evidence.
- Mark uncertainty explicitly as `未验证`; mark external dependencies as `阻塞`.
- Preserve relevant uncommitted/untracked user work and distinguish it from the current task.
- Record failed approaches with observed evidence, cause when known, and the safer alternative.
- Do not commit, push, deploy, clean up, or delete merely to make a handoff tidy.

## Migration

Scan only the user-approved E-drive root. Ignore plugin/skill files whose path merely contains `handoff`; candidate legacy records are documentation files such as `HANDOFF.md` or `CODEX_HANDOFF.md`.

For every legacy file:

1. Identify the owning stable object and resolve or register it.
2. Compare all records for that object. If completion state, validation state, requirements, or next action conflict, stop for user adjudication.
3. Import each original file as an exact SHA-256-verified snapshot with `import-legacy`.
4. Commit one structured current record that retains still-valid facts from all sources.
5. Run `audit` and read the current record back.
6. Only after successful verification, run `finalize-legacy` for each exact source/snapshot pair. This deletes the old source but keeps its verified central snapshot subject to the 30-entry retention limit.

## Management

- `list`: list all registered objects and revisions.
- `resolve -Query <text>`: return a unique match or candidate list.
- `show -Id <id>`: print manifest and current record.
- `add-alias -Id <id> -Aliases <names>`: add non-conflicting aliases.
- `merge -SourceId <id> -TargetId <id> -ConfirmMerge`: merge duplicate identities only after explicit user confirmation.
- `rollback -Id <id> -Revision <n> -ExpectedRevision <n>`: create a new revision from an older history entry; never rewrite history.
- `audit`: verify registry, manifests, current files, hashes, locks, and the 30-entry limit.
- `unlock -Id <id> -ConfirmUnlock`: remove a stale lock only after confirming no other task is writing.

## Quality Gate

Do not finish until:

- the stable object is uniquely identified;
- the current state is verified against relevant files;
- the update status is truthful;
- current and history agree on the new revision;
- no concurrency mismatch or unresolved migration conflict was bypassed;
- no secrets or unnecessary personal/customer data were stored.
