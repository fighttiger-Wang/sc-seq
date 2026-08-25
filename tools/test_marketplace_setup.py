#!/usr/bin/env python3
"""Regression tests for marketplace setup safety and CLI-output parsing."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


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
        with tempfile.TemporaryDirectory(prefix="marketplace-setup-") as temporary:
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
        with tempfile.TemporaryDirectory(prefix="marketplace-clone-") as temporary:
            destination = Path(temporary) / "source"
            (destination / "tools").mkdir(parents=True)
            (destination / "skill-pack.json").write_text("{}\n", encoding="utf-8")
            (destination / "tools" / "install_personal_skill_marketplace.py").write_text("# test\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "use --marketplace-root"):
                MANAGER.safe_clone_destination(destination, Path(temporary) / "codex-home")


if __name__ == "__main__":
    unittest.main()
