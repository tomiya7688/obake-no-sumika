from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.repo_sync.script.report import inspect


ROOT = Path(__file__).resolve().parents[1]


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )
    if result.returncode:
        raise AssertionError(f"git {' '.join(args)}: {result.stderr}")
    return result.stdout.strip()


class RepoSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.local = root / "local"
        self.local.mkdir()
        self.remote = root / "remote.git"
        run_git(root, "init", "--bare", "-q", "--initial-branch=work", str(self.remote))
        run_git(self.local, "init", "-q", "--initial-branch=work")
        for repo in (self.local,):
            run_git(repo, "config", "user.name", "Test")
            run_git(repo, "config", "user.email", "test@example.invalid")
        (self.local / "game.py").write_text("def original():\n    return 1\n", encoding="utf-8")
        run_git(self.local, "add", "game.py")
        run_git(self.local, "commit", "-qm", "initial")
        run_git(self.local, "remote", "add", "origin", str(self.remote))
        run_git(self.local, "push", "-qu", "origin", "work")
        self.initial = run_git(self.local, "rev-parse", "HEAD")
        self.other = root / "other"
        run_git(root, "clone", "-q", "-b", "work", str(self.remote), str(self.other))
        run_git(self.other, "config", "user.name", "Other")
        run_git(self.other, "config", "user.email", "other@example.invalid")
        (self.other / "game.py").write_text("def remote_change():\n    return 2\n", encoding="utf-8")
        run_git(self.other, "add", "game.py")
        run_git(self.other, "commit", "-qm", "remote change")
        run_git(self.other, "push", "-q", "origin", "work")

    def test_fetch_reports_remote_change_without_merging(self) -> None:
        stale = inspect(self.local)
        self.assertEqual(stale["state"], "up_to_date")
        report = inspect(self.local, fetch=True)
        self.assertEqual(report["state"], "behind")
        self.assertEqual((report["ahead"], report["behind"]), (0, 1))
        self.assertTrue(report["fast_forward_safe"])
        self.assertEqual(report["remote_changes"]["files"][0]["path"], "game.py")
        self.assertEqual(run_git(self.local, "rev-parse", "HEAD"), self.initial)
        self.assertEqual(run_git(self.local, "status", "--porcelain"), "")

    def test_dirty_and_diverged_are_not_safe_to_fast_forward(self) -> None:
        inspect(self.local, fetch=True)
        (self.local / "notes.txt").write_text("uncommitted\n", encoding="utf-8")
        dirty = inspect(self.local)
        self.assertTrue(dirty["dirty_worktree"])
        self.assertFalse(dirty["fast_forward_safe"])
        (self.local / "notes.txt").write_text("local commit\n", encoding="utf-8")
        run_git(self.local, "add", "notes.txt")
        run_git(self.local, "commit", "-qm", "local change")
        diverged = inspect(self.local)
        self.assertEqual(diverged["state"], "diverged")
        self.assertEqual((diverged["ahead"], diverged["behind"]), (1, 1))
        self.assertFalse(diverged["fast_forward_safe"])

    def test_cli_json_and_invalid_remote(self) -> None:
        with self.assertRaises(ValueError):
            inspect(self.local, remote="--evil")
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/repo_sync/script/report.py"),
             "--repo", str(self.local), "--fetch", "--json"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout)["state"], "behind")


if __name__ == "__main__":
    unittest.main()
