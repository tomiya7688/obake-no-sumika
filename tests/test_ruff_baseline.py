from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.quality.script.check_ruff import (
    compare,
    load_baseline,
    records_to_set,
    run_command,
    run_ruff,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/quality/script/check_ruff.py"
KNOWN = {"path": "old.py", "code": "E402", "row": 3, "column": 1}


def baseline(records: list) -> dict:
    return {
        "schema_version": 1,
        "recorded_with": "ruff fixture",
        "tracking_issue": 86,
        "diagnostics": records,
    }


class RuffBaselineTests(unittest.TestCase):
    def test_exact_diagnostics_pass_but_same_count_replacement_fails(self) -> None:
        expected = records_to_set([KNOWN])
        self.assertEqual(compare(expected, expected)["status"], "pass")
        moved = records_to_set([{**KNOWN, "row": 4}])
        result = compare(moved, expected)
        self.assertEqual(result["status"], "fail")
        self.assertEqual((result["new_count"], result["stale_count"]), (1, 1))

    def test_fixed_entries_must_be_removed_and_new_errors_cannot_be_traded(self) -> None:
        expected = records_to_set([KNOWN])
        self.assertEqual(compare(set(), expected)["stale_count"], 1)
        actual = records_to_set([{**KNOWN, "code": "F821"}])
        self.assertEqual(compare(actual, expected)["new_count"], 1)

    def test_report_is_bounded_without_losing_totals(self) -> None:
        actual = records_to_set([{**KNOWN, "row": row} for row in range(1, 5)])
        result = compare(actual, set(), limit=2)
        self.assertEqual(
            (result["new_count"], len(result["new"]), result["omitted_new"]), (4, 2, 2)
        )
        with self.assertRaises(ValueError):
            compare(set(), set(), 0)

    def test_bad_schema_paths_locations_codes_and_duplicates_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            mutations = [
                {"schema_version": True},
                {"tracking_issue": 0},
                {"recorded_with": ""},
                {"diagnostics": [KNOWN, KNOWN]},
                {"diagnostics": None},
            ]
            mutations.extend(
                {"diagnostics": [{**KNOWN, key: value}]}
                for key, value in (
                    ("path", "../outside.py"),
                    ("path", "/outside.py"),
                    ("path", "C:/outside.py"),
                    ("path", "a//b.py"),
                    ("path", "a\\b.py"),
                    ("row", 0),
                    ("column", True),
                    ("code", "I001"),
                    ("code", "F821"),
                    ("code", "invalid-syntax"),
                )
            )
            for mutation in mutations:
                path.write_text(json.dumps({**baseline([KNOWN]), **mutation}), encoding="utf-8")
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    load_baseline(path)
            path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_baseline(path)

    def test_checker_failures_and_inconsistent_json_never_pass(self) -> None:
        version = subprocess.CompletedProcess([], 0, "ruff fixture\n", "")
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            item = {
                "filename": str(repo / "old.py"),
                "code": "I001",
                "location": {"row": 3, "column": 1},
            }
            failures = [
                (2, "", "bad config"),
                (0, json.dumps([item]), ""),
                (1, "[]", ""),
                (1, "not JSON", ""),
                (1, "{}", ""),
                (1, json.dumps([item, item]), ""),
                (1, json.dumps([{**item, "filename": str(repo.parent / "outside.py")}]), ""),
                (1, json.dumps([{**item, "code": "invalid-syntax"}]), ""),
            ]
            for code, stdout, stderr in failures:
                with (
                    self.subTest(code=code, stdout=stdout),
                    patch(
                        "tools.quality.script.check_ruff.run_command",
                        side_effect=[
                            version,
                            subprocess.CompletedProcess([], code, stdout, stderr),
                        ],
                    ),
                    self.assertRaises(ValueError),
                ):
                    run_ruff(repo)
            with patch(
                "tools.quality.script.check_ruff.run_command",
                return_value=subprocess.CompletedProcess([], 1, "", "No module named ruff"),
            ):
                with self.assertRaisesRegex(ValueError, "unavailable"):
                    run_ruff(repo)

    def test_checker_uses_venv_module_explicit_config_and_read_only_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            with patch(
                "tools.quality.script.check_ruff.run_command",
                side_effect=[
                    subprocess.CompletedProcess([], 0, "ruff fixture", ""),
                    subprocess.CompletedProcess([], 0, "[]", ""),
                ],
            ) as run:
                self.assertEqual(run_ruff(repo), ("ruff fixture", set()))
            args = run.call_args_list[1].args[1]
            for option in ("--no-fix", "--no-cache", "--no-respect-gitignore", "--config"):
                self.assertIn(option, args)
            self.assertIn(str(repo / "ruff.toml"), args)
            with patch("tools.quality.script.check_ruff.subprocess.run") as process:
                run_command(repo, ["--version"], timeout=10)
            self.assertEqual(process.call_args.args[0], [sys.executable, "-m", "ruff", "--version"])
            self.assertEqual(process.call_args.kwargs["timeout"], 10)

    def test_checker_timeout_propagates_instead_of_passing(self) -> None:
        with patch(
            "tools.quality.script.check_ruff.run_command",
            side_effect=subprocess.TimeoutExpired("ruff", 10),
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_ruff(ROOT)

    def test_committed_baseline_is_empty(self) -> None:
        expected = load_baseline(ROOT / "tools/quality/ruff_baseline.json")
        self.assertEqual(expected, set())

    def test_zero_baseline_rejects_every_old_diagnostic_category(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps(baseline([])), encoding="utf-8")
            self.assertEqual(load_baseline(path), set())
            for code in ("I001", "E402", "F821"):
                path.write_text(json.dumps(baseline([{**KNOWN, "code": code}])), encoding="utf-8")
                with (
                    self.subTest(code=code),
                    self.assertRaisesRegex(ValueError, "must remain empty"),
                ):
                    load_baseline(path)

    def test_workflow_installs_latest_and_runs_an_independent_mandatory_gate(self) -> None:
        workflow = (ROOT / ".github/workflows/work-ci.yml").read_text(encoding="utf-8")
        quality_job = workflow.split("  ruff_lint:\n", 1)[1].split("  validate:\n", 1)[0]
        self.assertIn("Ruff lint baseline (Python 3.10)", quality_job)
        self.assertIn("--upgrade -r tools/quality/requirements.txt", quality_job)
        self.assertIn("python tools/quality/script/check_ruff.py", quality_job)
        # Changed-file formatting is part of the same mandatory job (Issue #110).
        self.assertIn("tools/quality/script/format_changed.py --check --base", quality_job)
        self.assertIn("fetch-depth: 0", quality_job)
        self.assertNotIn("continue-on-error", quality_job)
        self.assertNotIn("needs:", quality_job)
        self.assertNotIn("if:", quality_job)

    def test_real_cli_from_other_cwd_rejects_ignored_errors_without_writing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory).resolve()
            config = repo / "ruff.toml"
            config.write_text(
                'target-version = "py310"\n[lint]\nselect = ["F"]\n', encoding="utf-8"
            )
            saved = repo / "baseline.json"
            saved.write_text(json.dumps(baseline([])), encoding="utf-8")
            (repo / "clean.py").write_text("value = 1\n", encoding="utf-8")

            def run(*args: str) -> subprocess.CompletedProcess:
                return subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--repo",
                        str(repo),
                        "--baseline",
                        str(saved),
                        "--json",
                        *args,
                    ],
                    cwd=repo.parent,
                    capture_output=True,
                    encoding="utf-8",
                )

            result = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "pass")
            (repo / "ignored.py").write_text("print(undefined_variable)\n", encoding="utf-8")
            (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
            before = {path.name: path.read_bytes() for path in repo.iterdir()}
            result = run()
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)["new"][0]["code"], "F821")
            self.assertEqual({path.name: path.read_bytes() for path in repo.iterdir()}, before)
            saved.write_text(
                json.dumps(baseline(json.loads(result.stdout)["new"])), encoding="utf-8"
            )
            result = run()
            self.assertEqual(result.returncode, 2)
            self.assertIn("must remain empty", result.stderr)
            self.assertEqual(result.stdout, "")
            saved.write_text(json.dumps(baseline([])), encoding="utf-8")
            self.assertEqual(run("--limit", "0").returncode, 2)
            config.write_text("invalid toml =\n", encoding="utf-8")
            result = run()
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            config.write_text(
                'target-version = "py310"\n[lint]\nselect = ["F"]\n', encoding="utf-8"
            )
            (repo / "broken.py").write_text("def invalid(\n", encoding="utf-8")
            result = run()
            self.assertEqual(result.returncode, 2)
            self.assertIn("Ruff syntax error", result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
