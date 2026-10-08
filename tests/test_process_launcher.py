from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher


ROOT = Path(__file__).resolve().parents[1]


class ProcessLauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.script = self.root / "child.py"
        self.manifest = replace(load_project_manifest(ROOT / "engine_project.json"),
                                root=self.root, entrypoint=self.script)
        self.launcher = ProcessLauncher(self.manifest)
        self.children = []

    def tearDown(self):
        for child in self.children:
            if child.poll() is None:
                child.process.terminate()
            child.process.wait(timeout=10)
        self.directory.cleanup()

    def launch(self, source):
        self.script.write_text(source, encoding="utf-8")
        child = self.launcher.launch_game()
        self.children.append(child)
        return child

    def test_captures_stdout_stderr_and_japanese_traceback(self):
        child = self.launch("import sys\nprint('標準出力')\nprint('標準エラー', file=sys.stderr)\nraise RuntimeError('原因が見える')\n")
        self.assertEqual(child.process.wait(timeout=10), 1)
        self.assertEqual(child.poll(), 1)
        log = child.log_tail()
        self.assertIn("標準出力", log)
        self.assertIn("標準エラー", log)
        self.assertIn("RuntimeError: 原因が見える", log)
        self.assertEqual(child.log_path.parent, self.root / "tmp" / "launch_logs")

    def test_large_output_does_not_block_and_tail_is_bounded(self):
        child = self.launch("print('x' * 2_000_000)\nprint('last line')\n")
        self.assertEqual(child.process.wait(timeout=10), 0)
        self.assertGreater(child.log_path.stat().st_size, 2_000_000)
        tail = child.log_tail()
        self.assertLessEqual(len(tail.encode("utf-8")), 8192)
        self.assertTrue(tail.rstrip().endswith("last line"))

    def test_launch_returns_without_waiting_for_child(self):
        start = time.monotonic()
        child = self.launch("import time\ntime.sleep(60)\n")
        self.assertLess(time.monotonic() - start, 5)
        self.assertIsNone(child.poll())

    def test_each_launch_has_a_unique_persistent_log(self):
        self.script.write_text("print('done')\n", encoding="utf-8")
        first = self.launcher.launch_game()
        second = self.launcher.launch_game()
        self.children.extend((first, second))
        self.assertNotEqual(first.log_path, second.log_path)
        for child in self.children:
            self.assertEqual(child.process.wait(timeout=10), 0)
            self.assertIn("done", child.log_tail())

    def test_pythonw_uses_console_sibling_and_hidden_output_capture(self):
        console_python = Path(sys.executable).with_name("python.exe")
        pythonw = console_python.with_name("pythonw.exe")
        with patch("engine.process_launcher.sys.executable", str(pythonw)), \
                patch("engine.process_launcher.Path.is_file", return_value=True), \
                patch("engine.process_launcher.subprocess.Popen") as popen:
            child = self.launcher.launch_game()
        self.assertEqual(popen.call_args.args[0][0], str(console_python))
        kwargs = popen.call_args.kwargs
        self.assertEqual(kwargs["cwd"], self.root)
        self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["env"]["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(kwargs["env"]["PYTHONUNBUFFERED"], "1")
        self.assertEqual(kwargs["creationflags"], subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.assertTrue(kwargs["stdout"].closed)
        self.assertTrue(child.log_path.is_file())

    def test_spawn_failure_does_not_leak_parent_log_handle(self):
        with patch("engine.process_launcher.subprocess.Popen", side_effect=OSError("cannot spawn")) as popen:
            with self.assertRaisesRegex(OSError, "cannot spawn"):
                self.launcher.launch_game()
        self.assertTrue(popen.call_args.kwargs["stdout"].closed)


if __name__ == "__main__":
    unittest.main()
