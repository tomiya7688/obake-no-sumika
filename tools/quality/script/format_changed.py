"""Format, or check, only the Python files changed by the current piece of work.

Exactly one source of files is used, so other agents' uncommitted edits in a
shared checkout are never touched:

* explicit paths           format_changed.py game.py tests/test_x.py
* the files you staged     format_changed.py --staged
* a branch against a base  format_changed.py --base origin/work

Add --check to report files that need formatting without rewriting them.
Ruff runs from the current interpreter with the repository's ruff.toml.

Ruff rewrites whole files in the working tree. With --staged or --base a
selected file must therefore have no other pending edits (unstaged changes, or
for --base anything not committed); otherwise someone else's work could be
reformatted, and the check would not describe what gets committed. Such files
are refused with exit code 2.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class SelectionError(Exception):
    """The requested files cannot be formatted safely."""


def git_paths(repo: Path, command: str, *args: str) -> list[str]:
    """Run a git command that lists paths and return them (NUL separated)."""
    result = subprocess.run(
        ["git", command, "-z", *args],
        cwd=repo,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise SelectionError(f"git {command} {' '.join(args)} failed: {detail}")
    return [name for name in result.stdout.decode("utf-8").split("\0") if name]


def inside_repo(repo: Path, name: str) -> str:
    path = (repo / name).resolve()
    try:
        relative = path.relative_to(repo)
    except ValueError:
        raise SelectionError(f"outside the repository: {name}") from None
    if not path.is_file():
        raise SelectionError(f"not a file: {name}")
    return relative.as_posix()


def changed_python_files(
    repo: Path, *, staged: bool = False, base: str | None = None, paths: list[str] | None = None
) -> list[str]:
    """Return repository-relative .py files from exactly one source, deleted files excluded."""
    if sum((staged, base is not None, bool(paths))) != 1:
        raise ValueError("choose exactly one of: paths, --staged, --base")
    repo = repo.resolve()
    if paths:
        names = paths
        pending: set[str] = set()
    elif staged:
        names = git_paths(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
        # Unstaged edits on top of the staged version would be reformatted too.
        pending = set(git_paths(repo, "diff", "--name-only"))
    else:
        names = git_paths(
            repo, "diff", "--name-only", "--diff-filter=ACMR", "--end-of-options", f"{base}...HEAD"
        )
        # Anything not committed (staged or not) is outside the branch diff.
        pending = set(git_paths(repo, "diff", "HEAD", "--name-only"))
    selected = sorted({inside_repo(repo, name) for name in names if Path(name).suffix == ".py"})
    blocked = [name for name in selected if name in pending]
    if blocked:
        raise SelectionError(
            "uncommitted edits outside the selection in: "
            + ", ".join(blocked)
            + " (stage or commit your own edits; leave others' edits alone)"
        )
    return selected


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
    except (ValueError, SelectionError) as exc:
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
