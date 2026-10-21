"""Background preparation, cancellation and explicit launch without GUI widgets."""

import os
import sys
import tempfile
import unittest
from concurrent.futures import CancelledError
from dataclasses import replace
from pathlib import Path
from threading import Event, get_ident
from unittest.mock import Mock, patch

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import godot_runner
from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher
from engine.project_creator import ProjectCreator


class GodotPreparationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="Godot preparation 日本語 ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest_path = ProjectCreator().create_project(self.root, "待ち時間の住処")
        self.manifest = load_project_manifest(self.manifest_path)
        self.launcher = ProcessLauncher(self.manifest)
        self.executable = self.root / "Godot with spaces.exe"
        self.executable.touch()

    def invocation(self, manifest=None):
        selected = manifest if manifest is not None else self.manifest
        return godot_runner.GodotInvocation((str(self.executable), "--", "--content-root", str(selected.root)), selected)

    def test_blocked_worker_returns_future_without_spawning_game(self):
        entered, release = Event(), Event()
        caller = get_ident()

        def blocked(*args, **kwargs):
            self.assertNotEqual(get_ident(), caller)
            entered.set()
            self.assertTrue(release.wait(5))
            return self.invocation(kwargs["expected_manifest"])

        with patch.object(godot_runner, "prepare_godot_invocation", side_effect=blocked), \
                patch("engine.process_launcher.subprocess.Popen") as popen:
            future = self.launcher.prepare_godot_async(executable=self.executable)
            try:
                self.assertTrue(entered.wait(2))
                self.assertFalse(future.done())
                self.assertTrue(future.running())
                # Future cancellation only applies before its worker starts.
                self.assertFalse(future.cancel())
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5), self.invocation())
            popen.assert_not_called()
        self.assertFalse(self.launcher.log_dir.exists())

    def test_worker_failures_are_reported_through_future(self):
        for problem in (RuntimeError("準備に失敗"), SystemExit(9)):
            with self.subTest(problem=problem), \
                    patch.object(godot_runner, "prepare_godot_invocation", side_effect=problem), \
                    patch("engine.process_launcher.subprocess.Popen") as popen:
                future = self.launcher.prepare_godot_async(executable=self.executable)
                with self.assertRaises(type(problem)) as caught:
                    future.result(timeout=5)
                self.assertIs(caught.exception, problem)
                popen.assert_not_called()
        self.assertFalse(self.launcher.log_dir.exists())

    def test_unstarted_request_can_cancel_without_preparation(self):
        with patch.object(godot_runner, "Thread") as thread, \
                patch.object(godot_runner, "prepare_godot_invocation") as prepare:
            future = self.launcher.prepare_godot_async(executable=self.executable)
            self.assertTrue(future.cancel())
            thread.call_args.kwargs["target"]()
            self.assertTrue(future.cancelled())
            prepare.assert_not_called()
            self.assertTrue(thread.call_args.kwargs["daemon"])
            thread.return_value.start.assert_called_once_with()
            with self.assertRaises(CancelledError):
                future.result(timeout=0)

    def test_thread_start_failure_is_a_completed_future_error(self):
        with patch.object(godot_runner, "Thread") as thread:
            thread.return_value.start.side_effect = RuntimeError("cannot start worker")
            future = self.launcher.prepare_godot_async(executable=self.executable)
            self.assertTrue(future.done())
            with self.assertRaisesRegex(RuntimeError, "cannot start worker"):
                future.result(timeout=0)

    def test_selection_is_deep_copied_before_worker_runs(self):
        with patch.object(godot_runner, "Thread") as thread:
            future = self.launcher.prepare_godot_async(executable=self.executable, test_frames=60, seed=4)
            original = dict(self.manifest.content)
            self.manifest.content["room"] = self.root / "changed-room.json"

            def prepared(*args, **kwargs):
                self.assertEqual(kwargs["expected_manifest"].content, original)
                self.assertEqual(kwargs["test_frames"], 60)
                self.assertEqual(kwargs["seed"], 4)
                return self.invocation(kwargs["expected_manifest"])

            with patch.object(godot_runner, "prepare_godot_invocation", side_effect=prepared):
                thread.call_args.kwargs["target"]()
            invocation = future.result(timeout=0)
            with patch("engine.process_launcher.subprocess.Popen") as popen:
                with self.assertRaisesRegex(ValueError, "selection changed"):
                    self.launcher.launch_prepared_godot(invocation)
                popen.assert_not_called()

    def test_relative_paths_are_captured_before_worker_runs(self):
        first, second = self.root / "first", self.root / "second"
        first.mkdir()
        second.mkdir()
        original = Path.cwd()
        # Windows resolves relative paths with a native API, not just os.getcwd.
        # Change only this test process's cwd and always restore it.
        try:
            os.chdir(first)
            with patch.object(godot_runner, "Thread") as thread:
                future = godot_runner.prepare_godot_invocation_async(Path("engine_project.json"), executable=Path("godot.exe"))
            os.chdir(second)
            with patch.object(godot_runner, "prepare_godot_invocation", return_value=self.invocation()) as prepare:
                thread.call_args.kwargs["target"]()
        finally:
            os.chdir(original)
        self.assertEqual(prepare.call_args.args[0], first / "engine_project.json")
        self.assertEqual(prepare.call_args.kwargs["executable"], first / "godot.exe")
        self.assertEqual(future.result(timeout=0), self.invocation())

    def test_requests_complete_independently(self):
        entered, release = Event(), Event()

        def independent(*args, **kwargs):
            if kwargs["seed"] == 2:
                raise RuntimeError("second request failed")
            entered.set()
            self.assertTrue(release.wait(5))
            return self.invocation(kwargs["expected_manifest"])

        with patch.object(godot_runner, "prepare_godot_invocation", side_effect=independent):
            first = self.launcher.prepare_godot_async(executable=self.executable, seed=1)
            try:
                self.assertTrue(entered.wait(2))
                second = self.launcher.prepare_godot_async(executable=self.executable, seed=2)
                with self.assertRaisesRegex(RuntimeError, "second request failed"):
                    second.result(timeout=5)
                self.assertFalse(first.done())
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5), self.invocation())

    def test_shared_validation_errors_do_not_create_launch_logs(self):
        for launcher, options in (
            (self.launcher, {"headless": True}),
            (ProcessLauncher(replace(self.manifest, name="different")), {}),
            (ProcessLauncher(replace(self.manifest, project_type="special")), {}),
        ):
            with self.subTest(options=options, manifest=launcher.manifest.name), \
                    patch.object(godot_runner, "verify_godot") as verify, \
                    patch("engine.process_launcher.subprocess.Popen") as popen:
                future = launcher.prepare_godot_async(executable=self.executable, **options)
                with self.assertRaises(ValueError):
                    future.result(timeout=5)
                verify.assert_not_called()
                popen.assert_not_called()
                self.assertFalse(launcher.log_dir.exists())

    def test_explicit_launch_uses_completed_invocation_without_reprobing(self):
        invocation = self.invocation()
        with patch.object(godot_runner, "verify_godot") as verify, \
                patch("engine.process_launcher.prepare_godot_invocation") as prepare, \
                patch("engine.process_launcher.subprocess.Popen", return_value=Mock()) as popen:
            child = self.launcher.launch_prepared_godot(invocation)
            self.assertEqual(popen.call_args.args[0], list(invocation.command))
            self.assertTrue(child.log_path.is_file())
            self.assertTrue(popen.call_args.kwargs["stdout"].closed)
            verify.assert_not_called()
            prepare.assert_not_called()
        other = ProcessLauncher(replace(self.manifest, name="other"))
        with patch("engine.process_launcher.subprocess.Popen") as popen:
            with self.assertRaises(ValueError):
                other.launch_prepared_godot(invocation)
            with self.assertRaises(TypeError):
                self.launcher.launch_prepared_godot({"command": invocation.command})
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
