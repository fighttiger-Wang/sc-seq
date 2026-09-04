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
        self.assertEqual(
            MANAGER.publication_plugins(
                ROOT,
                [
                    "shared/sc-annotation-evidence-core/VERSION.json",
                    "plugins/sc-marker-cluster-annotation-auto/skills/sc-marker-cluster-annotation-auto/SKILL.md",
                ],
            ),
            ["sc-marker-cluster-annotation-auto"],
        )

    def test_new_plugin_directory_requires_marketplace_registration(self) -> None:
        paths = [
            "plugins/new-cross-platform-skill/.codex-plugin/plugin.json",
            "plugins/new-cross-platform-skill/skills/new-cross-platform-skill/SKILL.md",
        ]
        self.assertEqual(MANAGER.changed_plugin_ids(paths), ["new-cross-platform-skill"])
        self.assertEqual(MANAGER.unregistered_changed_plugins(ROOT, paths), ["new-cross-platform-skill"])
        self.assertEqual(
            MANAGER.unregistered_changed_plugins(
                ROOT,
                ["plugins/skill-writing/skills/skill-writing/SKILL.md"],
            ),
            [],
        )

    def test_github_compare_url_is_available_without_github_cli(self) -> None:
        self.assertEqual(
            MANAGER.repository_compare_url(
                "https://github.com/fighttiger-Wang/sc-seq.git",
                "main",
                "codex/new-skill",
            ),
            "https://github.com/fighttiger-wang/sc-seq/compare/main...codex/new-skill?expand=1",
        )
        self.assertIsNone(
            MANAGER.repository_compare_url(
                "https://example.invalid/fighttiger-Wang/sc-seq.git",
                "main",
                "codex/new-skill",
            )
        )

    def test_github_repository_slug_and_ci_summary_are_deterministic(self) -> None:
        self.assertEqual(
            MANAGER.github_repository_slug("git@github.com:fighttiger-Wang/sc-seq.git"),
            "fighttiger-wang/sc-seq",
        )
        self.assertIsNone(MANAGER.github_repository_slug("https://example.invalid/owner/repo.git"))
        successful = MANAGER.github_ci_summary(
            {
                "check_runs": [
                    {"name": "windows", "status": "completed", "conclusion": "success"},
                    {"name": "macos", "status": "completed", "conclusion": "success"},
                ]
            },
            {"statuses": []},
        )
        self.assertTrue(successful["successful"])
        failed = MANAGER.github_ci_summary(
            {"check_runs": [{"name": "windows", "status": "completed", "conclusion": "failure"}]},
            {"statuses": []},
        )
        self.assertEqual(failed["failed"], ["windows"])

    def test_semantic_version_plan_bumps_patch_once_and_syncs_display_name(self) -> None:
        git = MANAGER.require_git()
        self.assertEqual(MANAGER.display_name_with_version("13 · 共享 Skill 下载安装 v0.1.0", "0.1.1"), "13 · 共享 Skill 下载安装 v0.1.1")
        with temporary_directory("marketplace-version-yaml-") as temporary:
            root = Path(temporary)
            plugin = root / "plugins" / "example" / ".codex-plugin"
            plugin.mkdir(parents=True)
            manifest = plugin / "plugin.json"
            manifest.write_text('{"name":"example","version":"2.4.6+codex.old"}\n', encoding="utf-8")
            subprocess.run([git, "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=root, check=True)
            subprocess.run([git, "add", "."], cwd=root, check=True)
            subprocess.run([git, "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            self.assertEqual(MANAGER.proposed_plugin_versions(root, ["example"], git)["example"], "2.4.7")
            manifest.write_text('{"name":"example","version":"3.0.0"}\n', encoding="utf-8")
            self.assertEqual(MANAGER.proposed_plugin_versions(root, ["example"], git)["example"], "3.0.0")

            metadata = root / "openai.yaml"
            metadata.write_text('interface:\n  display_name: "13 · 示例 v0.1.0"\n', encoding="utf-8")
            MANAGER.update_yaml_display_version(metadata, "0.1.1")
            self.assertIn('display_name: "13 · 示例 v0.1.1"', metadata.read_text(encoding="utf-8"))

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
            self.assertIn("ask once for a single end-to-end authorization", text)
            self.assertIn("do not ask a second merge or installation question", text)
            self.assertIn("publication only, PR only, no merge, or no install", text)

    def test_read_only_publish_plan_declares_one_review_default(self) -> None:
        policy = MANAGER.release_authorization_policy(False)
        self.assertTrue(policy["singleReviewDefault"])
        self.assertTrue(policy["publicationOnlyRequiresExplicitLimitation"])
        self.assertTrue(policy["mergeRequiresExplicitAuthorization"])
        self.assertFalse(policy["mergeAuthorized"])
        self.assertEqual(
            policy["defaultAuthorizationScope"],
            [
            "version-update",
            "commit",
            "push",
            "pull-request",
            "ci-wait",
            "sha-pinned-merge",
            "stable-main-verification",
            "local-cache-refresh",
            ],
        )
        self.assertTrue(MANAGER.release_authorization_policy(True)["mergeAuthorized"])

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

    def test_registered_detached_stable_root_fast_forwards_without_touching_release_worktree(self) -> None:
        git = MANAGER.require_git()
        with temporary_directory("marketplace-stable-root-") as temporary:
            base = Path(temporary)
            source = base / "source"
            remote = base / "remote.git"
            registered = base / "registered"
            subprocess.run([git, "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run([git, "init", "-b", "main", str(source)], check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=source, check=True)
            (source / "README.md").write_text("one\n", encoding="utf-8")
            subprocess.run([git, "add", "README.md"], cwd=source, check=True)
            subprocess.run([git, "commit", "-m", "one"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "remote", "add", "origin", str(remote)], cwd=source, check=True)
            subprocess.run([git, "push", "-u", "origin", "main"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote, check=True)
            subprocess.run([git, "clone", str(remote), str(registered)], check=True, capture_output=True)
            subprocess.run([git, "switch", "--detach"], cwd=registered, check=True, capture_output=True)
            (source / "README.md").write_text("two\n", encoding="utf-8")
            subprocess.run([git, "add", "README.md"], cwd=source, check=True)
            subprocess.run([git, "commit", "-m", "two"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "push", "origin", "main"], cwd=source, check=True, capture_output=True)
            result = MANAGER.synchronize_registered_stable_root(git, source, registered, str(remote), "main")
            self.assertEqual(result["status"], "updated")
            self.assertEqual(
                subprocess.run([git, "rev-parse", "HEAD"], cwd=registered, check=True, text=True, capture_output=True).stdout.strip(),
                subprocess.run([git, "rev-parse", "HEAD"], cwd=source, check=True, text=True, capture_output=True).stdout.strip(),
            )


if __name__ == "__main__":
    unittest.main()
