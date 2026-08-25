#!/usr/bin/env python3
"""Regression tests for marketplace setup safety and CLI-output parsing."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def temporary_directory(prefix: str):
    configured = os.environ.get("CODEX_TEST_TMPDIR")
    directory = Path(configured).expanduser().resolve() if configured else None
    if directory:
        directory.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=directory)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALLER = load_module("marketplace_installer", ROOT / "tools" / "install_personal_skill_marketplace.py")
MANAGER = load_module(
    "marketplace_setup_manager",
    ROOT
    / "plugins"
    / "personal-skill-marketplace-setup"
    / "skills"
    / "personal-skill-marketplace-setup"
    / "scripts"
    / "setup.py",
)


class MarketplaceSetupTests(unittest.TestCase):
    def test_repository_normalization_accepts_https_and_ssh_forms(self) -> None:
        expected = "github.com/fighttiger-wang/sc-seq"
        self.assertEqual(MANAGER.normalized_repository("https://github.com/fighttiger-Wang/sc-seq.git"), expected)
        self.assertEqual(MANAGER.normalized_repository("git@github.com:fighttiger-Wang/sc-seq.git"), expected)

    def test_cli_output_parsers_require_exact_marketplace_version_and_state(self) -> None:
        marketplace_output = "workspace-local /approved/source/path\nother /different/path\n"
        self.assertEqual(INSTALLER.marketplace_roots(marketplace_output, "workspace-local"), ["/approved/source/path"])
        plugin_output = "example@workspace-local installed, enabled 1.2.3+codex.test\n"
        self.assertTrue(INSTALLER.plugin_is_enabled(plugin_output, "example", "workspace-local", "1.2.3+codex.test"))
        self.assertFalse(INSTALLER.plugin_is_enabled(plugin_output, "example", "workspace-local", "1.2.4+codex.test"))
        self.assertFalse(INSTALLER.plugin_is_enabled("example@workspace-local installed, disabled 1.2.3+codex.test\n", "example", "workspace-local", "1.2.3+codex.test"))

    def test_workspace_and_source_cannot_overlap_codex_home(self) -> None:
        with temporary_directory("marketplace-setup-") as temporary:
            base = Path(temporary).resolve()
            codex_home = base / "codex-home"
            codex_home.mkdir()
            safe_workspace = base / "workspace"
            self.assertEqual(INSTALLER.validate_workspace(safe_workspace, codex_home, False), safe_workspace)
            for unsafe in (codex_home, codex_home / "work", base):
                with self.subTest(unsafe=unsafe):
                    with self.assertRaises(RuntimeError):
                        INSTALLER.validate_workspace(unsafe, codex_home, False)
            with self.assertRaises(RuntimeError):
                INSTALLER.validate_marketplace_root(codex_home / "source", codex_home)
            with self.assertRaises(RuntimeError):
                MANAGER.safe_clone_destination(codex_home / "source", codex_home)

    def test_existing_marketplace_is_not_recloned(self) -> None:
        with temporary_directory("marketplace-clone-") as temporary:
            destination = Path(temporary) / "source"
            (destination / "tools").mkdir(parents=True)
            (destination / "skill-pack.json").write_text("{}\n", encoding="utf-8")
            (destination / "tools" / "install_personal_skill_marketplace.py").write_text("# test\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "use --marketplace-root"):
                MANAGER.safe_clone_destination(destination, Path(temporary) / "codex-home")

    def test_selective_plugin_install_rejects_unknown_ids(self) -> None:
        pack = {"plugins": [{"id": "one"}, {"id": "two"}]}
        all_plugins, selected = INSTALLER.select_plugins(pack, ["two", "two"])
        self.assertEqual([item["id"] for item in all_plugins], ["one", "two"])
        self.assertEqual([item["id"] for item in selected], ["two"])
        with self.assertRaisesRegex(RuntimeError, "Unknown plugin ids"):
            INSTALLER.select_plugins(pack, ["missing"])

    def test_affected_plugins_prefers_direct_plugin_and_expands_shared_changes(self) -> None:
        direct = MANAGER.affected_plugins(ROOT, ["plugins/personal-skill-marketplace-setup/skills/x/SKILL.md"])
        self.assertEqual(direct, ["personal-skill-marketplace-setup"])
        installer = MANAGER.affected_plugins(ROOT, ["tools/install_personal_skill_marketplace.py"])
        self.assertEqual(installer, ["personal-skill-marketplace-setup"])
        shared = MANAGER.affected_plugins(ROOT, ["shared/sc-annotation-evidence-core/VERSION.json"])
        pack = INSTALLER.load_json(ROOT / "skill-pack.json")
        self.assertEqual(shared, [item["id"] for item in pack["plugins"]])

    def test_managed_guidance_preserves_existing_content_and_is_idempotent(self) -> None:
        with temporary_directory("marketplace-guidance-") as temporary:
            workspace = Path(temporary)
            agents = workspace / "AGENTS.md"
            agents.write_text("# Existing\n\nKeep this.\n", encoding="utf-8")
            first = MANAGER.install_managed_guidance(workspace, False)
            second = MANAGER.install_managed_guidance(workspace, False)
            text = agents.read_text(encoding="utf-8")
            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertIn("Keep this.", text)
            self.assertEqual(text.count(MANAGER.GUIDANCE_BEGIN), 1)
            self.assertEqual(text.count(MANAGER.GUIDANCE_END), 1)

    def test_bootstrap_copy_is_moved_to_recoverable_disabled_backup(self) -> None:
        with temporary_directory("marketplace-bootstrap-copy-") as temporary:
            base = Path(temporary)
            codex_home = base / "codex-home"
            bare = codex_home / "skills" / MANAGER.SETUP_SKILL_ID
            bare.mkdir(parents=True)
            (bare / "SKILL.md").write_text("---\nname: test\n---\n", encoding="utf-8")
            marketplace = base / "source"
            marketplace.mkdir()
            result = MANAGER.disable_bootstrap_copy(codex_home, marketplace, False)
            self.assertEqual(result["status"], "disabled")
            self.assertFalse(bare.exists())
            self.assertTrue(Path(result["destination"]).joinpath("SKILL.md").is_file())

    def test_preflight_is_noop_on_current_main_and_allows_current_development_branch(self) -> None:
        git = MANAGER.require_git()
        with temporary_directory("marketplace-preflight-") as temporary:
            base = Path(temporary)
            source = base / "source"
            remote = base / "remote.git"
            client = base / "client"
            subprocess.run([git, "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run([git, "init", "-b", "main", str(source)], check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=source, check=True)
            (source / "README.md").write_text("test\n", encoding="utf-8")
            subprocess.run([git, "add", "README.md"], cwd=source, check=True)
            subprocess.run([git, "commit", "-m", "initial"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "remote", "add", "origin", str(remote)], cwd=source, check=True)
            subprocess.run([git, "push", "-u", "origin", "main"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote, check=True)
            subprocess.run([git, "clone", str(remote), str(client)], check=True, capture_output=True)
            current = MANAGER.preflight_repository(client, str(remote), "main", False)
            self.assertEqual(current["status"], "up-to-date")
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=client, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=client, check=True)
            subprocess.run([git, "switch", "-c", "codex/test"], cwd=client, check=True, capture_output=True)
            (client / "README.md").write_text("test\ndevelopment\n", encoding="utf-8")
            subprocess.run([git, "add", "README.md"], cwd=client, check=True)
            subprocess.run([git, "commit", "-m", "development"], cwd=client, check=True, capture_output=True)
            development = MANAGER.preflight_repository(client, str(remote), "main", False)
            self.assertEqual(development["status"], "development-current")


if __name__ == "__main__":
    unittest.main()
