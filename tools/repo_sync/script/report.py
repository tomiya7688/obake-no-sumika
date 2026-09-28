"""Inspect local/remote branch drift without merging or touching worktree files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.diff_summary.script.summarize import git, resolve_commit, summarize, text


REMOTE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def inspect(repo: Path, remote: str = "origin", branch: str = "work", *, fetch: bool = False,
            max_files: int = 20) -> dict[str, object]:
    if not REMOTE_NAME.fullmatch(remote):
        raise ValueError("invalid remote name")
    if not branch or branch.startswith("-"):
        raise ValueError("invalid branch name")
    repo = Path(text(git(repo, "rev-parse", "--show-toplevel")).strip())
    git(repo, "check-ref-format", "--branch", branch)
    git(repo, "remote", "get-url", remote)
    if fetch:
        git(repo, "fetch", "--prune", remote)
    local = resolve_commit(repo, f"refs/heads/{branch}")
    upstream = resolve_commit(repo, f"refs/remotes/{remote}/{branch}")
    common = text(git(repo, "merge-base", local, upstream)).strip()
    ahead = int(text(git(repo, "rev-list", "--count", f"{common}..{local}")).strip())
    behind = int(text(git(repo, "rev-list", "--count", f"{common}..{upstream}")).strip())
    dirty = bool(git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"))
    if ahead and behind:
        state = "diverged"
    elif behind:
        state = "behind"
    elif ahead:
        state = "ahead"
    else:
        state = "up_to_date"
    return {
        "remote": remote,
        "branch": branch,
        "fetched": fetch,
        "local": local,
        "upstream": upstream,
        "merge_base": common,
        "ahead": ahead,
        "behind": behind,
        "state": state,
        "dirty_worktree": dirty,
        "fast_forward_safe": state == "behind" and not dirty,
        "remote_changes": summarize(repo, common, upstream, max_files) if behind else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="work")
    parser.add_argument("--fetch", action="store_true", help="update remote-tracking refs first")
    parser.add_argument("--max-files", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = inspect(args.repo, args.remote, args.branch,
                         fetch=args.fetch, max_files=args.max_files)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"{report['branch']} vs {report['remote']}/{report['branch']}: {report['state']}")
        print(f"  ahead={report['ahead']} behind={report['behind']} dirty={report['dirty_worktree']}")
        print(f"  fetched={report['fetched']} fast_forward_safe={report['fast_forward_safe']}")
        changes = report["remote_changes"]
        if changes:
            size = changes["summary"]
            print(f"  remote changes: {changes['file_count']} files (+{size['added_lines']}/-{size['deleted_lines']})")
            for commit in changes["commits"]:
                print(f"    commit {commit}")
            for file in changes["files"]:
                print(f"    {file['status']} {file['path']}")
                if file["tests"]:
                    print(f"      tests: {', '.join(file['tests'])}")
            if changes["omitted_files"]:
                print(f"    ... {changes['omitted_files']} more files")
        if not report["fetched"]:
            print("  Remote-tracking refs may be stale; use --fetch to refresh them.")
        print("  No merge or worktree modification was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
