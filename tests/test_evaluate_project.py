from contextlib import redirect_stdout
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from scripts.evaluate_project import (
    build_checks,
    iter_python_files,
    main,
    parse_args,
    run_check,
    snapshot_shared_json,
    validate_runtime_log,
)


class EvaluateProjectTests(unittest.TestCase):
    def test_python_file_scan_ignores_virtualenv(self):
        files = iter_python_files(PROJECT_DIR)
        relative = [path.relative_to(PROJECT_DIR).as_posix() for path in files]

        self.assertIn("game.py", relative)
        self.assertIn("scripts/evaluate_project.py", relative)
        self.assertFalse(any(".venv" in item for item in relative))

    def test_build_checks_include_standard_and_special_validation(self):
        labels = [label for label, _command, _env in build_checks(PROJECT_DIR, 12)]

        self.assertEqual(
            labels,
            [
                "py_compile",
                "unit tests",
                "engine manifest",
                "standard game smoke",
                "runtime evaluation log",
                "special project validate",
            ],
        )

    def test_run_check_passes_environment_to_subprocess(self):
        completed = Mock(returncode=0)
        with patch("scripts.evaluate_project.subprocess.run", return_value=completed) as run:
            self.assertTrue(run_check("demo", ["python", "--version"], {"X_TEST": "1"}))

        _command, kwargs = run.call_args
        self.assertEqual(kwargs["cwd"], PROJECT_DIR)
        self.assertEqual(kwargs["env"]["X_TEST"], "1")

    def test_required_mode_uses_real_cli_and_strict_audit(self):
        checks = build_checks(PROJECT_DIR, 12, require_godot=True)
        label, command, environment = checks[0]
        self.assertEqual(label, "required Godot smoke")
        self.assertEqual(command[1:], ["engine_app.py", "--playtest-godot", "--headless",
                                      "--test-frames", "12", "--seed", "12345"])
        self.assertEqual(environment, {})
        self.assertEqual(checks[-1][0], "context responsibilities")
        self.assertIn("--strict", checks[-1][1])
        self.assertIn(".github", checks[-1][1])

    def test_generated_python_is_excluded_from_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "game.py").write_text("pass", encoding="utf-8")
            for name in ("tmp", ".godot", ".venv", "__pycache__"):
                (root / name).mkdir()
                (root / name / "generated.py").write_text("not valid Python", encoding="utf-8")
            self.assertEqual(iter_python_files(root), [root / "game.py"])

    def test_failed_child_is_not_reported_as_success(self):
        with patch("scripts.evaluate_project.subprocess.run", return_value=Mock(returncode=1)):
            self.assertFalse(run_check("failed Godot", ["godot", "--headless"], {}))

    def test_required_godot_failure_makes_evaluation_fail_even_if_optional_tests_pass(self):
        with patch("scripts.evaluate_project.run_check", side_effect=lambda label, *_: label != "required Godot smoke"), \
                patch("scripts.evaluate_project.validate_runtime_log", return_value=True), \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--require-godot", "--frames", "12"]), 1)
        self.assertIn("FAILED: required Godot smoke", output.getvalue())

    def test_shared_snapshot_covers_standard_and_special_not_generated_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            special = root / "projects" / "obakeno_sumika_special"
            special.mkdir(parents=True)
            (root / "room.json").write_bytes(b'{"standard":true}')
            (special / "room.json").write_bytes(b'{"special":true}')
            (root / "tmp").mkdir()
            (root / "tmp" / "log.json").write_bytes(b"generated")
            snapshot = snapshot_shared_json(root)
            self.assertEqual(set(snapshot), {"room.json", "projects/obakeno_sumika_special/room.json"})
            self.assertEqual(snapshot["room.json"], b'{"standard":true}')

    def test_changed_shared_input_makes_successful_checks_fail(self):
        for after in ({"room.json": b"changed"}, {}, {"room.json": b"before", "added.json": b"new"}):
            with self.subTest(after=after), \
                    patch("scripts.evaluate_project.snapshot_shared_json", side_effect=[{"room.json": b"before"}, after]), \
                    patch("scripts.evaluate_project.run_check", return_value=True), \
                    patch("scripts.evaluate_project.validate_runtime_log", return_value=True), \
                    redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([]), 1)
            self.assertIn("[FAIL] shared JSON unchanged", output.getvalue())

    def test_snapshot_read_error_prevents_checks(self):
        with patch("scripts.evaluate_project.snapshot_shared_json", side_effect=OSError("unreadable")), \
                patch("scripts.evaluate_project.run_check") as run, redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 1)
        run.assert_not_called()

    def test_positive_frame_count_is_required(self):
        for count in ("0", "-1"):
            with self.subTest(count=count), patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as caught:
                parse_args(["--frames", count])
            self.assertEqual(caught.exception.code, 2)

    def test_workflow_keeps_required_gate_and_read_only_pr_permissions(self):
        workflow = (PROJECT_DIR / ".github" / "workflows" / "work-ci.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:\n    branches: [work]", workflow)
        self.assertIn("push:\n    branches: [work]", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("--require-godot --frames 900", workflow)
        self.assertIn("set -o pipefail", workflow)
        self.assertIn("if: always()", workflow)
        for unsafe_or_skipping in ("pull_request_target:", "continue-on-error:", "paths-ignore:", "contents: write"):
            self.assertNotIn(unsafe_or_skipping, workflow)

    def test_validate_runtime_log_requires_ghost_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log = root / "runtime.jsonl"
            log.write_text(
                '{"ghosts":[{"name":"kadoka","x":1,"y":2,"vx":0,"vy":0,'
                '"facing":1,"action":"stop"},{"name":"maru","x":3,"y":4,'
                '"vx":0,"vy":0,"facing":-1,"action":"stop"}],"objects":[]}\n',
                encoding="utf-8",
            )

            self.assertTrue(validate_runtime_log(root, Path("runtime.jsonl")))


if __name__ == "__main__":
    unittest.main()
