"""Discovery and skip decisions without requiring or starting a Godot process."""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import call, patch

from engine import godot_runner
from tests.godot_support import find_test_godot


ROOT = Path(__file__).resolve().parents[1]
CONSUMERS = (
    ("tests/test_godot_runtime.py", "GodotRuntimeTests"),
    ("tests/test_portable_project_contract.py", "GodotManifestContractTests"),
)


class GodotSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="Godot 日本語 ")
        self.addCleanup(directory.cleanup)
        self.executable = Path(directory.name) / "Godot with spaces.exe"
        self.executable.touch()

    def test_godot4_only_on_path_enables_both_suites(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(godot_runner.shutil, "which", side_effect=lambda name:
                              str(self.executable) if name == "godot4" else None) as which:
                for path, class_name in CONSUMERS:
                    with self.subTest(path=path):
                        namespace = runpy.run_path(str(ROOT / path))
                        self.assertEqual(namespace["GODOT"], self.executable.resolve())
                        self.assertFalse(getattr(namespace[class_name], "__unittest_skip__", False))
                self.assertEqual(which.call_args_list, [call("godot"), call("godot4")] * 2)

    def test_godot_is_preferred_to_godot4(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(godot_runner.shutil, "which", return_value=str(self.executable)) as which:
                self.assertEqual(find_test_godot(), self.executable.resolve())
                which.assert_called_once_with("godot")

    def test_configured_executable_enables_both_suites_without_path_lookup(self) -> None:
        with patch.dict(os.environ, {"GODOT_BIN": str(self.executable)}):
            with patch.object(godot_runner.shutil, "which") as which:
                for path, class_name in CONSUMERS:
                    with self.subTest(path=path):
                        namespace = runpy.run_path(str(ROOT / path))
                        self.assertEqual(namespace["GODOT"], self.executable.resolve())
                        self.assertFalse(getattr(namespace[class_name], "__unittest_skip__", False))
                which.assert_not_called()

    def test_unconfigured_absence_skips_both_suites(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(godot_runner.shutil, "which", return_value=None) as which:
                self.assertIsNone(find_test_godot())
                for path, class_name in CONSUMERS:
                    with self.subTest(path=path):
                        namespace = runpy.run_path(str(ROOT / path))
                        self.assertIsNone(namespace["GODOT"])
                        self.assertTrue(namespace[class_name].__unittest_skip__)
                        self.assertIn("GODOT_BIN", namespace[class_name].__unittest_skip_why__)
                self.assertEqual(which.call_args_list, [call("godot"), call("godot4")] * 3)

    def test_invalid_configuration_fails_instead_of_skipping_or_falling_back(self) -> None:
        cases = (
            (str(self.executable.parent / "missing.exe"), FileNotFoundError),
            (str(self.executable.parent), FileNotFoundError),
            ("", ValueError),
            ("  ", ValueError),
        )
        for configured, error in cases:
            with self.subTest(configured=configured), patch.dict(os.environ, {"GODOT_BIN": configured}):
                with patch.object(godot_runner.shutil, "which", return_value=str(self.executable)) as which:
                    with self.assertRaises(error):
                        find_test_godot()
                    for path, _ in CONSUMERS:
                        with self.subTest(path=path), self.assertRaises(error):
                            runpy.run_path(str(ROOT / path))
                    which.assert_not_called()


if __name__ == "__main__":
    unittest.main()
