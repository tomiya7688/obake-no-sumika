"""Tk-main-thread Godot preparation/launch lifecycle and real runtime wiring."""

from concurrent.futures import Future
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Event, get_ident
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.godot_runner import GodotInvocation
from engine.main_window import MainWindow
from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher
from engine.project_creator import ProjectCreator
from tests.godot_support import find_test_godot

ROOT = Path(__file__).resolve().parents[1]
GODOT = find_test_godot()


class WindowFixture:
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.update_idletasks()
        self.addCleanup(self.root.destroy)
        self.manifest = load_project_manifest(ROOT / "engine_project.json")
        self.launcher = Mock(spec=ProcessLauncher)
        self.window = MainWindow(self.root, self.manifest, self.launcher)
        self.child = Mock(log_path=Path("godot-test.log"))
        self.child.poll.return_value = 0
        self.launcher.launch_prepared_godot.return_value = self.child

    def wait_for(self, condition):
        deadline = time.monotonic() + 10
        while not condition() and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertTrue(condition(), "Tk Godot preparation/monitor did not finish")

    def invocation(self):
        return GodotInvocation(("godot.exe", "--", "--content-root", str(self.manifest.root)), self.manifest)

    def start(self, future):
        self.launcher.prepare_godot_async.return_value = future
        self.window.godot_button.invoke()


class GodotMainWindowTests(WindowFixture, unittest.TestCase):
    def test_blocked_worker_keeps_tk_responsive_and_completion_launches_once_on_main_thread(self):
        from engine import godot_runner

        entered, release = Event(), Event()
        owner = get_ident()
        seen_threads = []
        self.window.status.trace_add("write", lambda *_: seen_threads.append(get_ident()))

        def blocked(*args, **kwargs):
            self.assertNotEqual(get_ident(), owner)
            entered.set()
            self.assertTrue(release.wait(5))
            return self.invocation()

        real = ProcessLauncher(self.manifest)
        self.launcher.prepare_godot_async.side_effect = real.prepare_godot_async
        self.launcher.launch_prepared_godot.side_effect = lambda invocation: (seen_threads.append(get_ident()) or self.child)
        with patch.object(godot_runner, "prepare_godot_invocation", side_effect=blocked), \
                patch("engine.process_launcher.subprocess.Popen") as popen, \
                patch("engine.main_window.messagebox.showerror") as error:
            self.window.godot_button.invoke()
            try:
                self.assertTrue(entered.wait(2))
                future = self.window._godot_preparation
                with patch.object(future, "result", wraps=future.result) as result:
                    ticked = []
                    self.root.after(180, lambda: ticked.append(True))
                    self.wait_for(lambda: bool(ticked))
                    result.assert_not_called()
                self.window._launch_godot()
                self.window.godot_button.invoke()
                self.launcher.prepare_godot_async.assert_called_once_with()
                self.launcher.launch_prepared_godot.assert_not_called()
                self.assertIn("準備を確認", self.window.status.get())
                self.assertIn("disabled", self.window.godot_button.state())
            finally:
                release.set()
            self.wait_for(lambda: "が終了しました" in self.window.status.get())
            self.window._poll_godot_preparation(future, self.launcher, "古い要求")
            self.launcher.launch_prepared_godot.assert_called_once_with(self.invocation())
            self.assertNotIn("disabled", self.window.godot_button.state())
            self.assertIsNone(self.window._godot_preparation)
            self.assertIsNone(self.window._godot_poll_id)
            self.assertEqual(set(seen_threads), {owner})
            popen.assert_not_called()
            error.assert_not_called()

    def test_preparation_errors_restore_button_and_do_not_fall_back(self):
        for problem in (FileNotFoundError("Godot未設定"), RuntimeError("probe失敗"), SystemExit(3)):
            with self.subTest(problem=problem), patch("engine.main_window.messagebox.showerror") as error:
                future = Future()
                future.set_exception(problem)
                self.start(future)
                self.wait_for(lambda: error.called)
                self.assertIn(type(problem).__name__, error.call_args.args[1])
                self.assertIn("準備に失敗", self.window.status.get())
                self.assertNotIn("disabled", self.window.godot_button.state())
                self.assertIsNone(self.window._godot_preparation)
                self.launcher.launch_prepared_godot.assert_not_called()
                self.launcher.launch_game.assert_not_called()

    def test_immediate_request_error_and_spawn_failure_allow_retry(self):
        with patch("engine.main_window.messagebox.showerror") as error:
            self.launcher.prepare_godot_async.side_effect = RuntimeError("worker開始不可")
            self.window._launch_godot()
            self.assertIn("準備に失敗", self.window.status.get())
            self.assertIsNone(self.window._godot_poll_id)
            self.launcher.prepare_godot_async.side_effect = None
            self.launcher.launch_prepared_godot.side_effect = OSError("spawn不可")
            failed = Future()
            failed.set_result(self.invocation())
            self.start(failed)
            self.wait_for(lambda: error.call_count == 2)
            self.assertIn("起動に失敗", self.window.status.get())
            self.assertEqual(self.window._launch_poll_ids, set())
            self.launcher.launch_prepared_godot.side_effect = None
            retry = Future()
            retry.set_result(self.invocation())
            self.start(retry)
            self.wait_for(lambda: "が終了しました" in self.window.status.get())
            self.assertEqual(self.launcher.launch_prepared_godot.call_count, 2)
            self.launcher.launch_game.assert_not_called()

    def test_cancelled_request_restores_button_without_error(self):
        future = Future()
        self.start(future)
        future.cancel()
        with patch("engine.main_window.messagebox.showerror") as error:
            self.wait_for(lambda: "取り消しました" in self.window.status.get())
            self.assertNotIn("disabled", self.window.godot_button.state())
            self.launcher.launch_prepared_godot.assert_not_called()
            error.assert_not_called()

    def test_project_switch_discards_queued_running_and_completed_requests(self):
        for state in ("queued", "running", "completed"):
            with self.subTest(state=state):
                old_launcher = self.window.launcher = Mock(spec=ProcessLauncher)
                future = Future()
                if state != "queued":
                    future.set_running_or_notify_cancel()
                if state == "completed":
                    future.set_result(self.invocation())
                old_launcher.prepare_godot_async.return_value = future
                self.window._launch_godot()
                with tempfile.TemporaryDirectory() as directory:
                    manifest = ProjectCreator().create_project(Path(directory), "選択先")
                    self.window.open_project(manifest)
                self.assertIsNone(self.window._godot_preparation)
                self.assertIsNone(self.window._godot_poll_id)
                if state == "running":
                    future.set_result(self.invocation())
                self.window._poll_godot_preparation(future, old_launcher, "古い要求")
                old_launcher.launch_prepared_godot.assert_not_called()
                self.assertEqual(future.cancelled(), state == "queued")
                self.assertIn("プロジェクトを開きました", self.window.status.get())
                self.assertNotIn("disabled", self.window.godot_button.state())

    def test_reopening_same_project_discards_old_future_but_new_request_can_launch(self):
        old = Future()
        old.set_running_or_notify_cancel()
        self.start(old)
        self.window.open_project(self.manifest.root / "engine_project.json")
        new_launcher = self.window.launcher = Mock(spec=ProcessLauncher)
        new = Future()
        new_launcher.prepare_godot_async.return_value = new
        new_launcher.launch_prepared_godot.return_value = self.child
        self.window._launch_godot()
        old.set_result(self.invocation())
        self.window._poll_godot_preparation(old, self.launcher, "古い要求")
        self.assertIs(self.window._godot_preparation, new)
        self.assertIsNotNone(self.window._godot_poll_id)
        new.set_result(self.invocation())
        self.wait_for(lambda: "が終了しました" in self.window.status.get())
        self.launcher.launch_prepared_godot.assert_not_called()
        new_launcher.launch_prepared_godot.assert_called_once()

    def test_destroy_discards_worker_and_ignores_child_widget_destroy(self):
        future = Future()
        future.set_running_or_notify_cancel()
        self.start(future)
        frame = tk.Frame(self.root)
        frame.destroy()
        self.assertIs(self.window._godot_preparation, future)
        self.doCleanups()
        future.set_result(self.invocation())
        self.window._poll_godot_preparation(future, self.launcher, "閉じた要求")
        self.window._launch_godot()
        self.assertTrue(self.window._closed)
        self.assertIsNone(self.window._godot_poll_id)
        self.assertIsNone(self.window._godot_preparation)
        self.launcher.launch_prepared_godot.assert_not_called()

    def test_special_disables_godot_but_keeps_python_and_editors(self):
        self.window._set_project(replace(self.manifest, project_type="special"))
        launcher = self.window.launcher = Mock(spec=ProcessLauncher)
        launcher.launch_game.return_value = self.child
        launcher.launch_editor.return_value = self.child
        self.assertIn("disabled", self.window.godot_button.state())
        self.window.godot_button.invoke()
        with patch("engine.main_window.messagebox.showerror") as error:
            self.window._launch_godot()
            error.assert_called_once()
        launcher.prepare_godot_async.assert_not_called()
        self.window._launch_game()
        self.window._launch_editor(self.manifest.editors[0].id)
        launcher.launch_game.assert_called_once_with()
        launcher.launch_editor.assert_called_once_with(self.manifest.editors[0].id)

    def test_destroy_after_godot_launch_cancels_monitor_without_killing_child(self):
        future = Future()
        future.set_result(self.invocation())
        self.child.poll.return_value = None
        self.start(future)
        self.wait_for(lambda: "実行中" in self.window.status.get())
        self.assertTrue(self.window._launch_poll_ids)
        self.doCleanups()
        self.assertEqual(self.window._launch_poll_ids, set())
        self.child.process.terminate.assert_not_called()
        self.child.process.kill.assert_not_called()

    def test_running_godot_monitor_keeps_original_project_label_after_switch(self):
        future = Future()
        future.set_result(self.invocation())
        self.child.poll.return_value = None
        self.start(future)
        self.wait_for(lambda: "実行中" in self.window.status.get())
        self.window._set_project(replace(self.manifest, name="別の住処"))
        self.child.poll.return_value = 7
        self.child.log_tail.return_value = "日本語の初期化エラー"
        with patch("engine.main_window.messagebox.showerror") as error:
            self.wait_for(lambda: error.called)
            detail = error.call_args.args[1]
            self.assertIn(f"Godot版（{self.manifest.name}）", detail)
            self.assertNotIn("別の住処", detail)
            self.assertIn("終了コード: 7", detail)
            self.assertIn("godot-test.log", detail)
            self.assertIn("日本語の初期化エラー", detail)
        self.assertEqual(self.window._launch_poll_ids, set())
        self.child.process.terminate.assert_not_called()


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotMainWindowRuntimeTests(WindowFixture, unittest.TestCase):
    def test_real_godot_gui_pipeline_reports_success_and_japanese_failure(self):
        for invalid_image in (False, True):
            with self.subTest(invalid_image=invalid_image), tempfile.TemporaryDirectory(prefix="Tk Godot 日本語 ") as directory:
                root = Path(directory)
                for name in ("engine_project.json", "game_content.json", "characters.json", "room.json",
                             "placed_objects.json", "conversations.json", "events.json"):
                    shutil.copy2(ROOT / name, root / name)
                for name in ("assets", "objects"):
                    shutil.copytree(ROOT / name, root / name)
                definition = json.loads((root / "engine_project.json").read_text(encoding="utf-8"))
                for editor in definition["editors"]:
                    (root / editor["script"]).write_text("", encoding="utf-8")
                (root / definition["entrypoint"]).write_text("raise RuntimeError('Python gameplay must not run')\n", encoding="utf-8")
                if invalid_image:
                    path = root / "characters.json"
                    data = json.loads(path.read_text(encoding="utf-8"))
                    data["characters"][0]["image"] = "見つからない画像.png"
                    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                before = {path.name: path.read_bytes() for path in root.glob("*.json")}
                self.window.open_project(root / "engine_project.json")
                launcher = self.window.launcher
                prepare = launcher.prepare_godot_async
                launch = launcher.launch_prepared_godot
                children = []

                def capture(invocation):
                    child = launch(invocation)
                    children.append(child)
                    return child

                # Headless/fixed frames are injected only by this runtime test.
                # The production GUI always requests an interactive launch.
                with patch.object(launcher, "prepare_godot_async", side_effect=lambda: prepare(
                        executable=GODOT, headless=True, test_frames=180, seed=12345)), \
                        patch.object(launcher, "launch_prepared_godot", side_effect=capture), \
                        patch("engine.main_window.messagebox.showerror") as error:
                    try:
                        self.window.godot_button.invoke()
                        self.wait_for(lambda: "異常終了" in self.window.status.get() if invalid_image else "が終了しました" in self.window.status.get())
                        self.assertEqual(len(children), 1)
                        output = children[0].log_tail()
                        if invalid_image:
                            self.assertNotEqual(children[0].poll(), 0)
                            self.assertIn("Missing content: 見つからない画像.png", error.call_args.args[1])
                            self.assertIn(str(children[0].log_path), error.call_args.args[1])
                        else:
                            error.assert_not_called()
                            self.assertEqual(children[0].poll(), 0)
                            self.assertIn("GODOT_SMOKE_OK frames=180 ghosts=2", output)
                        self.assertNotIn("Python gameplay must not run", output)
                        self.assertNotIn("SCRIPT ERROR:", output)
                        self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)
                        self.assertNotIn("disabled", self.window.godot_button.state())
                    finally:
                        for child in children:
                            if child.poll() is None:
                                child.process.terminate()
                                child.process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
