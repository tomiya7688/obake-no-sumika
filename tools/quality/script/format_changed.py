"""Format, or check, only the Python files changed by the current piece of work.

Exactly one source of files is used, so other agents' uncommitted edits in a
shared checkout are never touched:

* explicit paths           format_changed.py game.py tests/test_x.py
* the files you staged     format_changed.py --staged
* a branch against a base  format_changed.py --base origin/work

Add --check to report files that need formatting without rewriting them.
Ruff runs from the current interpreter with the repository's ruff.toml.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def git_lines(repo: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def changed_python_files(
    repo: Path, *, staged: bool = False, base: str | None = None, paths: list[str] | None = None
) -> list[str]:
    """Return repository-relative .py files from exactly one source, deleted files excluded."""
    if sum((staged, base is not None, bool(paths))) != 1:
        raise ValueError("choose exactly one of: paths, --staged, --base")
    if paths:
        names = paths
    elif staged:
        names = git_lines(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    else:
        names = git_lines(repo, "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD")
    selected = []
    for name in names:
        path = Path(name)
        if path.suffix != ".py":
            continue
        if not (repo / path).is_file():
            raise FileNotFoundError(f"not a file: {name}")
        selected.append(path.as_posix())
    return sorted(set(selected))


def run_ruff_format(repo: Path, files: list[str], *, check: bool) -> int:
    command = [sys.executable, "-m", "ruff", "format"]
    if check:
        command.append("--check")
    # --force-exclude keeps ruff.toml exclusions (.venv, tmp, ...) for explicit paths.
    command += ["--force-exclude", "--", *files]
    return subprocess.run(command, cwd=repo).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help="Python files to format (repository-relative)")
    parser.add_argument("--staged", action="store_true", help="use the files staged with git add")
    parser.add_argument("--base", help="use files changed between BASE...HEAD, e.g. origin/work")
    parser.add_argument("--check", action="store_true", help="report only; do not rewrite files")
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        files = changed_python_files(repo, staged=args.staged, base=args.base, paths=args.paths)
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"format_changed: {exc}", file=sys.stderr)
        return 2
    version = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"], capture_output=True, text=True
    )
    if version.returncode != 0:
        print("format_changed: ruff is not installed in this interpreter", file=sys.stderr)
        return 2
    print(f"{version.stdout.strip()}: {'check' if args.check else 'format'} {len(files)} file(s)")
    if not files:
        return 0
    for name in files:
        print(f"  {name}")
    code = run_ruff_format(repo, files, check=args.check)
    if code == 0 and args.staged and not args.check:
        print("format_changed: re-run git add for the files above to stage the formatting")
    return code


if __name__ == "__main__":
    sys.exit(main())
