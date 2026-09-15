from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_git(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        output = result.stderr.strip() or output
    return result.returncode, output


def limited_lines(text: str, limit: int) -> list[str]:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) <= limit:
        return lines
    hidden = len(lines) - limit
    return [*lines[:limit], f"... +{hidden} more"]


def git_text(args: list[str], limit: int) -> dict[str, object]:
    code, output = run_git(*args)
    return {
        "ok": code == 0,
        "lines": limited_lines(output, limit),
    }


def collect_snapshot(base: str | None, limit: int, commits: int) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "branch": git_text(["status", "--short", "--branch"], limit),
        "working_files": git_text(["diff", "--name-status"], limit),
        "staged_files": git_text(["diff", "--cached", "--name-status"], limit),
        "working_stat": git_text(["diff", "--stat"], limit),
        "recent_commits": git_text(["log", f"-{commits}", "--oneline", "--decorate=no"], limit),
    }
    if base:
        snapshot["base"] = base
        snapshot["base_files"] = git_text(["diff", "--name-status", f"{base}...HEAD"], limit)
        snapshot["base_stat"] = git_text(["diff", "--stat", f"{base}...HEAD"], limit)
        snapshot["base_commits"] = git_text(
            ["log", "--oneline", f"{base}..HEAD", f"-{commits}"], limit
        )
    return snapshot


def print_section(title: str, value: object) -> None:
    print(f"[{title}]")
    if isinstance(value, dict) and "lines" in value:
        lines = value.get("lines")
        if isinstance(lines, list) and lines:
            for line in lines:
                print(line)
        elif value.get("ok"):
            print("(clean)")
        else:
            print("(unavailable)")
    else:
        print(value)


def print_text(snapshot: dict[str, object]) -> None:
    order = [
        "branch",
        "working_files",
        "staged_files",
        "working_stat",
        "base_files",
        "base_stat",
        "base_commits",
        "recent_commits",
    ]
    for key in order:
        if key not in snapshot:
            continue
        print_section(key, snapshot[key])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print compact Git context for AI-assisted development."
    )
    parser.add_argument(
        "--base",
        help="Optional comparison base such as origin/main. Uses three-dot diff.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="Maximum output lines per section.",
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=8,
        help="Maximum recent commit subjects.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1 or args.commits < 1:
        raise SystemExit("--limit and --commits must be >= 1")
    snapshot = collect_snapshot(args.base, args.limit, args.commits)
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print_text(snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
