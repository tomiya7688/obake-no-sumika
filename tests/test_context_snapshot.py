from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.context.script.snapshot import collect_snapshot, diff_metadata

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/context/script/snapshot.py"


class ContextSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "work")
        self.git("config", "user.name", "Snapshot Test")
        self.git("config", "user.email", "snapshot@example.invalid")
        self.write("tracked.txt", "base\n")
        self.write("delete.txt", "remove\n")
        self.write(".gitignore", "ignored/\n")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=self.repo, capture_output=True,
                                encoding="utf-8", errors="replace")
        if result.returncode:
            self.fail(result.stderr)
        return result.stdout

    def write(self, path: str, data: str) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data, encoding="utf-8")

    def commit(self, subject: str) -> None:
        self.git("add", "--all")
        self.git("commit", "-m", subject)

    def test_clean_snapshot_has_no_base_or_patch(self) -> None:
        result = collect_snapshot(self.repo)
        self.assertEqual(result["branch"], "work")
        self.assertEqual(result["head"], self.base)
        for section in ("working", "staged", "untracked"):
            self.assertEqual(result[section]["total"], 0)
        self.assertEqual(result["recent_commits"]["total"], 1)
        self.assertNotIn("base", result)

    def test_working_staged_and_untracked_are_separate_and_read_only(self) -> None:
        self.write("tracked.txt", "base\nstaged\n")
        self.git("add", "tracked.txt")
        self.write("tracked.txt", "base\nstaged\nSECRET_CONTENT_NOT_EMITTED\n")
        self.write("new 日本語 name.txt", "SECRET_CONTENT_NOT_EMITTED\n")
        self.write("ignored/secret.txt", "secret\n")
        self.git("rm", "delete.txt")
        self.git("mv", "tracked.txt", "renamed 日本語.txt")
        # Keep a path modified both in the index and worktree as well.
        self.write("both.txt", "staged\n")
        self.git("add", "both.txt")
        self.write("both.txt", "staged\nworking\n")
        before_index = (self.repo / ".git/index").read_bytes()
        before_head = self.git("rev-parse", "HEAD")
        before_refs = self.git("show-ref")
        before_files = {str(p.relative_to(self.repo)): p.read_bytes()
                        for p in self.repo.rglob("*") if p.is_file() and ".git" not in p.parts}
        result = collect_snapshot(self.repo)
        self.assertEqual((self.repo / ".git/index").read_bytes(), before_index)
        self.assertEqual(self.git("rev-parse", "HEAD"), before_head)
        self.assertEqual(self.git("show-ref"), before_refs)
        self.assertEqual({str(p.relative_to(self.repo)): p.read_bytes()
                          for p in self.repo.rglob("*") if p.is_file() and ".git" not in p.parts}, before_files)
        working = {item["path"]: item for item in result["working"]["items"]}
        staged = {item["path"]: item for item in result["staged"]["items"]}
        self.assertEqual(working["both.txt"]["added"], "1")
        self.assertEqual(staged["both.txt"]["statuses"], ["A"])
        self.assertEqual(staged["delete.txt"]["statuses"], ["D"])
        self.assertIn("renamed 日本語.txt", staged)
        self.assertEqual(result["untracked"]["items"], ["new 日本語 name.txt"])
        self.assertNotIn("SECRET_CONTENT_NOT_EMITTED", json.dumps(result))

    def test_nul_parsing_preserves_tabs_newlines_and_conflict_statuses(self) -> None:
        # These POSIX-valid filenames cannot be created on Windows.
        path = "日本語\tline\nname.txt"
        encoded = path.encode("utf-8")
        with patch("tools.context.script.snapshot.run_git", side_effect=[
            b"U\0" + encoded + b"\0M\0" + encoded + b"\0",
            b"0\t0\t" + encoded + b"\x001\t2\t" + encoded + b"\0",
        ]) as run:
            result = diff_metadata(self.repo, [], 20)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"], [{"path": path, "statuses": ["U", "M"], "added": "1", "deleted": "2"}])
        self.assertEqual(result["summary"]["deleted_lines"], 2)
        self.assertTrue(all(call.args[1] == "--no-optional-locks" for call in run.call_args_list))

    def test_limits_report_full_totals_and_omissions(self) -> None:
        for index in range(4):
            self.write(f"file{index}.txt", "line\n")
        self.commit("four files")
        for index in range(4):
            self.write(f"file{index}.txt", "line\nnew\n")
            self.write(f"untracked{index}.txt", "new\n")
        result = collect_snapshot(self.repo, self.base, limit=2, commits=1)
        for name in ("working", "untracked"):
            self.assertEqual(result[name]["total"], 4)
            self.assertEqual(result[name]["omitted"], 2)
            self.assertEqual(len(result[name]["items"]), 2)
        self.assertEqual(result["working"]["summary"]["added_lines"], 4)
        self.assertEqual(result["recent_commits"]["total"], 2)
        self.assertEqual(result["recent_commits"]["omitted"], 1)
        self.assertEqual(result["base"]["changes"]["omitted"], 2)

    def test_base_files_use_merge_base_and_commits_use_two_dot(self) -> None:
        self.git("checkout", "-b", "other")
        self.write("other-only.txt", "other\n")
        self.commit("other subject")
        other = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "work")
        self.write("work-only.txt", "work\n")
        self.commit("work subject")
        result = collect_snapshot(self.repo, "other")
        base = result["base"]
        self.assertEqual(base["commit"], other)
        self.assertEqual(base["merge_base"], self.base)
        self.assertEqual([item["path"] for item in base["changes"]["items"]], ["work-only.txt"])
        self.assertEqual(base["commits"]["total"], 1)
        self.assertTrue(base["commits"]["items"][0].endswith("work subject"))
        self.git("checkout", "--orphan", "unrelated")
        self.git("commit", "-m", "unrelated root")
        with self.assertRaises(ValueError):
            collect_snapshot(self.repo, "other")

    def test_binary_counts_and_detached_head(self) -> None:
        (self.repo / "binary.dat").write_bytes(b"\0binary")
        self.commit("binary")
        (self.repo / "binary.dat").write_bytes(b"\0changed")
        self.git("checkout", "--detach", "HEAD")
        result = collect_snapshot(self.repo)
        self.assertIsNone(result["branch"])
        self.assertEqual(result["working"]["summary"]["binary_files"], 1)
        self.assertEqual(result["working"]["items"][0]["added"], "-")

    def test_bad_limits_refs_and_missing_history_fail(self) -> None:
        for limit, commits in ((0, 8), (20, 0), (-1, 1)):
            with self.subTest(limit=limit, commits=commits), self.assertRaises(ValueError):
                collect_snapshot(self.repo, limit=limit, commits=commits)
        for base in ("-h", "missing-ref", ""):
            with self.subTest(base=base), self.assertRaises(ValueError):
                collect_snapshot(self.repo, base)
        outside = self.repo.parent / "outside"
        outside.mkdir()
        with self.assertRaises(ValueError):
            collect_snapshot(outside)
        self.repo = outside
        self.git("init", "-b", "work")
        with self.assertRaises(ValueError):
            collect_snapshot(outside)

    def test_cli_json_human_and_failure_from_other_directory(self) -> None:
        def run(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.repo), *args],
                                  cwd=self.repo.parent, capture_output=True, encoding="utf-8")
        result = run("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["head"], self.base)
        self.assertIn("working: 0 entries", run().stdout)
        for args in (("--base", "missing"), ("--limit", "0"), ("--commits", "0")):
            result = run("--json", *args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
