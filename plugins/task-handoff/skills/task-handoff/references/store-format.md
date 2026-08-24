# Central handoff store format

Store root: `<shared-workspace-root>\.codex-handoff`, where the root is resolved from `CODEX_SHARED_WORKSPACE_ROOT` or the source marketplace location.

```text
.codex-handoff/
├── registry.json
├── entities/
│   └── <id>/
│       ├── manifest.json
│       ├── CURRENT.md
│       └── history/
├── locks/
└── merged/
```

`registry.json` contains identity only: canonical ID, display name, type, aliases, and absolute anchors. Per-object `manifest.json` contains the mutable revision, status, timestamp, current hash, and history limit.

Every successful update creates a complete Markdown state in `history/` and atomically replaces `CURRENT.md`. Legacy imports are byte-for-byte snapshots in the same history sequence. Only the newest 30 history entries are retained.

Identity rules:

- IDs are lowercase ASCII hyphen-case.
- Exact ID, canonical name, alias, and anchor matches are authoritative.
- Partial matches only produce candidates; they never authorize automatic selection.
- An alias or anchor cannot belong to two active objects.

Concurrency rules:

- Mutating commands acquire an atomic directory lock.
- Commits and rollbacks require the revision read at task start.
- A revision mismatch or existing lock is a user-confirmation condition, not an auto-merge condition.

Recovery rules:

- Rollback creates a new revision from a prior snapshot.
- Merge preserves the source current state and retained history as target history entries before removing the duplicate identity.
- Legacy source deletion requires a matching SHA-256 snapshot and a successful audit.
- Do not directly edit `registry.json` or manifests unless the script cannot repair the store and the user approved manual recovery.
