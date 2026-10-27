from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tools.security.script import launch

ROOT = Path(__file__).resolve().parents[1]
WORKER = """import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from tools.security.script.launch import SetupLock
with SetupLock(Path(sys.argv[2]), timeout=float(sys.argv[4])):
    Path(sys.argv[3]).write_text('ready')
    while True:
        time.sleep(.05)
"""


class SetupLockTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = ROOT / "tmp" / "setup-lock-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.workspace = tempfile.TemporaryDirectory(prefix="lock 日本語 空白 ", dir=scratch)
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)

    def worker(self, timeout: float = 2) -> tuple[subprocess.Popen, Path]:
        ready = self.root / "worker-ready"
        process = subprocess.Popen(
            [
                sys._base_executable,
                "-I",
                "-B",
                "-c",
                WORKER,
                str(ROOT),
                str(self.root),
                str(ready),
                str(timeout),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        def stop() -> None:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)

        self.addCleanup(stop)
        return process, ready

    def wait_for(self, path: Path, process: subprocess.Popen) -> None:
        deadline = time.monotonic() + 20
        while not path.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(path.exists(), "worker did not enter the setup lock")

    def test_normal_and_controlled_error_release_but_interrupt_retains(self) -> None:
        path = self.root / launch.LOCK_NAME
        with launch.SetupLock(self.root) as holder:
            self.assertEqual(launch.read_owner(path), holder.owner)
            self.assertTrue(launch.process_alive(holder.owner["pid"]))
        self.assertFalse(path.exists())
        with self.assertRaisesRegex(ValueError, "controlled"):
            with launch.SetupLock(self.root):
                raise ValueError("controlled child exit")
        self.assertFalse(path.exists())
        with self.assertRaises(KeyboardInterrupt):
            with launch.SetupLock(self.root):
                raise KeyboardInterrupt
        self.assertTrue(path.exists())

    def test_second_process_times_out_without_mutation_or_owner_removal(self) -> None:
        with launch.SetupLock(self.root) as holder:
            process, ready = self.worker(timeout=0.15)
            stdout, stderr = process.communicate(timeout=20)
            self.assertNotEqual(process.returncode, 0, stdout)
            self.assertIn(b"Setup lock timeout", stderr)
            self.assertFalse(ready.exists())
            self.assertEqual(launch.read_owner(holder.path), holder.owner)

    def test_crashed_owner_is_not_auto_reaped_and_manual_recovery_is_guarded(self) -> None:
        process, ready = self.worker()
        self.wait_for(ready, process)
        path = self.root / launch.LOCK_NAME
        owner = launch.read_owner(path)
        self.assertIsNotNone(owner)
        self.assertEqual(owner["pid"], process.pid)
        with self.assertRaisesRegex(RuntimeError, "active or unknown"):
            launch.recover_lock(self.root, owner["token"], True)
        process.terminate()
        process.communicate(timeout=10)
        with self.assertRaisesRegex(RuntimeError, "Interrupted setup"):
            with launch.SetupLock(self.root, 0):
                self.fail("abandoned setup must never run")
        with self.assertRaises(ValueError):
            launch.recover_lock(self.root, owner["token"], False)
        with self.assertRaises(RuntimeError):
            launch.recover_lock(self.root, "0" * 32, True)
        self.assertEqual(launch.read_owner(path), owner)
        launch.recover_lock(self.root, owner["token"], True)
        self.assertFalse(path.exists())
        with launch.SetupLock(self.root, 0):
            pass

    def test_unknown_metadata_and_changed_owner_are_preserved(self) -> None:
        path = self.root / launch.LOCK_NAME
        path.mkdir()
        with self.assertRaises(TimeoutError):
            with launch.SetupLock(self.root, 0):
                self.fail("unknown lock must block setup")
        with self.assertRaises(RuntimeError):
            launch.recover_lock(self.root, "0" * 32, True)
        self.assertTrue(path.exists())
        path.rmdir()  # Exact empty fixture directory only.
        holder = launch.SetupLock(self.root)
        holder.__enter__()
        metadata = path / f"owner-{holder.owner['token']}.json"
        metadata.write_text("{}")
        with self.assertRaises(RuntimeError):
            holder.__exit__(None, None, None)
        self.assertEqual(metadata.read_text(), "{}")

    def test_recovery_does_not_guess_owner_when_query_is_unavailable(self) -> None:
        with launch.SetupLock(self.root) as holder:
            with mock.patch.object(launch, "process_alive", return_value=None):
                with self.assertRaises(RuntimeError):
                    launch.recover_lock(self.root, holder.owner["token"], True)
            self.assertEqual(launch.read_owner(holder.path), holder.owner)

    def test_release_retries_transient_sharing_but_bounds_permission_failure(self) -> None:
        holder = launch.SetupLock(self.root)
        holder.__enter__()
        original = Path.unlink
        attempts = []

        def unlink(path, *args, **kwargs):
            attempts.append(path)
            if len(attempts) == 1:
                raise PermissionError("reader still holds metadata")
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", unlink):
            holder.__exit__(None, None, None)
        self.assertEqual(len(attempts), 2)
        self.assertFalse(holder.path.exists())
        with (
            mock.patch.object(launch.time, "monotonic", side_effect=[0, 0.1, 1.1]),
            mock.patch.object(launch.time, "sleep"),
        ):
            operation = mock.Mock(side_effect=PermissionError("persistent"))
            with self.assertRaises(PermissionError):
                launch.retry_permission(operation)
        self.assertEqual(operation.call_count, 2)

    def test_metadata_write_failure_cleans_only_own_unstarted_lock(self) -> None:
        with mock.patch.object(launch.json, "dump", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                with launch.SetupLock(self.root):
                    self.fail("failed metadata must not start setup")
        self.assertFalse((self.root / launch.LOCK_NAME).exists())
        with mock.patch.object(launch.json, "dump", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                with launch.SetupLock(self.root):
                    self.fail("interrupt must not start setup")
        self.assertTrue((self.root / launch.LOCK_NAME).exists())

    def test_separate_projects_do_not_share_a_lock(self) -> None:
        other = self.root / "other"
        other.mkdir()
        with launch.SetupLock(self.root, 0), launch.SetupLock(other, 0):
            self.assertTrue((other / launch.LOCK_NAME).is_dir())

    def test_prepare_creates_only_missing_venv_then_apply_probe_install(self) -> None:
        with (
            mock.patch.object(launch, "run") as run,
            mock.patch.object(
                launch.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)
            ),
        ):
            launch.prepare(self.root, "engine")
        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(calls[0], [sys.executable, "-I", "-m", "venv", ".venv"])
        self.assertEqual(calls[1][-1], "--apply")
        self.assertEqual(calls[2][-5:], ["-m", "pip", "install", "-r", "requirements.txt"])
        python = launch.python_path(self.root)
        python.parent.mkdir(parents=True)
        python.touch()
        with (
            mock.patch.object(launch, "run") as run,
            mock.patch.object(
                launch.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ),
        ):
            launch.prepare(self.root, "conversation-editor")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-1], "--apply")
        with (
            mock.patch.object(launch, "run") as run,
            mock.patch.object(
                launch.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Tkinter"):
                launch.prepare(self.root, "conversation-editor")
        self.assertEqual(run.call_count, 1)

    def test_postlock_check_and_application_do_not_hold_setup_lock(self) -> None:
        python = launch.python_path(self.root)
        python.parent.mkdir(parents=True)
        python.touch()
        events = []

        def prepare(root, entry) -> None:
            self.assertTrue((root / launch.LOCK_NAME).is_dir())
            events.append("prepare")

        def run(command, root) -> None:
            self.assertFalse((root / launch.LOCK_NAME).exists())
            events.append("check" if command[-1].endswith("bootstrap.py") else "app")

        with (
            mock.patch.object(launch, "prepare", side_effect=prepare),
            mock.patch.object(launch, "run", side_effect=run),
        ):
            launch.launch(self.root, "game", fullscreen=True)
        self.assertEqual(events, ["prepare", "check", "app"])
        with (
            mock.patch.object(launch, "prepare"),
            mock.patch.object(launch, "run", side_effect=RuntimeError("check failed")) as run,
            mock.patch.object(launch.subprocess, "Popen") as popen,
        ):
            with self.assertRaisesRegex(RuntimeError, "check failed"):
                launch.launch(self.root, "engine")
        popen.assert_not_called()
        self.assertEqual(run.call_count, 1)
        self.assertTrue(run.call_args.args[0][-1].endswith("bootstrap.py"))

    def test_cli_rejects_invalid_timeout_or_recovery_without_launch(self) -> None:
        for value in ("nan", "inf", "-1", "3601"):
            with (
                self.subTest(value=value),
                mock.patch.object(launch, "ROOT", self.root),
                mock.patch.object(launch, "prepare") as prepare,
                mock.patch.object(launch, "run") as run,
                mock.patch.object(launch.subprocess, "Popen") as popen,
            ):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(launch.main(["game", "--lock-timeout", value]), 1)
                self.assertFalse((self.root / launch.LOCK_NAME).exists())
                prepare.assert_not_called()
                run.assert_not_called()
                popen.assert_not_called()
        with (
            mock.patch.object(launch, "launch") as start,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit):
                launch.main(["--recover-lock", "0" * 32])
            with self.assertRaises(SystemExit):
                launch.main(["engine", "--fullscreen"])
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
