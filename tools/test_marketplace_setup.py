#!/usr/bin/env python3
"""Regression tests for marketplace setup safety and CLI-output parsing."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
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

    def test_cache_verification_requires_expected_directory_manifest_and_file_hashes(self) -> None:
        with temporary_directory("marketplace-cache-verification-") as temporary:
            base = Path(temporary)
            root = base / "source"
            codex_home = base / "codex-home"
            plugin = root / "plugins" / "example"
            (plugin / ".codex-plugin").mkdir(parents=True)
            (plugin / "skills" / "example").mkdir(parents=True)
            version = "1.2.3+codex.test"
            (root / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": "example", "version": version}]}) + "\n",
                encoding="utf-8",
            )
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"name": "example", "version": version}) + "\n",
                encoding="utf-8",
            )
            skill = plugin / "skills" / "example" / "SKILL.md"
            skill.write_text("new stable content\n", encoding="utf-8")
            stale = codex_home / "plugins" / "cache" / "workspace-local" / "example" / "1.2.2+codex.old"
            stale.mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "cache directory missing"):
                MANAGER.verify_plugin_cache(root, codex_home)

            installed = codex_home / "plugins" / "cache" / "workspace-local" / "example" / version
            (installed / ".codex-plugin").mkdir(parents=True)
            (installed / "skills" / "example").mkdir(parents=True)
            (installed / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"name": "example", "version": version}) + "\n",
                encoding="utf-8",
            )
            (installed / "skills" / "example" / "SKILL.md").write_text("stale content\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                MANAGER.verify_plugin_cache(root, codex_home)
            (installed / "skills" / "example" / "SKILL.md").write_text("new stable content\n", encoding="utf-8")
            verified = MANAGER.verify_plugin_cache(root, codex_home)
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["verifiedPluginCount"], 1)

    def test_new_task_binding_is_separate_from_cache_installation(self) -> None:
        with temporary_directory("marketplace-binding-") as temporary:
            base = Path(temporary)
            root = base / "source"
            codex_home = base / "codex-home"
            root.mkdir()
            version = "2.0.0+codex.test"
            (root / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": "example", "version": version}]}) + "\n",
                encoding="utf-8",
            )
            pending = MANAGER.verify_loaded_skill_binding(root, codex_home, None)
            self.assertEqual(pending["status"], "restart-required")
            expected = MANAGER.expected_skill_path(root, codex_home, "example")
            expected.parent.mkdir(parents=True)
            expected.write_text("test\n", encoding="utf-8")
            stale = codex_home / "plugins" / "cache" / "workspace-local" / "example" / "1.9.0" / "skills" / "example" / "SKILL.md"
            stale.parent.mkdir(parents=True)
            stale.write_text("old\n", encoding="utf-8")
            self.assertEqual(
                MANAGER.verify_loaded_skill_binding(root, codex_home, stale)["status"],
                "loaded-path-mismatch",
            )
            active = MANAGER.verify_loaded_skill_binding(root, codex_home, expected)
            self.assertEqual(active["status"], "loaded-path-verified")
            self.assertFalse(active["newTaskRequired"])

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

    def test_publish_rejects_mixed_staged_and_unstaged_paths(self) -> None:
        git = MANAGER.require_git()
        with temporary_directory("marketplace-mixed-staging-") as temporary:
            root = Path(temporary)
            target = root / "tracked.txt"
            target.write_text("one\n", encoding="utf-8")
            subprocess.run([git, "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=root, check=True)
            subprocess.run([git, "add", "tracked.txt"], cwd=root, check=True)
            subprocess.run([git, "commit", "-m", "initial"], cwd=root, check=True, capture_output=True)
            target.write_text("two\n", encoding="utf-8")
            subprocess.run([git, "add", "tracked.txt"], cwd=root, check=True)
            target.write_text("three\n", encoding="utf-8")
            self.assertEqual(MANAGER.mixed_staging_paths(git, root), ["tracked.txt"])

    def test_publish_rejects_candidate_version_older_than_remote_stable(self) -> None:
        git = MANAGER.require_git()
        with temporary_directory("marketplace-version-gate-") as temporary:
            root = Path(temporary)
            remote = root / "remote.git"
            plugin = root / "plugins" / "example"
            (plugin / ".codex-plugin").mkdir(parents=True)
            (plugin / "skills" / "example" / "agents").mkdir(parents=True)
            manifest = plugin / ".codex-plugin" / "plugin.json"
            pack = root / "skill-pack.json"
            yaml = plugin / "skills" / "example" / "agents" / "openai.yaml"
            manifest.write_text(json.dumps({"name": "example", "version": "0.7.0+codex.stable", "interface": {"displayName": "01 · Example v0.7.0"}}) + "\n", encoding="utf-8")
            pack.write_text(json.dumps({"plugins": [{"id": "example", "version": "0.7.0+codex.stable"}]}) + "\n", encoding="utf-8")
            yaml.write_text('interface:\n  display_name: "01 · Example v0.7.0"\n', encoding="utf-8")
            subprocess.run([git, "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run([git, "init", "-b", "main", str(root)], check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=root, check=True)
            subprocess.run([git, "add", "."], cwd=root, check=True)
            subprocess.run([git, "commit", "-m", "stable"], cwd=root, check=True, capture_output=True)
            subprocess.run([git, "remote", "add", "origin", str(remote)], cwd=root, check=True)
            subprocess.run([git, "push", "-u", "origin", "main"], cwd=root, check=True, capture_output=True)
            manifest.write_text(json.dumps({"name": "example", "version": "0.6.3+codex.legacy", "interface": {"displayName": "01 · Example v0.6.3"}}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "older than stable"):
                MANAGER.validate_publish_versions(git, root, "main", ["example"])

    def test_quarantined_source_names_are_not_safe_publish_sources(self) -> None:
        self.assertTrue(MANAGER.unsafe_source_path(Path("local-marketplace-dirty-quarantine")))
        self.assertTrue(MANAGER.unsafe_source_path(Path("marketplace-backup")))
        self.assertTrue(MANAGER.unsafe_source_path(Path("workspace-dirty") / "local-marketplace-candidate"))
        self.assertFalse(MANAGER.unsafe_source_path(Path("local-marketplace-candidate")))

    def test_active_metadata_rejects_legacy_version(self) -> None:
        with temporary_directory("marketplace-legacy-metadata-") as temporary:
            root = Path(temporary)
            plugin = root / "plugins" / "example"
            (plugin / ".codex-plugin").mkdir(parents=True)
            (plugin / "skills" / "example" / "agents").mkdir(parents=True)
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"name": "example", "version": "0.6.3+codex.legacy", "interface": {"displayName": "01 · Example v0.6.3"}}),
                encoding="utf-8",
            )
            (plugin / "skills" / "example" / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "01 · Example v0.6.3"\n', encoding="utf-8"
            )
            (root / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": "example", "version": "0.6.3+codex.legacy"}]}), encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "legacy v0.6.3"):
                MANAGER.validate_active_metadata(root, ["example"])

    def test_active_metadata_rejects_legacy_version_in_openai_yaml(self) -> None:
        with temporary_directory("marketplace-legacy-yaml-") as temporary:
            root = Path(temporary)
            plugin = root / "plugins" / "example"
            (plugin / ".codex-plugin").mkdir(parents=True)
            (plugin / "skills" / "example" / "agents").mkdir(parents=True)
            stable = "0.7.0+codex.current"
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"name": "example", "version": stable, "interface": {"displayName": "01 · Example v0.7.0"}}),
                encoding="utf-8",
            )
            (plugin / "skills" / "example" / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "01 · Example v0.6.3"\n', encoding="utf-8"
            )
            (root / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": "example", "version": stable}]}), encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "legacy v0.6.3"):
                MANAGER.validate_active_metadata(root, ["example"])

    def test_installer_rolls_back_existing_registration_when_plugin_validation_fails(self) -> None:
        with temporary_directory("marketplace-install-transaction-") as temporary:
            base = Path(temporary)
            root = base / "candidate"
            old = base / "old-main"
            codex_home = base / "codex-home"
            git = MANAGER.require_git()
            root.mkdir()
            old.mkdir()
            (root / "skill-pack.json").write_text(
                json.dumps({"name": "workspace-local", "plugins": [{"id": "example", "version": "1.0.0+codex.test"}]}),
                encoding="utf-8",
            )
            subprocess.run([git, "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=root, check=True)
            subprocess.run([git, "add", "skill-pack.json"], cwd=root, check=True)
            subprocess.run([git, "commit", "-m", "candidate"], cwd=root, check=True, capture_output=True)
            (old / "skill-pack.json").write_text(json.dumps({"name": "workspace-local", "plugins": []}), encoding="utf-8")
            subprocess.run([git, "init", "-b", "main"], cwd=old, check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=old, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=old, check=True)
            subprocess.run([git, "add", "skill-pack.json"], cwd=old, check=True)
            subprocess.run([git, "commit", "-m", "stable"], cwd=old, check=True, capture_output=True)

            state = {"root": str(old)}
            calls: list[list[str]] = []

            def fake_run(command, *, allow_failure=False, capture=False, dry_run=False, show_output=True):
                calls.append(command)
                tail = command[1:]
                if tail == ["plugin", "marketplace", "list"]:
                    output = f"workspace-local {state['root']}\n" if state["root"] else ""
                    return subprocess.CompletedProcess(command, 0, output, "")
                if tail[:3] == ["plugin", "marketplace", "add"]:
                    state["root"] = command[-1]
                    return subprocess.CompletedProcess(command, 0, "", "")
                if tail == ["plugin", "marketplace", "remove", "workspace-local"]:
                    state["root"] = ""
                    return subprocess.CompletedProcess(command, 0, "", "")
                if tail[:2] == ["plugin", "add"]:
                    return subprocess.CompletedProcess(command, 0, "", "")
                if tail[:2] == ["plugin", "list"]:
                    return subprocess.CompletedProcess(command, 0, "", "")
                raise AssertionError(f"Unexpected command: {command}")

            with mock.patch.object(INSTALLER, "run", side_effect=fake_run), mock.patch.object(
                INSTALLER, "rollback_safe_source", return_value=True
            ):
                with self.assertRaisesRegex(RuntimeError, "expected enabled plugin versions"):
                    INSTALLER.install(
                        root,
                        sys.executable,
                        True,
                        False,
                        workspace_root=base / "workspace",
                        codex_home=codex_home,
                    )

            self.assertEqual(Path(state["root"]).resolve(), old.resolve())
            self.assertTrue(any(call[1:] == ["plugin", "marketplace", "remove", "workspace-local"] for call in calls))
            self.assertTrue(any(call[1:] == ["plugin", "marketplace", "add", str(old.resolve())] for call in calls))
            self.assertFalse((codex_home / "workspace-local.json").exists())

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
            self.assertIn("request one task-scoped authorization for the complete one-step closeout", text)
            self.assertIn("do not ask separate PR, merge, installation, restart, or cache questions", text)
            self.assertIn("publication only, PR only, no merge, or no install", text)
            self.assertIn("new-task Skill-path pickup", text)
            self.assertIn("persistent clean stable clone", text)

    def test_read_only_publish_plan_declares_one_review_default(self) -> None:
        policy = MANAGER.release_authorization_policy(False)
        self.assertTrue(policy["singleReviewDefault"])
        self.assertTrue(policy["oneStepRelease"])
        self.assertEqual(policy["oneStepCommand"], "publish --one-step")
        self.assertTrue(policy["noAdditionalApprovalAfterAuthorization"])
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
            "cache-hash-verification",
            "restart-and-new-task-pickup",
            ],
        )
        self.assertTrue(MANAGER.release_authorization_policy(True)["mergeAuthorized"])

    def test_one_step_authorization_expands_to_complete_publish_controls(self) -> None:
        args = type("Args", (), {
            "one_step": True,
            "mode": "publish",
            "confirm_publish": False,
            "confirm_merge": False,
            "create_pr": False,
        })()
        MANAGER.apply_one_step_authorization(args)
        self.assertTrue(args.confirm_publish)
        self.assertTrue(args.confirm_merge)
        self.assertTrue(args.create_pr)
        args.mode = "audit"
        with self.assertRaisesRegex(ValueError, "only valid with publish"):
            MANAGER.apply_one_step_authorization(args)

    def test_commit_identity_reuses_existing_repository_author_without_global_config(self) -> None:
        with temporary_directory("marketplace-commit-identity-") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.com", "commit", "--allow-empty", "-m", "seed"], cwd=root, check=True, capture_output=True)
            self.assertEqual(MANAGER.git_commit_identity("git", root), ("fixture", "fixture@example.com"))

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

    def test_registered_detached_root_is_not_treated_as_updateable_stable_source(self) -> None:
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
            self.assertEqual(result["status"], "detached-source-retained")
            self.assertEqual(
                subprocess.run([git, "rev-parse", "HEAD"], cwd=registered, check=True, text=True, capture_output=True).stdout.strip(),
                result["before"],
            )

    def test_dirty_registered_source_is_not_reused_as_final_stable_registration(self) -> None:
        git = MANAGER.require_git()
        with temporary_directory("marketplace-persistent-stable-") as temporary:
            base = Path(temporary)
            source = base / "source"
            remote = base / "remote.git"
            registered = base / "registered-dirty"
            workspace = base / "workspace"
            subprocess.run([git, "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run([git, "init", "-b", "main", str(source)], check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=source, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=source, check=True)
            (source / "tools").mkdir(parents=True)
            (source / "plugins" / "example").mkdir(parents=True)
            (source / "skill-pack.json").write_text('{"plugins":[]}\n', encoding="utf-8")
            (source / "tools" / "install_personal_skill_marketplace.py").write_text("# installer\n", encoding="utf-8")
            (source / "release.txt").write_text("stable-one\n", encoding="utf-8")
            subprocess.run([git, "add", "."], cwd=source, check=True)
            subprocess.run([git, "commit", "-m", "stable one"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "remote", "add", "origin", str(remote)], cwd=source, check=True)
            subprocess.run([git, "push", "-u", "origin", "main"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote, check=True)
            subprocess.run([git, "clone", str(remote), str(registered)], check=True, capture_output=True)
            (registered / "local-work.txt").write_text("do not overwrite\n", encoding="utf-8")
            (source / "release.txt").write_text("stable-two\n", encoding="utf-8")
            subprocess.run([git, "add", "release.txt"], cwd=source, check=True)
            subprocess.run([git, "commit", "-m", "stable two"], cwd=source, check=True, capture_output=True)
            subprocess.run([git, "push", "origin", "main"], cwd=source, check=True, capture_output=True)

            retained = MANAGER.synchronize_registered_stable_root(git, source, registered, str(remote), "main")
            self.assertEqual(retained["status"], "dirty-source-retained")
            self.assertIn(retained["status"], MANAGER.UNSAFE_REGISTRATION_STATUSES)
            persistent = MANAGER.prepare_persistent_stable_root(git, source, workspace, str(remote), "main")
            persistent_root = Path(persistent["path"])
            self.assertNotEqual(persistent_root.resolve(), registered.resolve())
            self.assertEqual((persistent_root / "release.txt").read_text(encoding="utf-8"), "stable-two\n")
            self.assertEqual((registered / "local-work.txt").read_text(encoding="utf-8"), "do not overwrite\n")
            facts = MANAGER.git_facts(persistent_root, str(remote))
            self.assertEqual(facts["branch"], "main")
            self.assertFalse(facts["dirty"])

    def test_rmtree_safe_removes_readonly_files(self) -> None:
        import stat
        with temporary_directory("marketplace-rmtree-ro-") as temporary:
            target = Path(temporary) / "ro-dir"
            (target / "nested").mkdir(parents=True)
            ro_file = target / "nested" / "locked.txt"
            ro_file.write_text("read only\n", encoding="utf-8")
            os.chmod(ro_file, stat.S_IREAD)
            MANAGER.rmtree_safe(target)
            self.assertFalse(target.exists())

    def test_synchronize_codex_plugins_skips_when_codex_absent(self) -> None:
        with temporary_directory("marketplace-codex-skip-") as temporary:
            base = Path(temporary)
            root = base / "mp"
            codex_home = base / "codex-home"
            root.mkdir()
            codex_home.mkdir()
            res_no_cli = MANAGER.synchronize_codex_plugins(root, codex_home, codex_cli=None)
            self.assertEqual(res_no_cli["status"], "skipped")
            self.assertEqual(res_no_cli["reason"], "codex-cli-unavailable")
            self.assertFalse(res_no_cli["codexRestartRequired"])
            res_no_cfg = MANAGER.synchronize_codex_plugins(root, codex_home, codex_cli="codex.exe")
            self.assertEqual(res_no_cfg["status"], "skipped")
            self.assertEqual(res_no_cfg["reason"], "config-toml-missing")

    def test_synchronize_codex_plugins_incremental_refresh_and_retire(self) -> None:
        import shutil
        with temporary_directory("marketplace-codex-sync-") as temporary:
            base = Path(temporary)
            root = base / "mp"
            codex_home = base / "codex-home"
            cache_root = codex_home / "plugins" / "cache" / "workspace-local"
            root.mkdir(parents=True)
            codex_home.mkdir(parents=True)

            plugins_spec = [
                ("alpha", "1.0.0+codex.1", "alpha-new\n"),
                ("beta", "1.0.0+codex.1", "beta-same\n"),
                ("gamma", "2.0.0+codex.2", "gamma-new\n"),
            ]
            (root / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": pid, "version": ver} for pid, ver, _ in plugins_spec]}) + "\n",
                encoding="utf-8",
            )
            for pid, ver, content in plugins_spec:
                pdir = root / "plugins" / pid
                (pdir / ".codex-plugin").mkdir(parents=True)
                (pdir / "skills" / pid).mkdir(parents=True)
                (pdir / ".codex-plugin" / "plugin.json").write_text(
                    json.dumps({"name": pid, "version": ver}) + "\n",
                    encoding="utf-8",
                )
                (pdir / "skills" / pid / "SKILL.md").write_text(content, encoding="utf-8")

            # Seed cache: alpha (same ver, stale content), beta (match), retired (leftover); gamma missing
            for pid, ver, content in [("alpha", "1.0.0+codex.1", "alpha-stale\n"), ("beta", "1.0.0+codex.1", "beta-same\n"), ("retired", "0.1.0+codex.0", "old\n")]:
                cdir = cache_root / pid / ver
                (cdir / ".codex-plugin").mkdir(parents=True)
                (cdir / "skills" / pid).mkdir(parents=True)
                (cdir / ".codex-plugin" / "plugin.json").write_text(
                    json.dumps({"name": pid, "version": ver}) + "\n",
                    encoding="utf-8",
                )
                (cdir / "skills" / pid / "SKILL.md").write_text(content, encoding="utf-8")

            cfg_path = codex_home / "config.toml"
            cfg_path.write_text(
                'model = "gpt-6.1-sol"\n\n'
                '[plugins."browser@openai-bundled"]\nenabled = true\n\n'
                '[plugins."alpha@workspace-local"]\nenabled = true\n\n'
                '[plugins."beta@workspace-local"]\nenabled = true\n\n'
                '[plugins."retired@workspace-local"]\nenabled = true\n',
                encoding="utf-8",
            )

            installed_versions = {
                "alpha": "1.0.0+codex.1",
                "beta": "1.0.0+codex.1",
            }
            calls: list[list[str]] = []

            def fake_subproc(cmd, *, cwd=None, text=True, capture_output=False, encoding=None, errors=None, env=None):
                calls.append(cmd)
                tail = cmd[1:]
                if tail == ["plugin", "marketplace", "list"]:
                    return subprocess.CompletedProcess(cmd, 0, f"workspace-local  {root}\n", "")
                if tail == ["plugin", "list", "-m", "workspace-local"]:
                    lines = [f"{pid}@workspace-local  installed, enabled  {ver}" for pid, ver in installed_versions.items()]
                    return subprocess.CompletedProcess(cmd, 0, "\n".join(lines) + "\n", "")
                if tail[:2] == ["plugin", "remove"]:
                    pid = tail[2].split("@", 1)[0]
                    installed_versions.pop(pid, None)
                    cdir = cache_root / pid
                    if cdir.exists():
                        shutil.rmtree(cdir)
                    cur = cfg_path.read_text(encoding="utf-8")
                    cfg_path.write_text(MANAGER._remove_config_plugin_block(cur, f"{pid}@workspace-local"), encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                if tail[:2] == ["plugin", "add"]:
                    pid = tail[2].split("@", 1)[0]
                    ver = dict((p, v) for p, v, _ in plugins_spec)[pid]
                    installed_versions[pid] = ver
                    shutil.copytree(root / "plugins" / pid, cache_root / pid / ver)
                    cur = cfg_path.read_text(encoding="utf-8")
                    if f'[plugins."{pid}@workspace-local"]' not in cur:
                        cur = cur.rstrip() + f'\n\n[plugins."{pid}@workspace-local"]\nenabled = true\n'
                        cfg_path.write_text(cur, encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                raise AssertionError(f"Unexpected command: {cmd}")

            with mock.patch.object(MANAGER.subprocess, "run", side_effect=fake_subproc):
                res = MANAGER.synchronize_codex_plugins(root, codex_home, codex_cli="fake-codex")
                self.assertEqual(res["status"], "synchronized")
                self.assertEqual(res["removed"], ["retired"])
                self.assertEqual(res["refreshed"], ["alpha"])
                self.assertEqual(res["installed"], ["gamma"])
                self.assertTrue(res["codexRestartRequired"])
                self.assertFalse(any("beta@workspace-local" in " ".join(c) for c in calls if "remove" in c or "add" in c))

                # Second run must be an idempotent no-op
                res2 = MANAGER.synchronize_codex_plugins(root, codex_home, codex_cli="fake-codex")
                self.assertEqual(res2["status"], "up-to-date")
                self.assertFalse(res2["codexRestartRequired"])

            cfg_after = MANAGER._load_toml(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(cfg_after["plugins"]["browser@openai-bundled"], {"enabled": True})
            self.assertNotIn("retired@workspace-local", cfg_after["plugins"])
            self.assertTrue((cache_root / "alpha" / "1.0.0+codex.1" / "skills" / "alpha" / "SKILL.md").read_text(encoding="utf-8") == "alpha-new\n")
            self.assertFalse((cache_root / "retired").exists())

    def test_synchronize_codex_plugins_rejects_unsafe_retired_plugin_id(self) -> None:
        with temporary_directory("marketplace-codex-unsafe-") as temporary:
            base = Path(temporary)
            root = base / "mp"
            codex_home = base / "codex-home"
            sentinel = codex_home / "plugins" / "cache" / "escape"
            (sentinel / "keep.txt").parent.mkdir(parents=True)
            (sentinel / "keep.txt").write_text("must survive\n", encoding="utf-8")
            (codex_home / "plugins" / "cache" / "workspace-local").mkdir(parents=True)
            root.mkdir(parents=True)
            (root / "skill-pack.json").write_text('{"plugins": []}\n', encoding="utf-8")
            cfg_path = codex_home / "config.toml"
            cfg_path.write_text('[plugins."../escape@workspace-local"]\nenabled = true\n', encoding="utf-8")

            def fake_subproc(cmd, *, cwd=None, text=True, capture_output=False, encoding=None, errors=None, env=None):
                if cmd[1:] == ["plugin", "marketplace", "list"]:
                    return subprocess.CompletedProcess(cmd, 0, f"workspace-local  {root}\n", "")
                raise AssertionError(f"CLI should not be mutated on unsafe ID: {cmd}")

            with mock.patch.object(MANAGER.subprocess, "run", side_effect=fake_subproc):
                with self.assertRaisesRegex(RuntimeError, "Unsafe or invalid plugin ID"):
                    MANAGER.synchronize_codex_plugins(root, codex_home, codex_cli="fake-codex")
            self.assertTrue((sentinel / "keep.txt").is_file())

    def test_synchronize_codex_plugins_dry_run_avoids_plugin_list_side_effects(self) -> None:
        with temporary_directory("marketplace-codex-dry-") as temporary:
            base = Path(temporary)
            root = base / "mp"
            codex_home = base / "codex-home"
            (root / "plugins" / "alpha" / ".codex-plugin").mkdir(parents=True)
            (root / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": "alpha", "version": "1.0.0+codex.1"}]}) + "\n",
                encoding="utf-8",
            )
            (root / "plugins" / "alpha" / ".codex-plugin" / "plugin.json").write_text(
                '{"name": "alpha", "version": "1.0.0+codex.1"}\n',
                encoding="utf-8",
            )
            codex_home.mkdir(parents=True)
            (codex_home / "config.toml").write_text('model = "gpt-6.1-sol"\n', encoding="utf-8")
            calls: list[list[str]] = []

            def fake_subproc(cmd, *, cwd=None, text=True, capture_output=False, encoding=None, errors=None, env=None):
                calls.append(cmd)
                if cmd[1:] == ["plugin", "marketplace", "list"]:
                    return subprocess.CompletedProcess(cmd, 0, f"workspace-local  {root}\n", "")
                raise AssertionError(f"dry_run must not invoke {cmd}")

            with mock.patch.object(MANAGER.subprocess, "run", side_effect=fake_subproc):
                res = MANAGER.synchronize_codex_plugins(root, codex_home, codex_cli="fake-codex", dry_run=True)
            self.assertEqual(res["status"], "dry-run")
            self.assertEqual(res["installed"], ["alpha"])
            self.assertEqual(len(calls), 1)

    def test_synchronize_codex_plugins_rolls_back_cache_and_config_on_add_failure(self) -> None:
        import shutil
        import stat
        with temporary_directory("marketplace-codex-rollback-") as temporary:
            base = Path(temporary)
            root = base / "mp"
            codex_home = base / "codex-home"
            cache_root = codex_home / "plugins" / "cache" / "workspace-local"
            pdir = root / "plugins" / "alpha"
            (pdir / ".codex-plugin").mkdir(parents=True)
            (pdir / "skills" / "alpha").mkdir(parents=True)
            (root / "skill-pack.json").write_text('{"plugins": [{"id": "alpha", "version": "1.0.0+codex.1"}]}\n', encoding="utf-8")
            (pdir / ".codex-plugin" / "plugin.json").write_text('{"name": "alpha", "version": "1.0.0+codex.1"}\n', encoding="utf-8")
            (pdir / "skills" / "alpha" / "SKILL.md").write_text("alpha-new\n", encoding="utf-8")

            cdir = cache_root / "alpha" / "1.0.0+codex.1"
            (cdir / ".codex-plugin").mkdir(parents=True)
            (cdir / "skills" / "alpha").mkdir(parents=True)
            (cdir / ".codex-plugin" / "plugin.json").write_text('{"name": "alpha", "version": "1.0.0+codex.1"}\n', encoding="utf-8")
            (cdir / "skills" / "alpha" / "SKILL.md").write_text("alpha-old\n", encoding="utf-8")

            cfg_path = codex_home / "config.toml"
            original_cfg = (
                'model = "gpt-6.1-sol"\r\n\r\n'
                '[plugins."alpha@workspace-local"] # comment\r\nenabled = true\r\n\r\n'
                '[plugins."alpha@other-marketplace"]\r\nenabled = true\r\n'
            )
            cfg_path.write_bytes(original_cfg.encode("utf-8"))
            if os.name != "nt":
                os.chmod(cfg_path, 0o600)

            dups = MANAGER.duplicate_findings(root, codex_home, None)
            self.assertEqual(dups, ["Enabled plugin duplicate: alpha@other-marketplace"])

            def fake_subproc(cmd, *, cwd=None, text=True, capture_output=False, encoding=None, errors=None, env=None):
                tail = cmd[1:]
                if tail == ["plugin", "marketplace", "list"]:
                    return subprocess.CompletedProcess(cmd, 0, f"workspace-local  {root}\n", "")
                if tail == ["plugin", "list", "-m", "workspace-local"]:
                    return subprocess.CompletedProcess(cmd, 0, "alpha@workspace-local installed, enabled 1.0.0+codex.1\n", "")
                if tail == ["plugin", "remove", "alpha@workspace-local"]:
                    shutil.rmtree(cache_root / "alpha")
                    cur = MANAGER._read_text_preserve_eol(cfg_path)
                    stripped_cfg = MANAGER._remove_config_plugin_block(cur, "alpha@workspace-local")
                    cfg_path.write_bytes(stripped_cfg.encode("utf-8"))
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                if tail == ["plugin", "add", "alpha@workspace-local"]:
                    return subprocess.CompletedProcess(cmd, 1, "", "simulated add failure")
                raise AssertionError(f"Unexpected command: {cmd}")

            with mock.patch.object(MANAGER.subprocess, "run", side_effect=fake_subproc):
                with self.assertRaises(RuntimeError):
                    MANAGER.synchronize_codex_plugins(root, codex_home, codex_cli="fake-codex")

            self.assertEqual(cfg_path.read_bytes(), original_cfg.encode("utf-8"))
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(cfg_path.stat().st_mode), 0o600)
            self.assertEqual((cdir / "skills" / "alpha" / "SKILL.md").read_text(encoding="utf-8"), "alpha-old\n")

    def test_antigravity_sync_backs_up_downstream_drift_without_polluting_skill_dir(self) -> None:
        with temporary_directory("marketplace-ag-drift-") as temporary:
            base = Path(temporary)
            mp = base / "mp"
            ag_home = base / "ag-home"
            state_file = base / "codex-home" / "skill-sync-state.json"
            plugin_id = "single-cell-qc-extract"
            cn_name = "A01-质控过滤提取"
            sdir = mp / "plugins" / plugin_id
            (sdir / ".codex-plugin").mkdir(parents=True)
            (sdir / "skills" / plugin_id).mkdir(parents=True)
            (sdir / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"name": plugin_id, "version": "0.1.0+codex.1", "interface": {"displayName": "A01 · 质控过滤提取 v0.1.0", "shortDescription": "short"}}),
                encoding="utf-8",
            )
            (sdir / "skills" / plugin_id / "SKILL.md").write_text(
                "---\nname: single-cell-qc-extract\ndescription: desc\n---\n\n# A01 · 质控过滤提取 v0.1.0\n\nbody\n",
                encoding="utf-8",
            )
            ag_home.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"ANTIGRAVITY_HOME": str(ag_home)}):
                first = MANAGER.synchronize_antigravity_environment(mp, state_file=state_file, desktop_dir=base / "no-desktop")
                self.assertEqual(first["downstreamDriftBackups"], [])
                dest_dir = ag_home / "config" / "skills" / cn_name
                self.assertTrue((dest_dir / "SKILL.md").is_file())
                self.assertFalse((dest_dir / ".sync-manifest.json").exists())
                self.assertTrue(state_file.is_file())

                # Simulate an unmerged downstream edit in Antigravity
                (dest_dir / "SKILL.md").write_text("manual downstream tweak\n", encoding="utf-8")
                second = MANAGER.synchronize_antigravity_environment(mp, state_file=state_file, desktop_dir=base / "no-desktop")
                self.assertEqual(len(second["downstreamDriftBackups"]), 1)
                backup_path = Path(second["downstreamDriftBackups"][0]["backupPath"])
                self.assertTrue((backup_path / "SKILL.md").is_file())
                self.assertEqual((backup_path / "SKILL.md").read_text(encoding="utf-8"), "manual downstream tweak\n")

                # Corrupt state file + manual edit must still protect downstream edit
                state_file.write_text("{broken json", encoding="utf-8")
                (dest_dir / "SKILL.md").write_text("unmerged tweak under corrupt state\n", encoding="utf-8")
                third = MANAGER.synchronize_antigravity_environment(mp, state_file=state_file, desktop_dir=base / "no-desktop")
                self.assertEqual(len(third["downstreamDriftBackups"]), 1)
                backup_path3 = Path(third["downstreamDriftBackups"][0]["backupPath"])
                self.assertEqual((backup_path3 / "SKILL.md").read_text(encoding="utf-8"), "unmerged tweak under corrupt state\n")

    def test_desktop_sync_repairs_corrupt_zip_and_restored_dir(self) -> None:
        with temporary_directory("marketplace-desktop-zip-") as temporary:
            base = Path(temporary)
            mp = base / "mp"
            desktop_dir = base / "desktop"
            state_file = base / "codex-home" / "skill-sync-state.json"
            plugin_id = "single-cell-qc-extract"
            sdir = mp / "plugins" / plugin_id
            (sdir / ".codex-plugin").mkdir(parents=True)
            (sdir / "skills" / plugin_id).mkdir(parents=True)
            (sdir / ".codex-plugin" / "plugin.json").write_text('{"name": "single-cell-qc-extract", "version": "0.1.0+codex.1"}\n', encoding="utf-8")
            (sdir / "skills" / plugin_id / "SKILL.md").write_text("new content\n", encoding="utf-8")

            standalone_dir = desktop_dir / f"01-{plugin_id}"
            standalone_dir.mkdir(parents=True)
            (standalone_dir / "old.txt").write_text("old", encoding="utf-8")
            with mock.patch.dict(os.environ, {"ANTIGRAVITY_HOME": str(base / "no-ag")}):
                first = MANAGER.synchronize_antigravity_environment(mp, state_file=state_file, desktop_dir=desktop_dir)
                self.assertEqual(first["desktopUpdatedPlugins"], [plugin_id])
                zpath = desktop_dir / f"01-{plugin_id}.zip"
                self.assertTrue(MANAGER._is_valid_zip(zpath))

                # Corrupt zip without changing upstream source: next run must detect and repair
                zpath.write_bytes(b"not a valid zip")
                repaired_zip = MANAGER.synchronize_antigravity_environment(mp, state_file=state_file, desktop_dir=desktop_dir)
                self.assertEqual(repaired_zip["desktopUpdatedPlugins"], [plugin_id])
                self.assertTrue(MANAGER._is_valid_zip(zpath))

                # Restore stale file into standalone_dir: next run must detect and repair
                (standalone_dir / "skills" / plugin_id / "SKILL.md").write_text("restored old\n", encoding="utf-8")
                repaired_dir = MANAGER.synchronize_antigravity_environment(mp, state_file=state_file, desktop_dir=desktop_dir)
                self.assertEqual(repaired_dir["desktopUpdatedPlugins"], [plugin_id])
                self.assertEqual((standalone_dir / "skills" / plugin_id / "SKILL.md").read_text(encoding="utf-8"), "new content\n")

    def test_validator_skips_leftover_codex_cache_without_config_and_publish_gates(self) -> None:
        validator = load_module(
            "validate_skill_robustness",
            ROOT / "plugins" / "skill-writing" / "skills" / "skill-writing" / "scripts" / "validate_skill_robustness.py",
        )
        publisher = load_module(
            "publish_skill",
            ROOT / "plugins" / "skill-sync-publish" / "skills" / "skill-sync-publish" / "scripts" / "publish_skill.py",
        )
        with temporary_directory("marketplace-g4-pub-") as temporary:
            base = Path(temporary)
            ag_home = base / "ag-home"
            ag_skills = ag_home / "config" / "skills"
            ag_skills.mkdir(parents=True)
            (ag_home / "config" / "skills.json").write_text('{"entries": []}\n', encoding="utf-8")
            for _, (_, cn) in validator.STANDARD_20_MAP.items():
                (ag_skills / cn).mkdir()
            (ag_skills / "shared_global_pitfalls.json").write_bytes((ROOT / "shared" / "global_pitfalls.json").read_bytes())

            # Case 1: leftover empty/stale cache WITHOUT config.toml must be skipped gracefully
            codex_home = base / "codex-home"
            (codex_home / "plugins" / "cache" / "workspace-local" / "orphan-old").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"ANTIGRAVITY_HOME": str(ag_home), "CODEX_HOME": str(codex_home)}):
                errs_skip, _ = validator.check_guardrail_4_registry_alignment(ROOT, ag_home)
                self.assertFalse(any("Codex缓存失步" in e for e in errs_skip), errs_skip)

                # Case 2: active config.toml + matching marker MUST report cache drift
                (codex_home / "config.toml").write_text('[plugins."skill-writing@workspace-local"]\nenabled = true\n', encoding="utf-8")
                (codex_home / "workspace-local.json").write_text(json.dumps({"marketplaceRoot": str(ROOT)}), encoding="utf-8")
                errs_active, _ = validator.check_guardrail_4_registry_alignment(ROOT, ag_home)
                self.assertTrue(any("Codex缓存失步" in e for e in errs_active), errs_active)

            # Publish JSON & git gate checks
            self.assertEqual(publisher._parse_json_stdout('{"ok": 1}'), {"ok": 1})
            with self.assertRaises(ValueError):
                publisher._parse_json_stdout('[1, 2]')

            git = MANAGER.require_git()
            remote = base / "remote.git"
            repo = base / "repo"
            subprocess.run([git, "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run([git, "init", "-b", "main", str(repo)], check=True, capture_output=True)
            subprocess.run([git, "config", "user.email", "tests@example.invalid"], cwd=repo, check=True)
            subprocess.run([git, "config", "user.name", "Marketplace Tests"], cwd=repo, check=True)
            for pid, ver in [("alpha", "0.5.0+codex.1"), ("beta", "0.2.0+codex.1")]:
                (repo / "plugins" / pid / ".codex-plugin").mkdir(parents=True)
                (repo / "plugins" / pid / ".codex-plugin" / "plugin.json").write_text(
                    json.dumps({"name": pid, "version": ver}) + "\n", encoding="utf-8"
                )
            (repo / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": "alpha", "version": "0.5.0+codex.1"}, {"id": "beta", "version": "0.2.0+codex.1"}]}) + "\n",
                encoding="utf-8",
            )
            subprocess.run([git, "add", "."], cwd=repo, check=True)
            subprocess.run([git, "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
            subprocess.run([git, "remote", "add", "origin", str(remote)], cwd=repo, check=True)
            subprocess.run([git, "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run([git, "fetch", "origin", "main"], cwd=repo, check=True, capture_output=True)

            # Downgrade against origin/main must fail even when plugin.json was lowered directly
            (repo / "plugins" / "alpha" / ".codex-plugin" / "plugin.json").write_text(
                '{"name": "alpha", "version": "0.4.0+codex.0"}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "version downgrade"):
                publisher.check_remote_version_no_downgrade(git, repo, ["alpha"])
            (repo / "plugins" / "alpha" / ".codex-plugin" / "plugin.json").write_text(
                '{"name": "alpha", "version": "0.5.0+codex.1"}\n', encoding="utf-8"
            )

            # Unrelated edit inside shared skill-pack.json must fail single-skill gate
            (repo / "skill-pack.json").write_text(
                json.dumps({"plugins": [{"id": "alpha", "version": "0.5.0+codex.1"}, {"id": "beta", "version": "0.2.1+codex.2"}]}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "unrelated plugins"):
                publisher.check_unrelated_dirty_paths(git, repo, "alpha", False)
            subprocess.run([git, "checkout", "--", "skill-pack.json"], cwd=repo, check=True)

            # Untracked nested file under plugins/beta/ must be caught by -uall
            (repo / "plugins" / "beta" / "extra" / "note.txt").parent.mkdir(parents=True)
            (repo / "plugins" / "beta" / "extra" / "note.txt").write_text("unrelated\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unrelated uncommitted files"):
                publisher.check_unrelated_dirty_paths(git, repo, "alpha", False)


if __name__ == "__main__":
    unittest.main()
