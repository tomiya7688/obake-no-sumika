from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from tools.repo_sync.script.inventory import DEFAULT_PLAN, inspect_inventory, load_plan, validate_plan
from tests.test_repo_sync import run_git


class InventorySchemaTests(unittest.TestCase):
    def test_repository_plan_covers_23_commits_without_claiming_release_approval(self):
        plan = load_plan(DEFAULT_PLAN)
        self.assertEqual(len(plan["commits"]), 23)
        self.assertEqual(plan["status"], "proposal")
        self.assertEqual(plan["groups"]["shared_art"]["decision"], "port")
        self.assertEqual(plan["groups"]["pixel_scaling"]["decision"], "port")
        self.assertEqual(plan["groups"]["python_game_performance"]["decision"], "reference_only")

    def test_malformed_schema_decisions_and_commit_links_are_rejected(self):
        source = load_plan(DEFAULT_PLAN)
        sha = next(iter(source["commits"]))
        mutations = [
            lambda p: p.update(schema_version=True),
            lambda p: p.update(status="approved"),
            lambda p: p["snapshots"].update(main="HEAD"),
            lambda p: p["groups"]["shared_art"].update(decision=[]),
            lambda p: p["groups"]["shared_art"].update(verification=""),
            lambda p: p["commits"].update({sha: ["missing"]}),
            lambda p: p["commits"].update({sha: ["context_policy", "context_policy"]}),
            lambda p: p["groups"].update(unused=deepcopy(p["groups"]["shared_art"])),
        ]
        for change in mutations:
            plan = deepcopy(source)
            change(plan)
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_duplicate_json_keys_are_not_silently_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate inventory key"):
                load_plan(path)


class IntegrationInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        run_git(self.repo, "init", "-q", "--initial-branch=main")
        run_git(self.repo, "config", "user.name", "Inventory Test")
        run_git(self.repo, "config", "user.email", "test@example.invalid")
        self.common = self.commit("base.txt", "common")
        self.first = self.commit("main.txt", "main one")
        self.second = self.commit("main.txt", "main two 日本語")
        run_git(self.repo, "update-ref", "refs/remotes/origin/main", self.second)
        run_git(self.repo, "switch", "-qc", "work", self.common)
        self.work = self.commit("work.txt", "work one")
        run_git(self.repo, "update-ref", "refs/remotes/origin/work", self.work)
        self.plan = {
            "schema_version": 1, "status": "proposal",
            "snapshots": {"main": self.second, "work": self.work, "merge_base": self.common},
            "groups": {"fixture": {"decision": "port", "summary": "Keep both changes",
                                   "source_paths": ["main.txt"], "work_targets": ["main.txt"],
                                   "verification": "Fixture only; not a release approval"}},
            "commits": {self.first: ["fixture"], self.second: ["fixture"]},
        }

    def commit(self, name, content):
        (self.repo / name).write_text(content, encoding="utf-8")
        run_git(self.repo, "add", "--", name)
        run_git(self.repo, "commit", "-qm", content)
        return run_git(self.repo, "rev-parse", "HEAD")

    def test_read_only_report_preserves_dirty_staged_untracked_and_plan(self):
        (self.repo / "base.txt").write_text("staged", encoding="utf-8")
        run_git(self.repo, "add", "base.txt")
        (self.repo / "work.txt").write_text("unstaged", encoding="utf-8")
        (self.repo / "untracked.txt").write_text("keep", encoding="utf-8")
        before_status = run_git(self.repo, "status", "--porcelain=v1")
        before_index = (self.repo / ".git" / "index").read_bytes()
        before_plan = deepcopy(self.plan)
        report = inspect_inventory(self.repo, self.plan)
        self.assertEqual(report["status"], "consistent")
        self.assertEqual((report["work_only_count"], report["main_only_count"]), (1, 2))
        self.assertEqual(report["commits"][1]["subject"], "main two 日本語")
        self.assertFalse(report["fetched"])
        self.assertTrue(report["proposal_only"])
        self.assertEqual((self.repo / ".git" / "index").read_bytes(), before_index)
        self.assertEqual(run_git(self.repo, "status", "--porcelain=v1"), before_status)
        self.assertEqual(run_git(self.repo, "rev-parse", "HEAD"), self.work)
        self.assertEqual(self.plan, before_plan)
        self.assertEqual((self.repo / "untracked.txt").read_text(encoding="utf-8"), "keep")

    def test_ordinary_work_advance_does_not_invalidate_main_only_inventory(self):
        updated = self.commit("work.txt", "work two")
        run_git(self.repo, "update-ref", "refs/remotes/origin/work", updated)
        report = inspect_inventory(self.repo, self.plan)
        self.assertEqual(report["status"], "consistent")
        self.assertEqual(report["work_only_count"], 2)

    def test_new_main_commit_requires_refresh_and_exposes_unclassified_sha(self):
        run_git(self.repo, "switch", "-q", "main")
        added = self.commit("main.txt", "main three")
        run_git(self.repo, "update-ref", "refs/remotes/origin/main", added)
        report = inspect_inventory(self.repo, self.plan)
        self.assertEqual(report["status"], "needs_refresh")
        self.assertEqual(report["unclassified"], [added])
        self.assertIn("main snapshot changed", report["issues"])

    def test_partial_main_merge_requires_reclassification_not_silent_completion(self):
        run_git(self.repo, "merge", "--no-ff", "-qm", "partially integrate", self.first)
        run_git(self.repo, "update-ref", "refs/remotes/origin/work", "HEAD")
        report = inspect_inventory(self.repo, self.plan)
        self.assertEqual(report["status"], "needs_refresh")
        self.assertEqual(report["no_longer_main_only"], [self.first])
        self.assertIn("live merge base changed", report["issues"])

    def test_omitted_and_excess_pinned_commits_are_both_detected(self):
        del self.plan["commits"][self.first]
        self.plan["commits"][self.common] = ["fixture"]
        report = inspect_inventory(self.repo, self.plan)
        self.assertEqual(report["baseline_unclassified"], [self.first])
        self.assertEqual(report["baseline_excess"], [self.common])
        self.assertEqual(report["status"], "needs_refresh")

    def test_rewound_work_and_wrong_pinned_base_are_detected(self):
        run_git(self.repo, "update-ref", "refs/remotes/origin/work", self.common)
        self.plan["snapshots"]["merge_base"] = self.first
        report = inspect_inventory(self.repo, self.plan)
        self.assertIn("work no longer descends from snapshot", report["issues"])
        self.assertIn("pinned merge base mismatch", report["issues"])

    def test_missing_pinned_object_and_option_like_ref_are_errors(self):
        with self.assertRaises(ValueError):
            inspect_inventory(self.repo, self.plan, main_ref="--all")
        self.plan["snapshots"]["work"] = "f" * 40
        with self.assertRaises(ValueError):
            inspect_inventory(self.repo, self.plan)

    def test_cli_json_from_other_cwd_and_stale_exit_code(self):
        path = self.repo / "plan.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        command = [sys.executable, str(ROOT / "tools/repo_sync/script/inventory.py"),
                   "--repo", str(self.repo), "--plan", str(path), "--json"]
        result = subprocess.run(command, cwd=self.repo, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "consistent")
        del self.plan["commits"][self.first]
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        result = subprocess.run(command, cwd=self.repo, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["unclassified"], [self.first])


if __name__ == "__main__":
    unittest.main()
