#!/usr/bin/env python3
"""Cross-platform centralized task-handoff store."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


HISTORY_LIMIT = 30
ID_RE = re.compile(r"[^a-z0-9]+")
HEADINGS = ("## Goal", "## Changes", "## Verification", "## Open issues", "## Pitfalls")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def stamp() -> str:
    value = datetime.now().astimezone()
    return value.strftime("%Y%m%dT%H%M%S") + f"{value.microsecond // 1000:03d}" + value.strftime("%z")


def normalize_id(value: str) -> str:
    normalized = ID_RE.sub("-", value.lower()).strip("-")
    if not normalized or len(normalized) > 64:
        raise ValueError(f"Invalid normalized id: {normalized}")
    return normalized


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".tmp-{uuid.uuid4().hex}"
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


def atomic_json(path: Path, value) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def resolve_marketplace() -> Path | None:
    configured = os.environ.get("CODEX_SHARED_MARKETPLACE_ROOT")
    if configured:
        path = Path(configured).expanduser().resolve()
        if (path / "skill-pack.json").is_file():
            return path
    markers = [Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser() / "workspace-local.json", Path.home() / ".codex" / "workspace-local.json"]
    for marker in dict.fromkeys(markers):
        if marker.is_file():
            value = json.loads(marker.read_text(encoding="utf-8")).get("marketplaceRoot")
            if value:
                path = Path(value).expanduser().resolve()
                if (path / "skill-pack.json").is_file():
                    return path
    cursor = Path(__file__).resolve().parent
    for candidate in (cursor, *cursor.parents):
        if (candidate / "skill-pack.json").is_file():
            return candidate
    return None


class Store:
    def __init__(self, store_root: Path | None) -> None:
        marketplace = resolve_marketplace()
        configured_workspace = os.environ.get("CODEX_SHARED_WORKSPACE_ROOT")
        if configured_workspace:
            self.workspace = Path(configured_workspace).expanduser().resolve()
        elif marketplace:
            self.workspace = marketplace.parent
        else:
            markers = [Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser() / "workspace-local.json", Path.home() / ".codex" / "workspace-local.json"]
            marker = next((item for item in dict.fromkeys(markers) if item.is_file()), None)
            if marker is None:
                raise RuntimeError("Shared workspace could not be resolved. Run the marketplace installer first.")
            self.workspace = Path(json.loads(marker.read_text(encoding="utf-8"))["workspaceRoot"]).expanduser().resolve()
        configured_allowed = os.environ.get("CODEX_SHARED_ALLOWED_ROOT")
        self.allowed = Path(configured_allowed).expanduser().resolve() if configured_allowed else self.workspace.parent
        self.root = self.safe(store_root.expanduser().resolve() if store_root else self.workspace / ".codex-handoff")
        self.registry_path = self.root / "registry.json"
        self.entities_root = self.root / "entities"
        self.locks_root = self.root / "locks"
        self.merged_root = self.root / "merged"
        self.initialize()

    def safe(self, path: Path) -> Path:
        path = path.resolve()
        try:
            path.relative_to(self.allowed)
        except ValueError as exc:
            raise ValueError(f"Path must stay under {self.allowed}: {path}") from exc
        return path

    def initialize(self) -> None:
        for path in (self.root, self.entities_root, self.locks_root, self.merged_root):
            path.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.is_file():
            atomic_json(self.registry_path, {"schemaVersion": 1, "storeRoot": str(self.root), "historyLimit": HISTORY_LIMIT, "entities": []})

    def registry(self):
        value = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if value.get("schemaVersion") != 1:
            raise RuntimeError(f"Unsupported registry schema: {value.get('schemaVersion')}")
        return value

    def entity_dir(self, entity_id: str) -> Path:
        return self.entities_root / normalize_id(entity_id)

    def manifest_path(self, entity_id: str) -> Path:
        return self.entity_dir(entity_id) / "manifest.json"

    def current_path(self, entity_id: str) -> Path:
        return self.entity_dir(entity_id) / "CURRENT.md"

    def history_dir(self, entity_id: str) -> Path:
        return self.entity_dir(entity_id) / "history"

    def manifest(self, entity_id: str):
        path = self.manifest_path(entity_id)
        if not path.is_file():
            raise KeyError(f"Manifest not found for entity: {entity_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def save_manifest(self, entity_id: str, value) -> None:
        atomic_json(self.manifest_path(entity_id), value)

    def find(self, registry, entity_id: str):
        normalized = normalize_id(entity_id)
        return next((item for item in registry["entities"] if item["id"] == normalized), None)

    def history_files(self, entity_id: str) -> list[Path]:
        directory = self.history_dir(entity_id)
        return sorted(directory.glob("rev-*.md")) if directory.is_dir() else []

    def history_path(self, entity_id: str, revision: int, kind: str) -> Path:
        return self.history_dir(entity_id) / f"rev-{revision:04d}-{stamp()}-{kind}.md"

    def trim_history(self, entity_id: str) -> None:
        files = self.history_files(entity_id)
        for path in files[:-HISTORY_LIMIT]:
            path.unlink()

    @contextmanager
    def lock(self, lock_id: str):
        path = self.locks_root / f"{normalize_id(lock_id)}.lock"
        try:
            path.mkdir()
        except FileExistsError as exc:
            raise RuntimeError(f"Concurrent or stale lock detected: {path}. Stop and ask the user before unlock.") from exc
        atomic_json(path / "owner.json", {"createdAt": now_iso(), "processId": os.getpid()})
        try:
            yield
        finally:
            if path.exists():
                shutil.rmtree(path)

    def add_revision(self, entity_id: str, text: str, expected: int, status: str, kind: str = "update", validate: bool = True):
        manifest = self.manifest(entity_id)
        if expected >= 0 and int(manifest["currentRevision"]) != expected:
            raise RuntimeError(f"Revision mismatch for '{entity_id}': expected {expected}, actual {manifest['currentRevision']}. Stop for user confirmation.")
        if validate:
            missing = [heading for heading in HEADINGS if heading not in text]
            if missing:
                raise ValueError(f"Missing required headings: {', '.join(missing)}")
        revision = int(manifest["currentRevision"]) + 1
        history = self.history_path(entity_id, revision, kind)
        atomic_text(history, text)
        atomic_text(self.current_path(entity_id), text)
        manifest.update({"currentRevision": revision, "status": status, "updatedAt": now_iso(), "currentSha256": sha256(self.current_path(entity_id)), "historyLimit": HISTORY_LIMIT})
        self.save_manifest(entity_id, manifest)
        self.trim_history(entity_id)
        return {"id": entity_id, "revision": revision, "status": status, "currentPath": str(self.current_path(entity_id)), "historyPath": str(history), "sha256": manifest["currentSha256"]}


def identity_values(entity) -> list[str]:
    return [str(value) for value in [entity.get("id"), entity.get("name"), *entity.get("aliases", []), *entity.get("anchors", [])] if value]


def assert_available(registry, values: list[str], except_id: str = "") -> None:
    for value in values:
        for entity in registry["entities"]:
            if entity["id"] == except_id:
                continue
            if any(owned.casefold() == value.casefold() for owned in identity_values(entity)):
                raise ValueError(f"Identity value already belongs to '{entity['id']}': {value}")


def emit(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("init", "register", "resolve", "show", "list", "commit", "import-legacy", "finalize-legacy", "add-alias", "merge", "rollback", "audit", "unlock"))
    parser.add_argument("--store-root", type=Path)
    parser.add_argument("--id")
    parser.add_argument("--name")
    parser.add_argument("--type", default="other", choices=("project", "software", "codebase", "skill", "other"))
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument("--anchor", action="append", default=[])
    parser.add_argument("--query")
    parser.add_argument("--content-path", type=Path)
    parser.add_argument("--expected-revision", type=int, default=-1)
    parser.add_argument("--status", default="completed", choices=("completed", "failed", "blocked", "paused", "in-progress", "migrated"))
    parser.add_argument("--source-path", type=Path)
    parser.add_argument("--snapshot-path", type=Path)
    parser.add_argument("--source-id")
    parser.add_argument("--target-id")
    parser.add_argument("--revision", type=int, default=-1)
    parser.add_argument("--confirm-merge", action="store_true")
    parser.add_argument("--confirm-unlock", action="store_true")
    args = parser.parse_args()
    store = Store(args.store_root)
    command = args.command
    if command == "init":
        emit({"storeRoot": str(store.root), "registryPath": str(store.registry_path), "historyLimit": HISTORY_LIMIT})
    elif command == "register":
        with store.lock("registry"):
            registry = store.registry()
            entity_id = normalize_id(args.id or "")
            if store.find(registry, entity_id):
                raise ValueError(f"Entity already exists: {entity_id}")
            if not args.name:
                raise ValueError("Name is required")
            anchors = [str(store.safe(Path(item).expanduser())) for item in dict.fromkeys(args.anchor)]
            aliases = list(dict.fromkeys(item for item in args.alias if item))
            assert_available(registry, [entity_id, args.name, *aliases, *anchors])
            entity = {"id": entity_id, "name": args.name, "type": args.type, "aliases": aliases, "anchors": anchors, "createdAt": now_iso()}
            registry["entities"].append(entity)
            atomic_json(store.registry_path, registry)
            store.history_dir(entity_id).mkdir(parents=True, exist_ok=True)
            store.save_manifest(entity_id, {"schemaVersion": 1, "id": entity_id, "currentRevision": 0, "status": "in-progress", "updatedAt": None, "currentSha256": None, "historyLimit": HISTORY_LIMIT})
            emit(entity)
    elif command == "resolve":
        if not args.query:
            raise ValueError("Query is required")
        query = args.query.strip()
        query_path = Path(query).expanduser().resolve() if Path(query).is_absolute() else None
        results = []
        for entity in store.registry()["entities"]:
            exact = [entity["id"], entity["name"], *entity.get("aliases", [])]
            score, reason = 0, ""
            if any(value.casefold() == query.casefold() for value in exact):
                score, reason = 100, "exact-name-or-alias"
            elif query_path and any(Path(value).resolve() == query_path for value in entity.get("anchors", [])):
                score, reason = 100, "exact-anchor"
            elif any(query.casefold() in value.casefold() or value.casefold() in query.casefold() for value in exact):
                score, reason = 50, "partial-name-or-alias"
            elif query_path and any(query_path.is_relative_to(Path(value).resolve()) or Path(value).resolve().is_relative_to(query_path) for value in entity.get("anchors", [])):
                score, reason = 40, "related-anchor"
            if score:
                results.append({"id": entity["id"], "name": entity["name"], "type": entity["type"], "score": score, "reason": reason})
        results.sort(key=lambda item: (-item["score"], item["id"]))
        emit({"query": query, "unique": len(results) == 1 and results[0]["score"] == 100, "candidates": results})
    elif command == "show":
        registry = store.registry()
        entity = store.find(registry, args.id or "")
        if not entity:
            raise KeyError(f"Unknown entity: {args.id}")
        current = store.current_path(entity["id"])
        emit({"entity": entity, "manifest": store.manifest(entity["id"]), "currentPath": str(current), "currentExists": current.is_file()})
        if current.is_file():
            print(current.read_text(encoding="utf-8"), end="")
    elif command == "list":
        rows = []
        for entity in sorted(store.registry()["entities"], key=lambda item: item["id"]):
            manifest = store.manifest(entity["id"])
            rows.append({**entity, "revision": manifest["currentRevision"], "status": manifest["status"], "updatedAt": manifest["updatedAt"]})
        emit(rows)
    elif command == "commit":
        content = store.safe((args.content_path or Path("")).expanduser())
        if not content.is_file():
            raise FileNotFoundError(content)
        entity_id = normalize_id(args.id or "")
        with store.lock(entity_id):
            emit(store.add_revision(entity_id, content.read_text(encoding="utf-8"), args.expected_revision, args.status))
    elif command == "import-legacy":
        entity_id = normalize_id(args.id or "")
        source = store.safe((args.source_path or Path("")).expanduser())
        with store.lock(entity_id):
            manifest = store.manifest(entity_id)
            revision = int(manifest["currentRevision"]) + 1
            destination = store.history_path(entity_id, revision, "legacy")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            if sha256(source) != sha256(destination):
                destination.unlink()
                raise RuntimeError("Legacy snapshot hash verification failed")
            manifest.update({"currentRevision": revision, "status": "migrated", "updatedAt": now_iso()})
            store.save_manifest(entity_id, manifest)
            store.trim_history(entity_id)
            emit({"id": entity_id, "revision": revision, "sourcePath": str(source), "snapshotPath": str(destination), "sha256": sha256(source)})
    elif command == "finalize-legacy":
        source = store.safe((args.source_path or Path("")).expanduser())
        snapshot = store.safe((args.snapshot_path or Path("")).expanduser())
        if sha256(source) != sha256(snapshot):
            raise RuntimeError("Source and snapshot hashes do not match")
        issues = audit(store)
        if issues:
            raise RuntimeError(f"Audit failed; refusing deletion: {issues}")
        source.unlink()
        emit({"deleted": str(source), "recoverableFrom": str(snapshot), "sha256": sha256(snapshot)})
    elif command == "add-alias":
        with store.lock("registry"):
            registry = store.registry()
            entity = store.find(registry, args.id or "")
            if not entity:
                raise KeyError(f"Unknown entity: {args.id}")
            additions = list(dict.fromkeys(item for item in args.alias if item))
            assert_available(registry, additions, entity["id"])
            entity["aliases"] = list(dict.fromkeys([*entity.get("aliases", []), *additions]))
            atomic_json(store.registry_path, registry)
            emit(entity)
    elif command == "rollback":
        entity_id = normalize_id(args.id or "")
        matches = [path for path in store.history_files(entity_id) if path.name.startswith(f"rev-{args.revision:04d}-")]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one history file for revision {args.revision}; found {len(matches)}")
        with store.lock(entity_id):
            emit(store.add_revision(entity_id, matches[0].read_text(encoding="utf-8"), args.expected_revision, "in-progress", "rollback", False))
    elif command == "merge":
        if not args.confirm_merge:
            raise ValueError("Merge requires --confirm-merge")
        source_id, target_id = normalize_id(args.source_id or ""), normalize_id(args.target_id or "")
        with store.lock("registry"):
            with store.lock(source_id), store.lock(target_id):
                registry = store.registry()
                source = store.find(registry, source_id)
                target = store.find(registry, target_id)
                if not source or not target:
                    raise KeyError("Source or target entity not found")
                for path in [*store.history_files(source_id), *([store.current_path(source_id)] if store.current_path(source_id).is_file() else [])]:
                    manifest = store.manifest(target_id)
                    revision = int(manifest["currentRevision"]) + 1
                    destination = store.history_path(target_id, revision, "merged")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
                    manifest.update({"currentRevision": revision, "updatedAt": now_iso()})
                    store.save_manifest(target_id, manifest)
                target_current = store.current_path(target_id)
                if not target_current.is_file() and store.current_path(source_id).is_file():
                    shutil.copy2(store.current_path(source_id), target_current)
                target["aliases"] = list(dict.fromkeys([*target.get("aliases", []), source["id"], source["name"], *source.get("aliases", [])]))
                target["anchors"] = list(dict.fromkeys([*target.get("anchors", []), *source.get("anchors", [])]))
                registry["entities"] = [item for item in registry["entities"] if item["id"] != source_id]
                atomic_json(store.registry_path, registry)
                shutil.rmtree(store.entity_dir(source_id))
                manifest = store.manifest(target_id)
                store.add_revision(target_id, target_current.read_text(encoding="utf-8"), int(manifest["currentRevision"]), manifest["status"], "merge", False)
                store.trim_history(target_id)
                emit({"source": source_id, "target": target_id, "sourceRemoved": True, "targetRevision": store.manifest(target_id)["currentRevision"]})
    elif command == "audit":
        issues = audit(store)
        emit({"ok": not issues, "entityCount": len(store.registry()["entities"]), "issues": issues, "storeRoot": str(store.root)})
        raise SystemExit(0 if not issues else 2)
    elif command == "unlock":
        if not args.confirm_unlock:
            raise ValueError("Unlock requires --confirm-unlock")
        path = store.locks_root / f"{normalize_id(args.id or '')}.lock"
        if path.exists():
            shutil.rmtree(path)
        emit({"unlocked": str(path)})


def audit(store: Store) -> list[str]:
    issues: list[str] = []
    seen: dict[str, str] = {}
    registry = store.registry()
    for entity in registry["entities"]:
        for value in identity_values(entity):
            key = value.casefold()
            if key in seen and seen[key] != entity["id"]:
                issues.append(f"Duplicate identity '{value}': {seen[key]}, {entity['id']}")
            else:
                seen[key] = entity["id"]
        try:
            manifest = store.manifest(entity["id"])
            history = store.history_files(entity["id"])
            if len(history) > HISTORY_LIMIT:
                issues.append(f"History limit exceeded for {entity['id']}: {len(history)}")
            current = store.current_path(entity["id"])
            if int(manifest["currentRevision"]) > 0 and not current.is_file() and manifest["status"] != "migrated":
                issues.append(f"Current file missing for {entity['id']}")
            if current.is_file():
                current_hash = sha256(current)
                if manifest.get("currentSha256") and current_hash.casefold() != str(manifest["currentSha256"]).casefold():
                    issues.append(f"Current hash mismatch for {entity['id']}")
                matches = [path for path in history if path.name.startswith(f"rev-{int(manifest['currentRevision']):04d}-")]
                if len(matches) != 1:
                    issues.append(f"Current revision history missing or duplicated for {entity['id']}: {manifest['currentRevision']}")
                elif sha256(matches[0]) != current_hash:
                    issues.append(f"Current/history content mismatch for {entity['id']}: {manifest['currentRevision']}")
        except Exception as exc:
            issues.append(str(exc))
    for path in store.locks_root.glob("*.lock"):
        issues.append(f"Active or stale lock: {path}")
    return issues


if __name__ == "__main__":
    main()
