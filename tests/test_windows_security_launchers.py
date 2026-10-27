from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import venv
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tools.context.script.select_files import load_mapping, select_files

ROOT = Path(__file__).resolve().parents[1]
LAUNCHERS = {
    "run_game.bat": "game.py",
    "run_engine.bat": "engine_app.py",
    "run_object_editor.bat": "object_editor.py",
    "run_editor.bat": "conversation_editor.py",
}
ENTRIES = dict(zip(LAUNCHERS, ("game", "engine", "object-editor", "conversation-editor")))
GATE = r'".venv\Scripts\python.exe" -I -B "tools\security\script\launch.py"'
FIXTURE = """import json, os, sys, time
from pathlib import Path
root = Path.cwd()
options = json.loads((root / "scenario.json").read_text())
phase = "pip" if Path(__file__).parent.name == "pip" else ("apply" if "--apply" in sys.argv else "check")
guard = root / "mutation-active"
if options.get("guard") and phase in ("apply", "pip"):
    try:
        fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        (root / "overlap").write_text("overlapping update")
        raise SystemExit(97)
with (root / "calls.jsonl").open("a", encoding="utf-8") as out:
    out.write(json.dumps(phase) + "\\n")
if options.get("guard") and phase in ("apply", "pip"):
    if phase == "apply" and not (root / "apply-ready").exists():
        (root / "apply-ready").write_text("ready")
        deadline = time.monotonic() + 30
        while not (root / "release-apply").exists() and time.monotonic() < deadline:
            time.sleep(.02)
    time.sleep(.1)
    os.close(fd)
    guard.unlink()
code = options.get(phase, 0)
if phase == "pip" and code == 0:
    for name in ("pygame", "PIL"):
        (Path(__file__).parent.parent / (name + ".py")).write_text("")
raise SystemExit(code)
"""


class LauncherContractTests(unittest.TestCase):
    def test_all_python_launchers_are_gated_without_global_fallback(self) -> None:
        for name, app in LAUNCHERS.items():
            with self.subTest(name=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn(GATE + " " + ENTRIES[name] + "\nif errorlevel 1 goto :error", source)
                self.assertIn(
                    '%PYTHON_CMD% -I -B "tools\\security\\script\\launch.py" ' + ENTRIES[name],
                    source,
                )
                self.assertNotIn("-m pip install", source)
                self.assertNotIn(app, source)
                self.assertLess(source.index("goto :existing_venv"), source.index("where py"))
                self.assertNotIn("--managed-runtime", source)
                self.assertNotIn("--trusted-host", source)
        editor = (ROOT / "run_editor.bat").read_text(encoding="utf-8")
        self.assertNotIn("where pyw", editor)
        self.assertNotIn("py conversation_editor.py", editor)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("py -m pip install", readme)
        self.assertIn("launch.py game", readme)
        self.assertIn("if ($LASTEXITCODE -ne 0) { throw", readme)

    def test_launcher_changes_select_the_security_contract(self) -> None:
        for name in LAUNCHERS:
            result = select_files([name], load_mapping())
            self.assertIn("tests/test_windows_security_launchers.py", result["tests"])
            self.assertIn("tools/security/script/bootstrap.py", result["related_files"])
            self.assertIn("tools/security/script/launch.py", result["related_files"])
            self.assertNotIn("game.py", result["related_files"])
            self.assertEqual(result["unmapped_files"], [])


@unittest.skipUnless(os.name == "nt", "Windows CMD integration; static contract runs everywhere")
class WindowsLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        scratch = ROOT / "tmp" / "launcher-security"
        scratch.mkdir(parents=True, exist_ok=True)
        cls.workspace = tempfile.TemporaryDirectory(prefix="launcher 日本語 空白 ", dir=scratch)
        cls.addClassCleanup(cls.cleanup_workspace, cls.workspace)
        cls.base = Path(cls.workspace.name)
        cls.template = cls.base / "template"
        venv.EnvBuilder(with_pip=False).create(cls.template)
        cls.other_cwd = cls.base / "unrelated"
        cls.other_cwd.mkdir()

    @staticmethod
    def cleanup_workspace(workspace: tempfile.TemporaryDirectory) -> None:
        # Windows scanners can briefly lock even unused venv activation scripts.
        path = Path(workspace.name).resolve()
        scratch = (ROOT / "tmp" / "launcher-security").resolve()
        if path == scratch or not path.is_relative_to(scratch):
            raise ValueError("fixture cleanup target must remain inside its scratch directory")
        for attempt in range(20):
            try:
                workspace.cleanup()
                return
            except OSError as error:
                if error.winerror not in (32, 33, 267) or attempt == 19:
                    raise
                time.sleep(0.1)

    @contextmanager
    def fixture_directory(self) -> Iterator[str]:
        workspace = tempfile.TemporaryDirectory(prefix="case ", dir=self.base)
        try:
            yield workspace.name
        finally:
            self.cleanup_workspace(workspace)

    def wait_for_app(self, marker: Path) -> None:
        # start/pythonw detaches; wait for this fixture PID before deleting its venv.
        deadline = time.monotonic() + 30
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(marker.exists(), "fixture application was not launched")
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, int(marker.read_text()))
        if handle:
            try:
                self.assertEqual(kernel.WaitForSingleObject(handle, 30_000), 0)
            finally:
                kernel.CloseHandle(handle)

    def run_case(
        self, name: str, app: str, options: dict, expected: list[str], success: bool
    ) -> None:
        with self.fixture_directory() as directory:
            project = Path(directory)
            shutil.copytree(self.template, project / ".venv")
            if options.get("missing_pythonw"):
                (project / ".venv" / "Scripts" / "pythonw.exe").unlink()
            shutil.copyfile(ROOT / name, project / name)
            site = project / ".venv" / "Lib" / "site-packages"
            (site / "pip").mkdir()
            (site / "pip" / "__main__.py").write_text(FIXTURE, encoding="utf-8")
            if options.get("deps", True):
                for module in ("pygame", "PIL"):
                    (site / (module + ".py")).write_text("")
            bootstrap = project / "tools" / "security" / "script" / "bootstrap.py"
            bootstrap.parent.mkdir(parents=True)
            shutil.copyfile(
                ROOT / "tools/security/script/launch.py", bootstrap.with_name("launch.py")
            )
            bootstrap.write_text(FIXTURE, encoding="utf-8")
            (project / "scenario.json").write_text(json.dumps(options), encoding="utf-8")
            (project / "requirements.txt").write_text("# fixture: no network\n")
            (project / app).write_text(
                "import os\nfrom pathlib import Path\n"
                'marker = Path(__file__).with_name("started")\n'
                'temporary = marker.with_suffix(".tmp")\n'
                "temporary.write_text(str(os.getpid()))\n"
                "temporary.replace(marker)\n"
            )
            environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
            environment.pop("PYTHONPATH", None)
            environment.pop("PYTHONHOME", None)
            environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
            result = subprocess.run(
                [os.environ["COMSPEC"], "/d", "/c", str(project / name)],
                cwd=self.other_cwd,
                env=environment,
                input="\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # CMD pause/errors use the system code page, not Python's UTF-8.
                timeout=90,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
            self.assertEqual(
                [json.loads(line) for line in (project / "calls.jsonl").read_text().splitlines()],
                expected,
            )
            marker = project / "started"
            if success:
                self.wait_for_app(marker)
            else:
                self.assertFalse(marker.exists())
            self.assertFalse((project / ".venv-setup.lock").exists())

    def test_real_cmd_success_and_fail_closed_paths(self) -> None:
        for name, app in LAUNCHERS.items():
            installed = (
                ["apply", "check"] if name == "run_editor.bat" else ["apply", "pip", "check"]
            )
            cases = [
                ({}, ["apply", "check"], True),
                ({"deps": False}, installed, True),
                ({"apply": 2, "deps": False}, ["apply"], False),
                ({"check": 2}, ["apply", "check"], False),
                ({"apply": 1, "deps": False}, ["apply"], False),
                ({"check": 1}, ["apply", "check"], False),
                ({"deps": False, "check": 1}, installed, False),
            ]
            if name != "run_editor.bat":
                cases.append(({"pip": 42, "deps": False}, ["apply", "pip"], False))
            if name != "run_game.bat":
                cases.append(({"missing_pythonw": True}, ["apply", "check"], False))
            for options, expected, success in cases:
                with self.subTest(launcher=name, options=options):
                    self.run_case(name, app, options, expected, success)

    def test_two_cmd_launchers_serialize_updates_and_release_on_failure(self) -> None:
        for fail in (False, True):
            with self.subTest(pip_failure=fail), self.fixture_directory() as directory:
                project = Path(directory)
                shutil.copytree(self.template, project / ".venv")
                bootstrap = project / "tools/security/script/bootstrap.py"
                bootstrap.parent.mkdir(parents=True)
                bootstrap.write_text(FIXTURE, encoding="utf-8")
                shutil.copyfile(
                    ROOT / "tools/security/script/launch.py", bootstrap.with_name("launch.py")
                )
                site = project / ".venv/Lib/site-packages/pip"
                site.mkdir()
                (site / "__main__.py").write_text(FIXTURE, encoding="utf-8")
                (project / "scenario.json").write_text(
                    json.dumps({"guard": True, "pip": 42 if fail else 0})
                )
                (project / "requirements.txt").write_text("# fixture only")
                processes = []
                logs = []
                try:
                    for name, app in (
                        ("run_game.bat", "game.py"),
                        ("run_object_editor.bat", "object_editor.py"),
                    ):
                        shutil.copyfile(ROOT / name, project / name)
                        (project / app).write_text(
                            "import os, time\nfrom pathlib import Path\n"
                            "marker=Path(__file__).with_suffix('.started')\n"
                            "temporary=marker.with_suffix('.tmp')\n"
                            "temporary.write_text(str(os.getpid()))\n"
                            "temporary.replace(marker)\n"
                            "if Path(__file__).name == 'game.py':\n"
                            "    other=Path(__file__).with_name('object_editor.started')\n"
                            "    deadline=time.monotonic()+20\n"
                            "    while not other.exists() and time.monotonic()<deadline:\n"
                            "        time.sleep(.02)\n"
                            "    if not other.exists(): raise SystemExit(96)\n"
                        )
                        log = (project / (name + ".log")).open("w", encoding="utf-8")
                        logs.append(log)
                        process = subprocess.Popen(
                            [os.environ["COMSPEC"], "/d", "/c", str(project / name)],
                            cwd=self.other_cwd,
                            stdin=subprocess.PIPE,
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        processes.append(process)
                        process.stdin.write(b"\n")
                        process.stdin.close()
                        target = (
                            project / "apply-ready"
                            if len(processes) == 1
                            else project / (name + ".log")
                        )
                        deadline = time.monotonic() + 30
                        while time.monotonic() < deadline:
                            if target.exists() and (
                                len(processes) == 1
                                or "Waiting for project setup" in target.read_text(errors="replace")
                            ):
                                break
                            time.sleep(0.02)
                        else:
                            self.fail("updater/contender did not reach the fixture barrier")
                    (project / "release-apply").write_text("go")
                    for process in processes:
                        self.assertEqual(process.wait(timeout=90), 1 if fail else 0)
                    if not fail:
                        for app in ("game.py", "object_editor.py"):
                            self.wait_for_app((project / app).with_suffix(".started"))
                    self.assertFalse((project / "overlap").exists())
                    self.assertFalse((project / ".venv-setup.lock").exists())
                    phases = [
                        json.loads(line)
                        for line in (project / "calls.jsonl").read_text().splitlines()
                    ]
                    self.assertEqual(phases.count("apply"), 2)
                    self.assertEqual(phases.count("pip"), 2 if fail else 1)
                    self.assertEqual(phases.count("check"), 0 if fail else 2)
                finally:
                    (project / "release-apply").write_text("go")
                    for process in processes:
                        if process.poll() is None:
                            process.terminate()
                        process.wait(timeout=10)
                    for log in logs:
                        log.close()


if __name__ == "__main__":
    unittest.main()
