from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = Path(__file__).with_name("mypy_baseline.json")


def load_baseline(path: Path) -> tuple[int, int | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("mypy baseline must be a JSON object")

    max_errors = payload.get("max_errors")
    if isinstance(max_errors, bool) or not isinstance(max_errors, int) or max_errors < 0:
        raise ValueError("max_errors must be a non-negative integer")

    tracking_issue = payload.get("tracking_issue")
    if tracking_issue is not None and (
        isinstance(tracking_issue, bool)
        or not isinstance(tracking_issue, int)
        or tracking_issue <= 0
    ):
        raise ValueError("tracking_issue must be a positive integer or null")
    return max_errors, tracking_issue


def count_errors(output: str) -> int:
    return sum(1 for line in output.splitlines() if ": error:" in line)


def evaluate_result(returncode: int, error_count: int, max_errors: int) -> tuple[bool, str]:
    if returncode == 0:
        if error_count != 0:
            return False, "mypy returned success while error output was detected"
        if max_errors > 0:
            return True, f"mypy is clean; reduce baseline from {max_errors} to 0"
        return True, "mypy is clean"

    if error_count == 0:
        return False, "mypy failed without countable type errors"
    if error_count > max_errors:
        return False, f"mypy errors increased: {error_count} > baseline {max_errors}"
    if error_count < max_errors:
        return True, f"mypy errors improved: {error_count} < baseline {max_errors}; lower baseline"
    return True, f"mypy errors unchanged at baseline: {error_count}"


def run_mypy() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mypy", "."],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> int:
    max_errors, tracking_issue = load_baseline(DEFAULT_BASELINE)
    result = run_mypy()

    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)

    error_count = count_errors(result.stdout + "\n" + result.stderr)
    passed, message = evaluate_result(result.returncode, error_count, max_errors)
    issue_suffix = f"; tracking issue #{tracking_issue}" if tracking_issue is not None else ""
    status = "OK" if passed else "FAIL"
    print(f"[{status}] mypy baseline: {message}{issue_suffix}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
