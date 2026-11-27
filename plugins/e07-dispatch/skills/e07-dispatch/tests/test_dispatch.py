import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import delegate
import parallel_dispatch as dispatch


class PricingTests(unittest.TestCase):
    def test_beijing_time_boundaries(self):
        cases = (
            ("2026-11-27T08:59", True, "weekday"),
            ("2026-11-27T09:00", False, "weekday"),
            ("2026-11-27T12:00", True, "weekday"),
            ("2026-11-27T14:00", False, "weekday"),
            ("2026-11-27T18:00", True, "weekday"),
            ("2026-11-28T10:00", True, "weekend"),
            ("2026-10-07T10:00", True, "holiday"),
            ("2026-10-08T10:00", False, "weekday"),
            ("2026-10-10T10:00", True, "makeup_workday"),
        )
        for timestamp, half_price, day_type in cases:
            with self.subTest(timestamp=timestamp):
                now = datetime.fromisoformat(timestamp + "+08:00")
                self.assertEqual(dispatch.is_deepseek_half_price_window(now), (half_price, timestamp[-5:]))
                self.assertEqual(dispatch.deepseek_pricing(now)["china_calendar_day_type"], day_type)
        utc_time = datetime.fromisoformat("2026-11-27T01:00+00:00")
        self.assertEqual(dispatch.is_deepseek_half_price_window(utc_time), (False, "09:00"))

    def test_uncovered_year_and_expired_review(self):
        for timestamp, note in (("2025-11-27", "未覆盖"), ("2026-12-25", "超期未复核")):
            with self.subTest(timestamp=timestamp):
                pricing = dispatch.deepseek_pricing(datetime.fromisoformat(timestamp + "T10:00+08:00"))
                self.assertIsNone(pricing["deepseek_half_price_window"])
                self.assertEqual(pricing["deepseek_pricing_status"], "unverified")
                self.assertIn(note, pricing["half_price_note"])


class RoutingTests(unittest.TestCase):
    def test_pool_defaults_and_explicit_aliases(self):
        for pool, code in (("1", "1B"), ("2", "2B"), ("3", "3C"), ("4", "4A")):
            self.assertEqual(dispatch.resolve_choice(pool)["code"], code)
        for alias in ("1A", "2A", "3A"):
            self.assertEqual(dispatch.resolve_choice(alias)["code"], alias)

    def test_retirement_warning_matches_model_family_and_radar_window(self):
        slugs = ["gemini-3.8-flash-medium", "gemini-4-argon-high", "gemini-4-argonish"]
        self.assertEqual(dispatch.retirement_warnings(slugs, date(2026, 11, 15)), [])
        for today, status in ((date(2026, 11, 16), "upcoming"), (date(2026, 12, 1), "past")):
            warnings = dispatch.retirement_warnings(slugs, today)
            self.assertEqual([notice["status"] for notice in warnings], [status, status])
        self.assertEqual(dispatch.retirement_warnings([slugs[-1]], date(2026, 12, 1)), [])


class ConfirmationTests(unittest.TestCase):
    def test_parallel_confirmation_blocks_or_forwards(self):
        with patch.object(dispatch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "{}")) as child:
            blocked = dispatch.dispatch_task("8A", "test", os.getcwd(), dry_run=True)
            self.assertEqual(blocked["status"], "ASK_USER_CONFIRMATION_REQUIRED")
            child.assert_not_called()
            allowed = dispatch.dispatch_task("8A", "test", os.getcwd(), dry_run=True, user_confirmed=True)
            self.assertEqual(allowed["status"], "PAYG_EXTERNAL_DRY_RUN")
            self.assertIn("--user-confirmed", child.call_args.args[0])

    def test_delegate_blocks_direct_official_and_unpatched_headless(self):
        for provider_args in (("--model", "deepseek-v4-pro"), ("--dsh-provider", "deepseek-account")):
            with self.subTest(provider_args=provider_args), patch.object(delegate, "detect_binary") as detect:
                output = io.StringIO()
                with redirect_stdout(output):
                    code = delegate.main(["run", "--runner", "dsh", "--prompt", "test", "--json", *provider_args])
                self.assertEqual(code, 1)
                self.assertIn("--user-confirmed", json.loads(output.getvalue())["error"])
                detect.assert_not_called()

    def test_confirmed_dry_run_never_creates_or_unlinks_yaml_or_starts_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "never-created"
            args = ["--home", str(state), "run", "--runner", "dsh", "--model", "deepseek-v4-pro",
                    "--prompt", "test", "--user-confirmed", "--dry-run", "--refresh", "--json"]
            output = io.StringIO()
            with (patch.dict(os.environ, {"OIL_DELEGATE_DSH_BIN": sys.executable}), redirect_stdout(output),
                  patch.object(delegate.tempfile, "NamedTemporaryFile") as make_temp,
                  patch.object(Path, "unlink") as unlink, patch.object(delegate.subprocess, "run") as run):
                self.assertEqual(delegate.main(args), 0)
                make_temp.assert_not_called()
                unlink.assert_not_called()
                run.assert_not_called()
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["command"][payload["command"].index("--patch") + 1], "<dry-run-temp.yml>")
            self.assertIn("provider: deepseek-official", payload["dsh_patch_preview"])
            self.assertFalse(state.exists())

    def test_real_execution_patch_is_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            args = delegate.build_parser().parse_args(["run", "--runner", "dsh", "--model", "deepseek-v4-pro",
                                                       "--prompt", "test", "--user-confirmed"])
            def fail(*invocation):
                patch_path, preview = invocation[-2:]
                self.assertEqual(patch_path.read_text(encoding="utf-8"), preview)
                raise RuntimeError("fake failure")

            with (patch.dict(os.environ, {"OIL_DELEGATE_DSH_BIN": sys.executable}),
                  patch.object(delegate, "execute_invocation", side_effect=fail), self.assertRaises(RuntimeError)):
                delegate.execute_run(args, state, delegate.default_config(), require_enabled=False)
            self.assertEqual(list(state.glob("*.yml")), [])


class TaskStatusTests(unittest.TestCase):
    def test_detached_dispatch_records_success_and_failure(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"E07_TASKS_DIR": temp}):
            fake_delegate = Path(temp) / "fake_delegate.py"
            fake_delegate.write_text(
                "import sys\nassert '--user-confirmed' in sys.argv\n"
                "sys.exit(int(sys.argv[sys.argv.index('--prompt') + 1]))\n", encoding="utf-8"
            )
            processes = []
            real_popen = subprocess.Popen

            def track_process(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                processes.append(process)
                return process

            with (patch.object(dispatch, "LOCAL_DELEGATE", fake_delegate),
                  patch.object(dispatch.subprocess, "Popen", side_effect=track_process)):
                for exit_code, expected in ((0, "COMPLETED"), (7, "FAILED")):
                    with self.subTest(exit_code=exit_code):
                        task = dispatch.dispatch_task("8A", str(exit_code), temp, user_confirmed=True)
                        self.assertEqual(processes[-1].wait(timeout=10), exit_code)
                        status = dispatch.get_task_status(task["task_id"])
                        self.assertEqual((status["task_status"], status.get("exit_code")), (expected, exit_code))
            self.assertEqual(dispatch.list_active_tasks(), [])

    def test_legacy_task_has_no_proof_of_success(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"E07_TASKS_DIR": temp}):
            task_dir = Path(temp) / "task_legacy"
            task_dir.mkdir()
            meta = task_dir / "meta.json"
            for original in ("RUNNING", "COMPLETED"):
                meta.write_text(json.dumps({"task_status": original, "pid": 123}), encoding="utf-8")
                with patch.object(dispatch, "check_pid_alive", return_value=False):
                    self.assertEqual(dispatch.get_task_status(task_dir.name)["task_status"], "EXITED_UNKNOWN")
                    self.assertEqual(dispatch.list_active_tasks(), [])
