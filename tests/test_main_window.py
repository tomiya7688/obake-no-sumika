import sys
import tempfile
import tkinter as tk
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from engine.main_window import MainWindow
from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher
from engine.project_creator import ProjectCreator


class MainWindowTests(unittest.TestCase):
    def make_root(self):
        root = tk.Tk()
        root.withdraw()
        # Flush theme initialization before creating/destroying another Tcl
        # interpreter; otherwise deferred ttk events can outlive the window.
        root.update_idletasks()
        return root

    def test_open_project_switches_launch_target(self):
        root = self.make_root()
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
                expected_python = Path(sys.executable)
                if expected_python.name.lower() == "pythonw.exe":
                    expected_python = expected_python.with_name("python.exe")
                self.assertEqual(popen.call_args.args[0], [str(expected_python), str(manifest_path.parent / "game.py")])
                self.assertEqual(popen.call_args.kwargs["cwd"], manifest_path.parent)
        finally:
            root.destroy()

    def wait_for(self, root, condition):
        deadline = time.monotonic() + 10
        while not condition() and time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
        self.assertTrue(condition(), "Tk launch monitor did not finish")

    def make_window(self, root, directory, source):
        script = Path(directory) / "test_game.py"
        script.write_text(source, encoding="utf-8")
        manifest = replace(load_project_manifest(PROJECT_DIR / "engine_project.json"),
                           root=Path(directory), entrypoint=script)
        return MainWindow(root, manifest, ProcessLauncher(manifest))

    def test_immediate_crash_is_not_reported_as_success_and_shows_traceback(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as directory:
                window = self.make_window(root, directory, "raise RuntimeError('起動時の例外')\n")
                statuses = []
                window.status.trace_add("write", lambda *_: statuses.append(window.status.get()))
                with patch("engine.main_window.messagebox.showerror") as error:
                    window._launch_game()
                    self.assertIn("確認しています", window.status.get())
                    self.wait_for(root, lambda: error.called)
                self.assertTrue(all("起動しました" not in status for status in statuses))
                self.assertIn("異常終了", window.status.get())
                detail = error.call_args.args[1]
                self.assertIn("RuntimeError: 起動時の例外", detail)
                self.assertIn("終了コード: 1", detail)
                self.assertIn(str(Path(directory) / "tmp" / "launch_logs"), detail)
                self.assertEqual(window._launch_poll_ids, set())
        finally:
            root.destroy()

    def test_normal_quick_exit_is_not_an_error(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as directory:
                window = self.make_window(root, directory, "print('正常終了')\n")
                with patch("engine.main_window.messagebox.showerror") as error:
                    window._launch_game()
                    self.wait_for(root, lambda: "が終了しました" in window.status.get())
                    error.assert_not_called()
                self.assertEqual(window._launch_poll_ids, set())
        finally:
            root.destroy()

    def test_keeps_monitoring_after_running_and_after_project_switch(self):
        root = self.make_root()
        try:
            with tempfile.TemporaryDirectory() as directory:
                window = self.make_window(root, directory,
                                          "import time\ntime.sleep(1.2)\nraise RuntimeError('実行中の例外')\n")
                original_name = window.manifest.name
                with patch("engine.main_window.messagebox.showerror") as error:
                    window._launch_game()
                    self.wait_for(root, lambda: "実行中" in window.status.get())
                    window._set_project(replace(window.manifest, name="別プロジェクト"))
                    self.wait_for(root, lambda: error.called)
                self.assertIn(original_name, error.call_args.args[1])
                self.assertIn("実行中の例外", error.call_args.args[1])
                self.assertNotIn("別プロジェクト", error.call_args.args[1])
        finally:
            root.destroy()

    def test_spawn_error_is_reported_without_scheduling_poll(self):
        root = self.make_root()
        try:
            manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")
            window = MainWindow(root, manifest, ProcessLauncher(manifest))
            with patch("engine.main_window.messagebox.showerror") as error:
                window._run("ゲーム", lambda: (_ for _ in ()).throw(OSError("起動不可")))
            self.assertIn("起動に失敗", window.status.get())
            self.assertIn("起動不可", error.call_args.args[1])
            self.assertEqual(window._launch_poll_ids, set())
        finally:
            root.destroy()

    def test_log_read_error_keeps_exit_code_and_log_path(self):
        from unittest.mock import Mock

        root = self.make_root()
        try:
            manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")
            window = MainWindow(root, manifest, ProcessLauncher(manifest))
            launched = Mock(log_path=Path("missing.log"))
            launched.poll.return_value = 7
            launched.log_tail.side_effect = OSError("読取不可")
            with patch("engine.main_window.messagebox.showerror") as error:
                window._poll_launch("ゲーム", launched, announced=False)
            self.assertIn("終了コード: 7", error.call_args.args[1])
            self.assertIn("missing.log", error.call_args.args[1])
            self.assertIn("読取不可", error.call_args.args[1])
        finally:
            root.destroy()

    def test_destroy_cancels_pending_callbacks_without_killing_child(self):
        from unittest.mock import Mock

        root = self.make_root()
        manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")
        window = MainWindow(root, manifest, ProcessLauncher(manifest))
        launched = Mock()
        window._run("ゲーム", lambda: launched)
        self.assertTrue(window._launch_poll_ids)
        root.destroy()
        self.assertEqual(window._launch_poll_ids, set())
        launched.process.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
