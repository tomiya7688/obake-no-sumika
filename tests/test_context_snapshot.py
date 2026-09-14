from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import context_snapshot


class ContextSnapshotTests(unittest.TestCase):
    def test_limited_lines_marks_hidden_lines(self) -> None:
        self.assertEqual(
            context_snapshot.limited_lines("a\nb\nc", 2),
            ["a", "b", "... +1 more"],
        )

    def test_collect_snapshot_without_base_skips_base_sections(self) -> None:
        with patch.object(context_snapshot, "run_git", return_value=(0, "ok")):
            snapshot = context_snapshot.collect_snapshot(None, limit=10, commits=3)

        self.assertIn("branch", snapshot)
        self.assertIn("working_files", snapshot)
        self.assertNotIn("base_files", snapshot)

    def test_collect_snapshot_with_base_uses_bounded_delta(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_run_git(*args: str) -> tuple[int, str]:
            calls.append(args)
            return 0, "ok"

        with patch.object(context_snapshot, "run_git", side_effect=fake_run_git):
            snapshot = context_snapshot.collect_snapshot("origin/main", limit=10, commits=3)

        self.assertEqual(snapshot["base"], "origin/main")
        self.assertIn(
            ("diff", "--name-status", "origin/main...HEAD"),
            calls,
        )
        self.assertIn(
            ("log", "--oneline", "origin/main..HEAD", "-3"),
            calls,
        )


if __name__ == "__main__":
    unittest.main()
