"""CLI bridge contract; these tests do not require a Godot installation."""

from __future__ import annotations

from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import engine_app
from engine import godot_runner
from engine.project_creator import ProjectCreator


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "engine_project.json"


class GodotRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.executable = Path(self.temp.name) / "Godot with spaces.exe"
        self.executable.touch()

    def test_explicit_executable_overrides_environment(self) -> None:
        with patch.dict(os.environ, {"GODOT_BIN": "missing.exe"}):
            self.assertEqual(godot_runner.resolve_godot(self.executable), self.executable.resolve())

    def test_environment_executable_is_used(self) -> None:
        with patch.dict(os.environ, {"GODOT_BIN": str(self.executable)}):
            self.assertEqual(godot_runner.resolve_godot(), self.executable.resolve())

    def test_invalid_environment_does_not_fall_back(self) -> None:
        with patch.dict(os.environ, {"GODOT_BIN": str(self.executable.parent / "missing.exe")}):
            with patch.object(godot_runner.shutil, "which") as which:
                with self.assertRaises(FileNotFoundError):
                    godot_runner.resolve_godot()
                which.assert_not_called()

    def test_empty_environment_is_an_error(self) -> None:
        with patch.dict(os.environ, {"GODOT_BIN": " "}):
            with self.assertRaisesRegex(ValueError, "non-empty"):
                godot_runner.resolve_godot()

    def test_directory_is_not_an_executable(self) -> None:
        with self.assertRaises(FileNotFoundError):
            godot_runner.resolve_godot(self.executable.parent)

    def test_path_discovery_supports_godot4(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(godot_runner.shutil, "which", side_effect=[None, str(self.executable)]) as which:
                self.assertEqual(godot_runner.resolve_godot(), self.executable.resolve())
                self.assertEqual(which.call_count, 2)

    def test_missing_executable_gives_configuration_hint(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(godot_runner.shutil, "which", return_value=None):
                with self.assertRaisesRegex(FileNotFoundError, "--godot-bin"):
                    godot_runner.resolve_godot()

    def test_version_probe_is_bounded_and_accepts_godot4(self) -> None:
        result = subprocess.CompletedProcess([], 0, "4.7.2.stable.official.hash\n", "")
        with patch.object(godot_runner.subprocess, "run", return_value=result) as run:
            godot_runner.verify_godot(self.executable)
        run.assert_called_once_with(
            [str(self.executable), "--version"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10, check=False,
        )

    def test_failed_or_unsupported_probe_never_starts_game(self) -> None:
        for code, version, error in [(0, "3.6.stable", ""), (0, "not Godot", ""), (9, "4.7.2.stable", "probe failed")]:
            with self.subTest(code=code, version=version):
                result = subprocess.CompletedProcess([], code, version, error)
                with patch.object(godot_runner.subprocess, "run", return_value=result) as run:
                    with self.assertRaisesRegex(RuntimeError, "version check failed") as caught:
                        godot_runner.run_godot(MANIFEST, executable=self.executable)
                    self.assertIn(error, str(caught.exception))
                    self.assertEqual(run.call_count, 1)

    def test_probe_timeout_never_starts_game(self) -> None:
        with patch.object(godot_runner.subprocess, "run", side_effect=subprocess.TimeoutExpired([], 10)) as run:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                godot_runner.run_godot(MANIFEST, executable=self.executable)
            self.assertEqual(run.call_count, 1)

    def test_selected_project_root_and_game_flags_are_separate(self) -> None:
        parent = Path(self.temp.name) / "folder with spaces"
        parent.mkdir()
        selected = ProjectCreator().create_project(parent, "別の 住処")
        with patch.object(godot_runner, "verify_godot"):
            with patch.object(godot_runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)) as run:
                result = godot_runner.run_godot(
                    selected, executable=self.executable, headless=True, test_frames=180, seed=12345,
                )
        self.assertEqual(result, 7)
        run.assert_called_once_with(
            [str(self.executable.resolve()), "--path", str(ROOT / "godot"), "--headless",
             "--fixed-fps", "60", "--", "--content-root", str(selected.parent.resolve()),
             "--test-frames", "180", "--seed", "12345"],
            cwd=selected.parent.resolve(), check=False,
        )

    def test_interactive_run_has_no_headless_or_fixed_frame_options(self) -> None:
        with patch.object(godot_runner, "verify_godot"):
            with patch.object(godot_runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(godot_runner.run_godot(MANIFEST, executable=self.executable), 0)
        run.assert_called_once_with(
            [str(self.executable.resolve()), "--path", str(ROOT / "godot"), "--", "--content-root", str(ROOT)],
            cwd=ROOT, check=False,
        )

    def test_invalid_simulation_options_stop_before_process_start(self) -> None:
        for options in ({"headless": True}, {"test_frames": 0}, {"test_frames": -1},
                        {"test_frames": True}, {"seed": True}, {"seed": 2**63}, {"seed": -(2**63) - 1}):
            with self.subTest(options=options), patch.object(godot_runner.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    godot_runner.run_godot(MANIFEST, executable=self.executable, **options)
                run.assert_not_called()

    def test_special_project_is_rejected_before_process_start(self) -> None:
        with patch.object(godot_runner.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "standard"):
                godot_runner.run_godot(ROOT / "projects/obakeno_sumika_special/engine_project.json")
            run.assert_not_called()

    def test_noncanonical_manifest_is_not_silently_replaced(self) -> None:
        with patch.object(godot_runner.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "engine_project.json"):
                godot_runner.run_godot(ROOT / "other.json")
            run.assert_not_called()

    def test_missing_source_runtime_does_not_fall_back_to_python(self) -> None:
        with patch.object(godot_runner, "RUNTIME_ROOT", Path(self.temp.name)):
            with patch.object(godot_runner.subprocess, "run") as run:
                with self.assertRaisesRegex(FileNotFoundError, "runtime is missing"):
                    godot_runner.run_godot(MANIFEST)
                run.assert_not_called()

    def test_cli_requires_no_tk_or_python_game_import_and_returns_exit_code(self) -> None:
        argv = ["engine_app.py", "--playtest-godot", "--headless", "--test-frames", "60", "--seed", "4"]
        with patch.object(sys, "argv", argv), patch.dict(sys.modules, {"tkinter": None, "game": None}):
            with patch.object(godot_runner, "run_godot", return_value=7) as run:
                self.assertEqual(engine_app.main(), 7)
        run.assert_called_once_with(MANIFEST, executable=None, headless=True, test_frames=60, seed=4)

    def test_cli_configuration_failure_is_visible_and_nonzero(self) -> None:
        error = io.StringIO()
        with patch.object(sys, "argv", ["engine_app.py", "--playtest-godot"]):
            with patch.object(godot_runner, "run_godot", side_effect=FileNotFoundError("missing Godot")):
                with redirect_stderr(error):
                    self.assertEqual(engine_app.main(), 1)
        self.assertIn("Godot playtest failed: missing Godot", error.getvalue())

    def test_godot_options_are_not_silently_ignored_by_other_modes(self) -> None:
        for options in (["--validate", "--headless"], ["--describe", "--seed", "0"],
                        ["--godot-bin", "missing.exe"], ["--test-frames", "60"],
                        ["--playtest-godot", "--validate"]):
            with self.subTest(options=options), patch.object(sys, "argv", ["engine_app.py", *options]):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    engine_app.parse_args()
                self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
