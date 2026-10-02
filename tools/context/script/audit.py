"""Report broken responsibility links, unused patterns and unmapped tracked files."""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.context.script.select_files import MAPPING_PATH, load_mapping, normalize_path


def audit_mapping(root: Path, tracked: list[str], rules: list[dict[str, object]],
                  scopes: tuple[str, ...] = ()) -> dict[str, object]:
    root = root.resolve()
    tracked = sorted(set(normalize_path(path) for path in tracked))
    scopes = tuple(normalize_path(scope.rstrip("/\\")) for scope in scopes)
    selected = [path for path in tracked if not scopes or any(
        path == scope or path.startswith(scope + "/") for scope in scopes
    )]
    errors: list[str] = []
    unmatched: list[str] = []
    mapped: set[str] = set()
    for index, rule in enumerate(rules, 1):
        if not rule["paths"]:
            errors.append(f"rule {index}: paths must not be empty")
        for pattern in rule["paths"]:
            try:
                pattern = normalize_path(pattern)
            except ValueError as exc:
                errors.append(f"rule {index} pattern: {exc}")
                continue
            matches = {path for path in tracked if fnmatchcase(path, pattern)}
            mapped.update(matches)
            if not matches:
                unmatched.append(pattern)
        for field in ("context", "related", "tests"):
            references = [rule[field]] if field == "context" else rule[field]
            for reference in references:
                try:
                    normalized = normalize_path(reference)
                    target = (root / normalized).resolve()
                    if not target.is_relative_to(root):
                        raise ValueError(f"path escapes repository: {reference}")
                    if not target.is_file():
                        raise ValueError(f"missing file: {reference}")
                except ValueError as exc:
                    errors.append(f"rule {index} {field}: {exc}")
    return {
        "tracked_file_count": len(tracked),
        "scope_file_count": len(selected),
        "errors": list(dict.fromkeys(errors)),
        "unmatched_patterns": sorted(set(unmatched)),
        "unmapped_files": [path for path in selected if path not in mapped],
    }


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--full-name", "-z"], cwd=root,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip())
    return [path.decode("utf-8", errors="surrogateescape")
            for path in result.stdout.split(b"\0") if path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT, help="repository root")
    parser.add_argument("--mapping", type=Path, default=MAPPING_PATH)
    parser.add_argument("--scope", action="append", default=[], help="limit unmapped-file report")
    parser.add_argument("--strict", action="store_true", help="fail on unused or unmapped entries too")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = audit_mapping(args.repo, tracked_files(args.repo), load_mapping(args.mapping),
                               tuple(args.scope))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"Audited {report['scope_file_count']} of {report['tracked_file_count']} tracked files")
        for key in ("errors", "unmatched_patterns", "unmapped_files"):
            print(f"{key}: {len(report[key])}")
            for item in report[key]:
                print(f"  {item}")
    return int(bool(report["errors"] or (args.strict and (
        report["unmatched_patterns"] or report["unmapped_files"]
    ))))


if __name__ == "__main__":
    raise SystemExit(main())
