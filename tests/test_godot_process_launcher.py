"""Godot launch preparation and persistent diagnostics without GUI widgets."""

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import godot_runner
from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher
from engine.project_creator import ProjectCreator


class GodotProcessLauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="Godot launcher 日本語 ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest_path = ProjectCreator().create_project(self.root, "別の 住処")
        self.manifest = load_project_manifest(self.manifest_path)
        self.launcher = ProcessLauncher(self.manifest)
        self.executable = self.root / "Godot with spaces.exe"
        self.executable.touch()

    def test_shared_preparation_returns_child_without_waiting(self):
        command = (str(self.executable), "--path", str(godot_runner.RUNTIME_ROOT), "--",
                   "--content-root", str(self.manifest.root))
        invocation = godot_runner.GodotInvocation(command, self.manifest)
        process = Mock()
        with patch("engine.process_launcher.prepare_godot_invocation", return_value=invocation) as prepare, \
                patch("engine.process_launcher.subprocess.Popen", return_value=process) as popen:
            child = self.launcher.launch_godot(executable=self.executable, headless=True, test_frames=60, seed=4)
        prepare.assert_called_once_with(
            self.manifest_path, executable=self.executable, headless=True, test_frames=60,
            seed=4, expected_manifest=self.manifest,
        )
        self.assertIs(child.process, process)
        process.wait.assert_not_called()
        process.poll.assert_not_called()
        self.assertEqual(popen.call_args.args[0], list(command))
        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["cwd"], self.manifest.root)
        self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.assertTrue(kwargs["stdout"].closed)
        self.assertEqual(child.log_path.parent, self.manifest.root / "tmp" / "launch_logs")
        self.assertTrue(child.log_path.name.startswith("godot-"))
        self.assertTrue(child.log_path.is_file())

    def test_actual_preparation_keeps_selected_root_and_engine_flags(self):
        with patch.object(godot_runner, "verify_godot") as verify, \
                patch("engine.process_launcher.subprocess.Popen") as popen:
            self.launcher.launch_godot(executable=self.executable, headless=True, test_frames=180, seed=12345)
        verify.assert_called_once_with(self.executable.resolve())
        self.assertEqual(popen.call_args.args[0], [
            str(self.executable.resolve()), "--path", str(godot_runner.RUNTIME_ROOT), "--headless",
            "--fixed-fps", "60", "--", "--content-root", str(self.manifest.root),
            "--test-frames", "180", "--seed", "12345",
        ])
        self.assertNotIn(str(self.manifest.entrypoint), popen.call_args.args[0])

    def test_interactive_launch_has_no_headless_or_fixed_fps(self):
        with patch.object(godot_runner, "verify_godot"), patch("engine.process_launcher.subprocess.Popen") as popen:
            self.launcher.launch_godot(executable=self.executable)
        self.assertEqual(popen.call_args.args[0], [str(self.executable.resolve()), "--path",
                         str(godot_runner.RUNTIME_ROOT), "--", "--content-root", str(self.manifest.root)])

    def test_invalid_options_fail_before_probe_spawn_or_log_creation(self):
        cases = ({"headless": True}, {"test_frames": 0}, {"test_frames": True},
                 {"seed": True}, {"seed": 2**63})
        for options in cases:
            with self.subTest(options=options), patch.object(godot_runner, "verify_godot") as verify, \
                    patch("engine.process_launcher.subprocess.Popen") as popen:
                with self.assertRaises(ValueError):
                    self.launcher.launch_godot(executable=self.executable, **options)
                verify.assert_not_called()
                popen.assert_not_called()
                self.assertFalse(self.launcher.log_dir.exists())

    def test_selected_manifest_mismatch_is_rejected_before_probe(self):
        # An alternate/stale selection must not silently start the canonical project.
        launcher = ProcessLauncher(replace(self.manifest, name="異なるプロジェクト"))
        with patch.object(godot_runner, "verify_godot") as verify, \
                patch("engine.process_launcher.subprocess.Popen") as popen:
            with self.assertRaisesRegex(ValueError, "reload the project"):
                launcher.launch_godot(executable=self.executable)
            verify.assert_not_called()
            popen.assert_not_called()
        self.assertFalse(launcher.log_dir.exists())

    def test_special_selection_does_not_fall_back_to_standard(self):
        launcher = ProcessLauncher(replace(self.manifest, project_type="special"))
        with patch("engine.process_launcher.prepare_godot_invocation") as prepare, \
                patch("engine.process_launcher.subprocess.Popen") as popen:
            with self.assertRaisesRegex(ValueError, "standard"):
                launcher.launch_godot(executable=self.executable)
            prepare.assert_not_called()
            popen.assert_not_called()
        self.assertFalse(launcher.log_dir.exists())

    def test_configuration_and_probe_failures_do_not_spawn_or_create_logs(self):
        with patch.dict(os.environ, {"GODOT_BIN": ""}), patch("engine.process_launcher.subprocess.Popen") as popen:
            with self.assertRaisesRegex(ValueError, "non-empty"):
                self.launcher.launch_godot()
            popen.assert_not_called()
        with patch.object(godot_runner, "verify_godot", side_effect=RuntimeError("version check failed")), \
                patch("engine.process_launcher.subprocess.Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "version check failed"):
                self.launcher.launch_godot(executable=self.executable)
            popen.assert_not_called()
        self.assertFalse(self.launcher.log_dir.exists())

    def test_spawn_failure_closes_parent_log_handle(self):
        with patch.object(godot_runner, "verify_godot"), \
                patch("engine.process_launcher.subprocess.Popen", side_effect=OSError("cannot spawn")) as popen:
            with self.assertRaisesRegex(OSError, "cannot spawn"):
                self.launcher.launch_godot(executable=self.executable)
        self.assertTrue(popen.call_args.kwargs["stdout"].closed)

    def test_godot_logs_are_unique_and_remain_readable(self):
        def capture(*args, **kwargs):
            kwargs["stdout"].write("Godotの診断\n".encode("utf-8"))
            return Mock()

        with patch.object(godot_runner, "verify_godot"), \
                patch("engine.process_launcher.subprocess.Popen", side_effect=capture):
            first = self.launcher.launch_godot(executable=self.executable)
            second = self.launcher.launch_godot(executable=self.executable)
        self.assertNotEqual(first.log_path, second.log_path)
        self.assertEqual(first.log_tail(), "Godotの診断\n")
        self.assertEqual(second.log_tail(), "Godotの診断\n")


if __name__ == "__main__":
    unittest.main()
