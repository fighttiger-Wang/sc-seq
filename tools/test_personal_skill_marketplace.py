#!/usr/bin/env python3
"""Cross-platform doctor for the shared personal Codex marketplace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DISPLAY_RE = re.compile(r"^\d{2} · .+$")
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".ps1", ".sh", ".py", ".r", ".txt"}
IGNORED_PARTS = {".git", "logs", "outputs", "tmp", "__pycache__"}
SECRET_RE = re.compile(r"(^\.env($|\.)|\.pem$|\.key$|credentials|secrets?|\.sqlite3(?:-wal|-shm)?$)", re.I)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ignored(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in IGNORED_PARTS or part.startswith("test_debug") for part in parts)


class Doctor:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks: list[dict] = []

    def add(self, name: str, passed: bool, detail: str = "", severity: str = "error") -> None:
        self.checks.append({"name": name, "passed": passed, "severity": severity, "detail": detail})
        if not passed:
            (self.warnings if severity == "warning" else self.errors).append(f"{name}: {detail}")

    def read_json(self, relative: str, label: str):
        path = self.root / relative
        if not path.is_file():
            self.add(label, False, f"Missing file: {path}")
            return None
        try:
            value = load_json(path)
        except Exception as exc:
            self.add(label, False, str(exc))
            return None
        self.add(label, True, str(path))
        return value

    def run(self) -> dict:
        pack = self.read_json("skill-pack.json", "skill-pack manifest")
        market = self.read_json(".agents/plugins/marketplace.json", "canonical marketplace manifest")
        compat = self.read_json(".codex-plugin/marketplace.json", "compatibility marketplace manifest")
        expected_ids: list[str] = []
        if pack:
            expected_ids = [str(item["id"]) for item in pack.get("plugins", [])]
            self.add("expected plugin count", len(expected_ids) == int(pack.get("expectedPluginCount", -1)), f"Expected {pack.get('expectedPluginCount')}, found {len(expected_ids)}")
            self.add("unique skill-pack ids", len(expected_ids) == len(set(expected_ids)), "Duplicate plugin ids exist")
        if market and pack:
            market_ids = [str(item["name"]) for item in market.get("plugins", [])]
            self.add("marketplace name", market.get("name") == pack.get("name"), f"Expected {pack.get('name')}, found {market.get('name')}")
            self.add("canonical plugin count", len(market_ids) == len(expected_ids), f"Expected {len(expected_ids)}, found {len(market_ids)}")
            self.add("canonical plugin set", sorted(market_ids) == sorted(expected_ids), "Canonical marketplace plugin ids differ from skill-pack.json")
            for entry in market.get("plugins", []):
                plugin_id = str(entry.get("name", ""))
                policy = entry.get("policy") or {}
                source = entry.get("source") or {}
                ok = (
                    source.get("source") == "local"
                    and source.get("path") == f"./plugins/{plugin_id}"
                    and policy.get("installation") == "INSTALLED_BY_DEFAULT"
                    and policy.get("authentication") == "ON_INSTALL"
                    and bool(entry.get("category"))
                )
                self.add(f"marketplace entry {plugin_id}", ok, "Source path or policy/category is invalid")
        if compat and market:
            compat_ids = [str(item["name"]) for item in compat.get("plugins", [])]
            self.add("compatibility marketplace name", compat.get("name") == market.get("name"), "Marketplace names differ")
            self.add("compatibility plugin set", sorted(compat_ids) == sorted(expected_ids), "Compatibility marketplace plugin ids differ")

        pack_versions = {str(item["id"]): str(item.get("version", "")) for item in (pack or {}).get("plugins", [])}
        for position, plugin_id in enumerate(expected_ids, start=1):
            plugin_root = self.root / "plugins" / plugin_id
            manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
            skill_root = plugin_root / "skills" / plugin_id
            skill_path = skill_root / "SKILL.md"
            agent_path = skill_root / "agents" / "openai.yaml"
            self.add(f"plugin directory {plugin_id}", plugin_root.is_dir(), str(plugin_root))
            manifest = None
            try:
                manifest = load_json(manifest_path)
                self.add(f"plugin manifest {plugin_id}", True, str(manifest_path))
            except Exception as exc:
                self.add(f"plugin manifest {plugin_id}", False, str(exc))
            if manifest:
                ok = (
                    manifest.get("name") == plugin_id
                    and str(manifest.get("version", "")) == pack_versions.get(plugin_id)
                    and bool(manifest.get("description"))
                    and bool((manifest.get("author") or {}).get("name"))
                    and bool((manifest.get("interface") or {}).get("displayName"))
                    and manifest.get("skills") == "./skills/"
                )
                self.add(f"plugin metadata {plugin_id}", ok, f"Expected version {pack_versions.get(plugin_id)}")
            self.add(f"skill file {plugin_id}", skill_path.is_file(), str(skill_path))
            if skill_path.is_file():
                text = skill_path.read_text(encoding="utf-8")
                front = re.match(r"\A---\s*\n(.*?)\n---", text, re.S)
                body = front.group(1) if front else ""
                ok = bool(re.search(rf"(?m)^name:\s*{re.escape(plugin_id)}\s*$", body) and re.search(r"(?m)^description:\s*\S", body))
                self.add(f"skill frontmatter {plugin_id}", ok, "SKILL.md frontmatter is invalid")
            self.add(f"skill UI metadata {plugin_id}", agent_path.is_file(), str(agent_path))
            if manifest and agent_path.is_file():
                agent_text = agent_path.read_text(encoding="utf-8")
                display_match = re.search(r'(?m)^\s*display_name:\s*["\']?([^"\'\r\n]+)', agent_text)
                implicit_match = re.search(r"(?m)^\s*allow_implicit_invocation:\s*(true|false)\s*$", agent_text, re.I)
                agent_display = display_match.group(1).strip() if display_match else ""
                plugin_display = str((manifest.get("interface") or {}).get("displayName", ""))
                self.add(f"numbered display name {plugin_id}", agent_display == plugin_display and bool(DISPLAY_RE.fullmatch(plugin_display)), f"plugin.json='{plugin_display}'; openai.yaml='{agent_display}'")
                self.add(f"workflow order {plugin_id}", plugin_display.startswith(f"{position:02d} · "), f"Expected prefix {position:02d} ·")
                implicit = implicit_match.group(1).lower() == "true" if implicit_match else True
                self.add(f"implicit invocation {plugin_id}", implicit, "Maintained shared skills must remain in the default skill set")

        for relative in (pack or {}).get("sharedPaths", []):
            path = self.root / str(relative)
            self.add(f"shared path {relative}", path.is_dir(), str(path))
        required_entrypoints = (
            "Install-PersonalSkillMarketplace.ps1",
            "Install-PersonalSkillMarketplace.sh",
            "Setup-PersonalSkillMarketplace.ps1",
            "Setup-PersonalSkillMarketplace.sh",
            "Test-PersonalSkillMarketplace.ps1",
            "Test-PersonalSkillMarketplace.sh",
            "tools/install_personal_skill_marketplace.py",
            "tools/resolve-python.sh",
            "tools/test_marketplace_setup.py",
            "plugins/personal-skill-marketplace-setup/skills/personal-skill-marketplace-setup/scripts/setup.py",
            ".github/workflows/marketplace-ci.yml",
        )
        for relative in required_entrypoints:
            self.add(f"platform entrypoint {relative}", (self.root / relative).is_file(), relative)
        self.check_annotation()
        self.check_forbidden_files()
        for runtime in ("git", "codex", "python3", "python", "Rscript", "pwsh"):
            found = shutil.which(runtime)
            if found and "WindowsApps" in found:
                found = None
            self.add(f"runtime {runtime}", bool(found), f"{runtime} is not currently available in PATH", "warning")
        return {
            "marketplaceRoot": str(self.root),
            "marketplace": (pack or {}).get("name"),
            "expectedPluginCount": int((pack or {}).get("expectedPluginCount", 0)),
            "errors": self.errors,
            "warnings": self.warnings,
            "passed": not self.errors,
            "checks": self.checks,
        }

    def check_annotation(self) -> None:
        evidence = self.root / "shared" / "sc-annotation-evidence-core"
        try:
            version = load_json(evidence / "VERSION.json")
            config = load_json(evidence / "annotation-evidence-config.v1.json")
            knowledge = load_json(evidence / "knowledge-base" / "cell-annotation-knowledge-base.v2.json")
            manifest = load_json(evidence / "knowledge-base" / "knowledge-base.manifest.json")
            core_text = (evidence / "annotation_evidence_core.py").read_text(encoding="utf-8")
            core_match = re.search(r'^CORE_VERSION\s*=\s*["\']([^"\']+)', core_text, re.M)
            ok = bool(core_match) and version.get("core_version") == core_match.group(1) and version.get("config_version") == config.get("config_version") and version.get("knowledge_base_version") == knowledge.get("knowledge_base_version") == manifest.get("knowledge_base_version")
            self.add("annotation canonical versions", ok, json.dumps(version, ensure_ascii=False))
            hash_errors = []
            newline_errors = []
            for filename, expected in (manifest.get("sha256") or {}).items():
                path = evidence / "knowledge-base" / filename
                if not path.is_file() or sha256(path) != expected:
                    hash_errors.append(filename)
                elif b"\r\n" in path.read_bytes():
                    newline_errors.append(filename)
            self.add("annotation knowledge hashes", not hash_errors, ", ".join(hash_errors))
            self.add("annotation knowledge LF newlines", not newline_errors, ", ".join(newline_errors))
            mappings = {
                "annotation_evidence_core.py": ("scripts", "annotation_evidence_core.py"),
                "knowledge_base.py": ("scripts", "knowledge_base.py"),
                "annotation-evidence-config.v1.json": ("references", "annotation-evidence-config.v1.json"),
                "evidence-scoring-policy.md": ("references", "evidence-scoring-policy.md"),
                "knowledge-base/cell-annotation-knowledge-base.v2.json": ("references", "cell-annotation-knowledge-base.v2.json"),
                "knowledge-base/legacy-migration.v2.json": ("references", "legacy-migration.v2.json"),
                "knowledge-base/knowledge-base.manifest.json": ("references", "knowledge-base.manifest.json"),
            }
            for plugin_id in ("sc-major-celltype-annotation-auto", "sc-marker-cluster-annotation-auto"):
                skill = self.root / "plugins" / plugin_id / "skills" / plugin_id
                snapshot = load_json(skill / "references" / "annotation-evidence-core.snapshot.json")
                metadata_ok = all(snapshot.get(key) == version.get(key) for key in ("core_version", "config_version", "knowledge_base_version", "snapshot_contract")) and snapshot.get("canonical_source") == "shared/sc-annotation-evidence-core"
                self.add(f"annotation snapshot metadata {plugin_id}", metadata_ok, json.dumps(snapshot, ensure_ascii=False))
                errors = []
                snapshot_newline_errors = []
                for source_name, (folder, destination_name) in mappings.items():
                    source = evidence / source_name
                    destination = skill / folder / destination_name
                    source_hash = sha256(source) if source.is_file() else ""
                    if not destination.is_file() or sha256(destination) != source_hash or (snapshot.get("files") or {}).get(source_name) != source_hash:
                        errors.append(source_name)
                    elif source.suffix.lower() in {".json", ".md", ".py"} and (b"\r\n" in source.read_bytes() or b"\r\n" in destination.read_bytes()):
                        snapshot_newline_errors.append(source_name)
                self.add(f"annotation snapshot files {plugin_id}", not errors, ", ".join(errors))
                self.add(f"annotation snapshot LF newlines {plugin_id}", not snapshot_newline_errors, ", ".join(snapshot_newline_errors))
        except Exception as exc:
            self.add("annotation evidence validation", False, str(exc))

    def check_forbidden_files(self) -> None:
        forbidden = []
        absolute_hits = []
        for path in self.root.rglob("*"):
            if not path.is_file() or ignored(path, self.root):
                continue
            if SECRET_RE.search(path.name):
                forbidden.append(str(path))
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if path.resolve() == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            normalized = text.replace("\\\\", "/").replace("\\", "/")
            segment = r"[^/\s<>'\"]+"
            if re.search(rf"(?i)\b[A-Z]:/Users/{segment}/", normalized) or re.search(rf"/(Users|home)/{segment}/", normalized):
                absolute_hits.append(str(path))
        self.add("secret-like files", not forbidden, "; ".join(forbidden[:10]))
        self.add("machine-specific absolute paths", not absolute_hits, "; ".join(absolute_hits[:10]), "warning")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace-root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = Doctor(args.marketplace_root.resolve()).run()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Personal skill marketplace: {result['marketplaceRoot']}")
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "WARN" if check["severity"] == "warning" else "FAIL"
            suffix = "" if check["passed"] or not check["detail"] else f": {check['detail']}"
            print(f"[{status}] {check['name']}{suffix}")
        print(f"Result: {len(result['errors'])} error(s), {len(result['warnings'])} warning(s).")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
