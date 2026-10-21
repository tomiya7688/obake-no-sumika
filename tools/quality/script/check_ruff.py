"""Run mandatory Ruff lint with an empty, non-expandable baseline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

PROJECT_ROOT = Path(__file__).resolve().parents[3]
Signature = tuple[str, str, int, int]


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def signature(record: object) -> Signature:
    if not isinstance(record, dict) or set(record) != {"path", "code", "row", "column"}:
        raise ValueError("diagnostic needs path/code/row/column")
    path, code = record["path"], record["code"]
    if (
        not isinstance(path, str)
        or not path
        or "\\" in path
        or ":" in path
        or path.startswith("/")
        or str(PurePosixPath(path)) != path
        or any(part in {".", ".."} for part in path.split("/"))
    ):
        raise ValueError("diagnostic path must be repository-relative")
    if not isinstance(code, str) or not re.fullmatch(r"[A-Z]+[0-9]+", code):
        raise ValueError("invalid diagnostic code")
    if any(type(record[key]) is not int or record[key] < 1 for key in ("row", "column")):
        raise ValueError("diagnostic row/column must be positive integers")
    return path, code, record["row"], record["column"]


def records_to_set(records: object, *, baseline: bool = False) -> set[Signature]:
    if not isinstance(records, list):
        raise ValueError("diagnostics must be a list")
    result = set()
    for record in records:
        item = signature(record)
        if baseline:
            raise ValueError("baseline must remain empty; fix diagnostics instead of adding exceptions")
        if item in result:
            raise ValueError("duplicate diagnostic")
        result.add(item)
    return result


def load_baseline(path: Path) -> set[Signature]:
    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload["schema_version"] != 1
    ):
        raise ValueError("baseline schema_version must be 1")
    if not isinstance(payload.get("recorded_with"), str) or not payload["recorded_with"].strip():
        raise ValueError("baseline needs recorded_with")
    if type(payload.get("tracking_issue")) is not int or payload["tracking_issue"] < 1:
        raise ValueError("baseline needs a tracking_issue")
    return records_to_set(payload.get("diagnostics"), baseline=True)


def run_command(repo: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def run_ruff(repo: Path) -> tuple[str, set[Signature]]:
    version = run_command(repo, ["--version"], timeout=10)
    if version.returncode or not version.stdout.strip().startswith("ruff "):
        raise ValueError(
            "Ruff is unavailable; install tools/quality/requirements.txt: "
            + version.stderr.strip()[:1000]
        )
    checked = run_command(
        repo,
        [
            "check",
            ".",
            "--config",
            str(repo / "ruff.toml"),
            "--output-format",
            "json",
            "--no-cache",
            "--no-fix",
            "--no-respect-gitignore",
        ],
    )
    if checked.returncode not in (0, 1):
        raise ValueError(f"Ruff execution failed ({checked.returncode}): {checked.stderr[:2000]}")
    payload = json.loads(checked.stdout, object_pairs_hook=unique_object)
    if not isinstance(payload, list):
        raise ValueError("Ruff output must be a diagnostic list")
    records = []
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("filename"), str):
            raise ValueError("Ruff diagnostic needs filename")
        location = item.get("location")
        if not isinstance(location, dict):
            raise ValueError("Ruff diagnostic needs location")
        filename = Path(item["filename"])
        if not filename.is_absolute():
            raise ValueError("Ruff filename must be absolute")
        relative = filename.resolve().relative_to(repo).as_posix()
        if item.get("code") == "invalid-syntax":
            raise ValueError(
                f"Ruff syntax error: {relative}:{location.get('row')}: "
                + str(item.get("message", "invalid syntax"))
            )
        records.append(
            {
                "path": relative,
                "code": item.get("code"),
                "row": location.get("row"),
                "column": location.get("column"),
            }
        )
    actual = records_to_set(records)
    if bool(actual) != (checked.returncode == 1):
        raise ValueError("Ruff exit status does not match its diagnostics")
    return version.stdout.strip(), actual


def record(item: Signature) -> dict:
    return dict(zip(("path", "code", "row", "column"), item))


def compare(actual: set[Signature], expected: set[Signature], limit: int = 20) -> dict:
    if limit < 1:
        raise ValueError("limit must be positive")
    new, stale = sorted(actual - expected), sorted(expected - actual)
    return {
        "status": "fail" if new or stale else "pass",
        "total_diagnostics": len(actual),
        "baseline_size": len(expected),
        "new_count": len(new),
        "stale_count": len(stale),
        "new": [record(item) for item in new[:limit]],
        "stale": [record(item) for item in stale[:limit]],
        "omitted_new": max(0, len(new) - limit),
        "omitted_stale": max(0, len(stale) - limit),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--baseline", type=Path, help="default: <repo>/tools/quality/ruff_baseline.json"
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.limit < 1:
            raise ValueError("limit must be positive")
        repo = args.repo.resolve(strict=True)
        expected = load_baseline(args.baseline or repo / "tools/quality/ruff_baseline.json")
        version, actual = run_ruff(repo)
        report = {"tool": version, **compare(actual, expected, args.limit)}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(
            f"{version}: {report['status']} ({len(actual)} diagnostics, {len(expected)} baseline, "
            f"{report['new_count']} new, {report['stale_count']} stale)"
        )
        for name in ("new", "stale"):
            for item in report[name]:
                print(f"  {name}: " + json.dumps(item, ensure_ascii=True))
            if report[f"omitted_{name}"]:
                print(f"  ... {report[f'omitted_{name}']} more {name} entries (use --limit)")
        if report["stale_count"]:
            print(
                "Remove resolved entries from the baseline; do not increase it to silence new issues."
            )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
