"""Print bounded Git worktree/index metadata, never file contents or patches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.diff_summary.script.summarize import git as run_git, resolve_commit, text


def git(repo: Path, *args: str) -> bytes:
    # Even index-refresh optimizations are unwanted in a read-only context query.
    return run_git(repo, "--no-optional-locks", *args)


def bounded(items: list, limit: int) -> dict:
    return {"total": len(items), "omitted": max(0, len(items) - limit), "items": items[:limit]}


def diff_metadata(repo: Path, revisions: list[str], limit: int) -> dict:
    options = ["diff", "--no-ext-diff", "--no-textconv", "--no-renames"]
    parts = git(repo, *options, "--name-status", "-z", *revisions, "--").split(b"\0")
    counts = {}
    for record in git(repo, *options, "--numstat", "-z", *revisions, "--").split(b"\0"):
        if record:
            added, deleted, path = text(record).split("\t", 2)
            counts[path] = (added, deleted)
    files = []
    # A conflicted path can have both U and M records; keep both statuses on one file.
    statuses = {}
    for index in range(0, len(parts) - 1, 2):
        status, path = text(parts[index]), text(parts[index + 1])
        statuses.setdefault(path, []).append(status)
    for path, status in statuses.items():
        added, deleted = counts.get(path, ("0", "0"))
        files.append({"path": path, "statuses": status, "added": added, "deleted": deleted})
    return {
        **bounded(files, limit),
        "summary": {
            "added_lines": sum(int(a) for a, _ in counts.values() if a != "-"),
            "deleted_lines": sum(int(d) for _, d in counts.values() if d != "-"),
            "binary_files": sum(a == "-" for a, _ in counts.values()),
        },
    }


def commit_metadata(repo: Path, revision: str, limit: int) -> dict:
    total = int(git(repo, "rev-list", "--count", revision, "--"))
    lines = text(git(repo, "log", "--no-decorate", "--format=%h %s", f"--max-count={limit}",
                     revision, "--")).rstrip("\n").split("\n")
    return {"total": total, "omitted": max(0, total - limit), "items": lines if total else []}


def collect_snapshot(repo: Path, base: str | None = None, limit: int = 20, commits: int = 8) -> dict:
    if limit < 1 or commits < 1:
        raise ValueError("limit and commits must be positive")
    repo = Path(text(git(repo, "rev-parse", "--show-toplevel")).strip())
    head = resolve_commit(repo, "HEAD")
    branch = text(git(repo, "rev-parse", "--abbrev-ref", "HEAD")).strip()
    base_sha = resolve_commit(repo, base) if base is not None else None
    untracked = [text(path) for path in git(repo, "ls-files", "--others", "--exclude-standard", "-z", "--").split(b"\0") if path]
    result = {
        "schema_version": 1,
        "repository": str(repo),
        "branch": None if branch == "HEAD" else branch,
        "head": head,
        "working": diff_metadata(repo, [], limit),
        "staged": diff_metadata(repo, ["--cached", head], limit),
        "untracked": bounded(untracked, limit),
        "recent_commits": commit_metadata(repo, head, commits),
    }
    if base_sha is not None:
        merge_base = text(git(repo, "merge-base", base_sha, head)).strip()
        result["base"] = {
            "ref": base,
            "commit": base_sha,
            "merge_base": merge_base,
            "changes": diff_metadata(repo, [merge_base, head], limit),
            "commits": commit_metadata(repo, f"{base_sha}..{head}", commits),
        }
    return result


def print_snapshot(result: dict) -> None:
    print(f"{result['branch'] or '(detached HEAD)'} @ {result['head'][:12]}")
    for name in ("working", "staged", "untracked", "recent_commits"):
        print_section(name, result[name])
    if "base" in result:
        base = result["base"]
        print(f"base {base['ref']} @ {base['commit'][:12]}, merge-base {base['merge_base'][:12]}")
        print_section("base changes (merge-base -> HEAD)", base["changes"])
        print_section("base commits (base..HEAD)", base["commits"])


def print_section(name: str, section: dict) -> None:
    print(f"{name}: {section['total']} entries, {section['omitted']} omitted")
    if "summary" in section:
        size = section["summary"]
        print(f"  +{size['added_lines']}/-{size['deleted_lines']}, {size['binary_files']} binary")
    for item in section["items"]:
        # Escape control characters in filenames/subjects even in human-readable mode.
        print("  " + json.dumps(item, ensure_ascii=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--base", help="optional base ref; files use merge-base, commits use base..HEAD")
    parser.add_argument("--limit", type=int, default=20, help="maximum files per section")
    parser.add_argument("--commits", type=int, default=8, help="maximum subjects per history section")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = collect_snapshot(args.repo, args.base, args.limit, args.commits)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        print_snapshot(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
