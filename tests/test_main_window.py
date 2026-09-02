import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from engine.main_window import MainWindow
from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher
from engine.project_creator import ProjectCreator


class MainWindowTests(unittest.TestCase):
    def test_open_project_switches_launch_target(self):
        root = tk.Tk()
        root.withdraw()
        try:
            current = load_project_manifest(PROJECT_DIR / "engine_project.json")
            window = MainWindow(root, current, ProcessLauncher(current))
            with tempfile.TemporaryDirectory() as temp_dir:
                manifest_path = ProjectCreator().create_project(Path(temp_dir), "other")
                window.open_project(manifest_path)

                self.assertEqual(window.manifest.name, "other")
                self.assertEqual(window.manifest.root, manifest_path.parent)
                with patch("engine.process_launcher.subprocess.Popen") as popen:
                    window.launcher.launch_game()
                popen.assert_called_once_with(
                    [sys.executable, str(manifest_path.parent / "game.py")],
                    cwd=manifest_path.parent,
                )
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
