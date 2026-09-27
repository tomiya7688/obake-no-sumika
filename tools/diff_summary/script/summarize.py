"""Summarize committed Git changes without emitting the full patch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.context.script.select_files import load_mapping, select_files


DEFINITION = re.compile(r"^[+-]\s*((?:async\s+)?def\s+\w+|class\s+\w+)")


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(message or f"git failed: {args[0]}")
    return result.stdout


def text(data: bytes) -> str:
    return data.decode("utf-8", errors="surrogateescape")


def resolve_commit(repo: Path, revision: str) -> str:
    if not revision or revision.startswith("-"):
        raise ValueError("revision must be a commit name")
    output = git(repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}")
    return text(output).strip()


def changed_definitions(repo: Path, base: str, head: str, path: str) -> list[str]:
    if not path.endswith(".py"):
        return []
    patch = text(git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "-U0", base, head, "--", path))
    definitions = []
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        match = DEFINITION.match(line)
        if match:
            definitions.append(f"{line[0]} {match.group(1)}")
    return list(dict.fromkeys(definitions))[:8]


def summarize(repo: Path, base_ref: str, head_ref: str, max_files: int = 50) -> dict[str, object]:
    if max_files < 1:
        raise ValueError("max_files must be positive")
    repo = Path(text(git(repo, "rev-parse", "--show-toplevel")).strip())
    base = resolve_commit(repo, base_ref)
    head = resolve_commit(repo, head_ref)
    status_parts = git(repo, "diff", "--no-renames", "--name-status", "-z", base, head, "--").split(b"\0")
    status_pairs = [
        (text(status_parts[index]), text(status_parts[index + 1]))
        for index in range(0, len(status_parts) - 1, 2)
    ]
    counts = {}
    for record in git(repo, "diff", "--no-renames", "--numstat", "-z", base, head, "--").split(b"\0"):
        if record:
            added, deleted, path = text(record).split("\t", 2)
            counts[path] = (added, deleted)
    status_counts: dict[str, int] = {}
    for status, _ in status_pairs:
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "statuses": status_counts,
        "added_lines": sum(int(added) for added, _ in counts.values() if added != "-"),
        "deleted_lines": sum(int(deleted) for _, deleted in counts.values() if deleted != "-"),
        "binary_files": sum(1 for added, _ in counts.values() if added == "-"),
    }
    rules = load_mapping()
    files = []
    for status, path in status_pairs[:max_files]:
        selected = select_files([path], rules)
        added, deleted = counts.get(path, ("0", "0"))
        files.append({
            "path": path,
            "status": status,
            "added": added,
            "deleted": deleted,
            "contexts": selected["contexts"],
            "related_files": selected["related_files"],
            "tests": selected["tests"],
            "changed_definitions": changed_definitions(repo, base, head, path),
            "unmapped": bool(selected["unmapped_files"]),
        })
    commits = text(git(repo, "log", "--format=%h %s", "--max-count=10", f"{base}..{head}"))
    return {
        "base": base,
        "head": head,
        "file_count": len(status_pairs),
        "omitted_files": max(0, len(status_pairs) - max_files),
        "summary": summary,
        "commits": commits.splitlines(),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="older Git commit or ref")
    parser.add_argument("--head", default="HEAD", help="newer Git commit or ref")
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--max-files", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = summarize(args.repo, args.base, args.head, args.max_files)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        size = result["summary"]
        print(
            f"{result['base'][:8]}..{result['head'][:8]}: {result['file_count']} files "
            f"(+{size['added_lines']}/-{size['deleted_lines']}, "
            f"{size['binary_files']} binary)"
        )
        for commit in result["commits"]:
            print(f"  commit {commit}")
        for file in result["files"]:
            print(f"  {file['status']} {file['path']} (+{file['added']}/-{file['deleted']})")
            for key, label in (
                ("contexts", "context"),
                ("related_files", "related"),
                ("tests", "tests"),
            ):
                if file[key]:
                    print(f"    {label}: {', '.join(file[key])}")
            for definition in file["changed_definitions"]:
                print(f"    {definition}")
            if file["unmapped"]:
                print("    unmapped: inspect manually")
        if result["omitted_files"]:
            print(f"  ... {result['omitted_files']} more files (use --max-files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
