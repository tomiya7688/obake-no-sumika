from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.diff_summary.script.summarize import summarize


ROOT = Path(__file__).resolve().parents[1]


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


class DiffSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.name", "Test")
        run_git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "game.py").write_text("def old():\n    return 1\n", encoding="utf-8")
        run_git(self.repo, "add", "game.py")
        run_git(self.repo, "commit", "-qm", "old behavior")
        self.base = run_git(self.repo, "rev-parse", "HEAD")
        (self.repo / "game.py").write_text("def new():\n    return 2\n", encoding="utf-8")
        (self.repo / "notes.txt").write_text("new file\n", encoding="utf-8")
        run_git(self.repo, "add", "game.py", "notes.txt")
        run_git(self.repo, "commit", "-qm", "new behavior")

    def test_summary_contains_responsibility_and_changed_definitions(self) -> None:
        report = summarize(self.repo, self.base, "HEAD")
        self.assertEqual(report["file_count"], 2)
        self.assertEqual(report["omitted_files"], 0)
        self.assertEqual(report["summary"]["statuses"], {"M": 1, "A": 1})
        self.assertEqual(report["summary"]["added_lines"], 3)
        game = next(item for item in report["files"] if item["path"] == "game.py")
        self.assertEqual(game["status"], "M")
        self.assertEqual(game["changed_definitions"], ["- def old", "+ def new"])
        self.assertIn("docs/context/game.md", game["contexts"])
        self.assertIn("tests/test_tagged_conversations.py", game["tests"])
        notes = next(item for item in report["files"] if item["path"] == "notes.txt")
        self.assertTrue(notes["unmapped"])
        self.assertIn("new behavior", report["commits"][0])

    def test_file_limit_and_bad_revision(self) -> None:
        report = summarize(self.repo, self.base, "HEAD", max_files=1)
        self.assertEqual(len(report["files"]), 1)
        self.assertEqual(report["omitted_files"], 1)
        with self.assertRaises(ValueError):
            summarize(self.repo, "--bad", "HEAD")
        with self.assertRaises(ValueError):
            summarize(self.repo, self.base, "HEAD", max_files=0)

    def test_equal_revisions_have_empty_summary(self) -> None:
        report = summarize(self.repo, "HEAD", "HEAD")
        self.assertEqual(report["file_count"], 0)
        self.assertEqual(report["summary"]["added_lines"], 0)
        self.assertEqual(report["files"], [])

    def test_json_cli_does_not_modify_repository(self) -> None:
        before = run_git(self.repo, "status", "--porcelain")
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/diff_summary/script/summarize.py"),
             "--repo", str(self.repo), "--base", self.base, "--json"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout)["file_count"], 2)
        self.assertEqual(run_git(self.repo, "status", "--porcelain"), before)

    def test_text_cli_shows_context_without_full_patch(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/diff_summary/script/summarize.py"),
             "--repo", str(self.repo), "--base", self.base],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        self.assertIn("docs/context/game.md", result.stdout)
        self.assertIn("+ def new", result.stdout)
        self.assertNotIn("return 2", result.stdout)


if __name__ == "__main__":
    unittest.main()
