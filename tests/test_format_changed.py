from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.quality.script.format_changed import SelectionError, changed_python_files, main

ROOT = Path(__file__).resolve().parents[1]
UGLY = "x = {  'a':1 }\n"
CLEAN = 'x = {"a": 1}\n'

# Keep the temporary repositories independent of the caller: no inherited
# GIT_DIR/GIT_INDEX_FILE (e.g. from a hook) and no global signing or hooks.
GIT_ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
GIT_ENV.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=", *args],
        cwd=repo,
        env=GIT_ENV,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")


class FormatChangedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        git(self.repo, "init", "-q", "-b", "base")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        shutil.copy(ROOT / "ruff.toml", self.repo / "ruff.toml")
        self.write("old.py", UGLY)
        self.write("notes.md", "x\n")
        self.commit_all("base")
        git(self.repo, "checkout", "-q", "-b", "work-item")
        # main() runs git in-process; isolate it the same way and restore the
        # caller's environment (including any original values) afterwards.
        isolated = mock.patch.dict(os.environ, GIT_ENV, clear=True)
        isolated.start()
        self.addCleanup(isolated.stop)

    def write(self, name: str, text: str) -> None:
        (self.repo / name).write_text(text, encoding="utf-8")

    def read(self, name: str) -> str:
        return (self.repo / name).read_text(encoding="utf-8")

    def commit_all(self, message: str) -> None:
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", message)

    def run_main(self, *args: str) -> int:
        return main([*args, "--repo", str(self.repo)])

    def test_exactly_one_file_source_is_required(self) -> None:
        with self.assertRaises(ValueError):
            changed_python_files(self.repo)
        with self.assertRaises(ValueError):
            changed_python_files(self.repo, staged=True, paths=["old.py"])
        self.assertEqual(self.run_main("--staged", "old.py"), 2)

    def test_base_mode_uses_the_merge_base_and_only_python_files(self) -> None:
        self.write("new.py", UGLY)
        self.write("notes.md", "y\n")
        self.write("old.py", UGLY + "y = 1\n")
        self.commit_all("change")
        # The base moves on after branching; its files are not this work's.
        git(self.repo, "checkout", "-q", "base")
        self.write("theirs.py", UGLY)
        self.commit_all("other work")
        git(self.repo, "checkout", "-q", "work-item")
        self.assertEqual(changed_python_files(self.repo, base="base"), ["new.py", "old.py"])
        self.assertEqual(self.run_main("--base", "base", "--check"), 1)
        self.assertEqual(self.read("new.py"), UGLY)

    def test_base_mode_refuses_files_with_uncommitted_edits(self) -> None:
        self.write("new.py", UGLY)
        self.commit_all("change")
        self.write("new.py", UGLY + "someone_else = 1\n")
        with self.assertRaises(SelectionError):
            changed_python_files(self.repo, base="base")
        self.assertEqual(self.run_main("--base", "base"), 2)
        self.assertEqual(self.read("new.py"), UGLY + "someone_else = 1\n")

    def test_staged_mode_ignores_other_unstaged_files(self) -> None:
        self.write("mine.py", UGLY)
        self.write("theirs.py", UGLY)
        git(self.repo, "add", "mine.py")
        self.assertEqual(self.run_main("--staged"), 0)
        self.assertEqual(self.read("mine.py"), CLEAN)
        self.assertEqual(self.read("theirs.py"), UGLY)
        # The formatting is now an unstaged edit: checking refuses until re-added,
        # so the check always describes what will be committed.
        self.assertEqual(self.run_main("--staged", "--check"), 2)
        git(self.repo, "add", "mine.py")
        self.assertEqual(self.run_main("--staged", "--check"), 0)

    def test_staged_mode_refuses_a_file_mixing_staged_and_unstaged_edits(self) -> None:
        self.write("old.py", UGLY + "mine = 1\n")
        git(self.repo, "add", "old.py")
        self.write("old.py", UGLY + "mine = 1\nother = {  'b':2 }\n")
        self.assertEqual(self.run_main("--staged"), 2)
        self.assertEqual(self.run_main("--staged", "--check"), 2)
        self.assertEqual(self.read("old.py"), UGLY + "mine = 1\nother = {  'b':2 }\n")

    def test_deleted_files_and_no_python_changes_are_fine(self) -> None:
        git(self.repo, "rm", "-q", "old.py")
        git(self.repo, "commit", "-q", "-m", "delete")
        self.assertEqual(changed_python_files(self.repo, base="base"), [])
        self.assertEqual(self.run_main("--base", "base", "--check"), 0)

    def test_explicit_paths_must_be_existing_files_inside_the_repository(self) -> None:
        self.assertEqual(self.run_main("old.py", "--check"), 1)
        self.assertEqual(self.read("old.py"), UGLY)
        self.assertEqual(self.run_main("missing.py"), 2)
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other).resolve() / "outside.py"
            outside.write_text(UGLY, encoding="utf-8")
            relative = Path("..") / outside.parent.name / outside.name
            # Next to the repository so "../<dir>/outside.py" resolves to a real file.
            sibling = self.repo.parent / outside.parent.name
            for path in (str(outside), str(relative)):
                with self.subTest(path=path):
                    self.assertEqual(self.run_main(path), 2)
            self.assertEqual(outside.read_text(encoding="utf-8"), UGLY)
            self.assertEqual(sibling, outside.parent)

    def test_missing_git_is_reported_not_raised(self) -> None:
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("git")):
            with self.assertRaisesRegex(SelectionError, "cannot run git"):
                changed_python_files(self.repo, staged=True)

    def test_unknown_base_reports_the_git_error(self) -> None:
        with self.assertRaisesRegex(SelectionError, "no-such-branch"):
            changed_python_files(self.repo, base="no-such-branch")

    def test_cli_runs_from_another_directory(self) -> None:
        script = ROOT / "tools/quality/script/format_changed.py"
        result = subprocess.run(
            [sys.executable, str(script), "--repo", str(self.repo), "old.py", "--check"],
            cwd=Path(self.temp.name).parent,
            env=GIT_ENV,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("check 1 file(s)", result.stdout)
        self.assertIn("old.py", result.stdout)


if __name__ == "__main__":
    unittest.main()
