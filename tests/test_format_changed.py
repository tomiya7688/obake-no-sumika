from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.quality.script.format_changed import changed_python_files, main

ROOT = Path(__file__).resolve().parents[1]
UGLY = "x = {  'a':1 }\n"
CLEAN = 'x = {"a": 1}\n'


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


class FormatChangedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-q", "-b", "base")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        shutil.copy(ROOT / "ruff.toml", self.repo / "ruff.toml")
        (self.repo / "old.py").write_text(UGLY, encoding="utf-8")
        (self.repo / "notes.md").write_text("x\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "checkout", "-q", "-b", "work-item")

    def write(self, name: str, text: str) -> None:
        (self.repo / name).write_text(text, encoding="utf-8")

    def run_main(self, *args: str) -> int:
        return main([*args, "--repo", str(self.repo)])

    def test_exactly_one_file_source_is_required(self) -> None:
        with self.assertRaises(ValueError):
            changed_python_files(self.repo)
        with self.assertRaises(ValueError):
            changed_python_files(self.repo, staged=True, paths=["old.py"])
        self.assertEqual(self.run_main("--staged", "old.py"), 2)

    def test_base_mode_selects_only_python_files_changed_on_the_branch(self) -> None:
        self.write("new.py", UGLY)
        self.write("notes.md", "y\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "change")
        self.assertEqual(changed_python_files(self.repo, base="base"), ["new.py"])
        self.assertEqual(self.run_main("--base", "base", "--check"), 1)
        # Untouched legacy files are not this work's responsibility.
        self.assertEqual((self.repo / "old.py").read_text(encoding="utf-8"), UGLY)

    def test_staged_mode_ignores_other_unstaged_edits(self) -> None:
        self.write("mine.py", UGLY)
        self.write("theirs.py", UGLY)
        git(self.repo, "add", "mine.py")
        self.assertEqual(self.run_main("--staged"), 0)
        self.assertEqual((self.repo / "mine.py").read_text(encoding="utf-8"), CLEAN)
        self.assertEqual((self.repo / "theirs.py").read_text(encoding="utf-8"), UGLY)
        self.assertEqual(self.run_main("--staged", "--check"), 0)

    def test_deleted_files_and_no_python_changes_are_fine(self) -> None:
        git(self.repo, "rm", "-q", "old.py")
        git(self.repo, "commit", "-q", "-m", "delete")
        self.assertEqual(changed_python_files(self.repo, base="base"), [])
        self.assertEqual(self.run_main("--base", "base", "--check"), 0)

    def test_explicit_paths_and_missing_files(self) -> None:
        self.assertEqual(self.run_main("old.py", "--check"), 1)
        self.assertEqual(self.run_main("missing.py"), 2)

    def test_cli_runs_from_another_directory(self) -> None:
        script = ROOT / "tools/quality/script/format_changed.py"
        result = subprocess.run(
            [sys.executable, str(script), "--repo", str(self.repo), "old.py", "--check"],
            cwd=tempfile.gettempdir(),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("ruff", result.stdout)


if __name__ == "__main__":
    unittest.main()
