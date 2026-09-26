"""Show the smallest documented reading set for changed repository files."""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = PROJECT_ROOT / "tools" / "context" / "responsibilities.json"


def normalize_path(value: str) -> str:
    path = value.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    if not path or path.startswith("/") or ":" in parts[0] or any(
        part in ("", "..") for part in parts
    ):
        raise ValueError(f"expected a repository-relative path: {value}")
    return path


def load_mapping(path: Path = MAPPING_PATH) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("rules"), list):
        raise ValueError("unsupported responsibility table")
    rules = payload["rules"]
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("context"), str) or not all(
            isinstance(rule.get(key), list)
            and all(isinstance(value, str) for value in rule[key])
            for key in ("paths", "related", "tests")
        ):
            raise ValueError("invalid responsibility rule")
    return rules


def select_files(paths: list[str], rules: list[dict[str, object]]) -> dict[str, list[str]]:
    changed = list(dict.fromkeys(normalize_path(path) for path in paths))
    contexts = ["docs/context/project.md"]
    related: list[str] = []
    tests: list[str] = []
    unmapped: list[str] = []
    for path in changed:
        matches = [
            rule for rule in rules
            if any(fnmatchcase(path, pattern) for pattern in rule["paths"])
        ]
        if not matches:
            unmapped.append(path)
        for rule in matches:
            contexts.append(rule["context"])
            related.extend(rule["related"])
            tests.extend(rule["tests"])
    return {
        "changed_files": changed,
        "contexts": list(dict.fromkeys(contexts)),
        "related_files": list(dict.fromkeys(path for path in related if path not in changed)),
        "tests": list(dict.fromkeys(tests)),
        "unmapped_files": unmapped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="changed paths relative to repository root")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    try:
        selection = select_files(args.paths, load_mapping())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(selection, ensure_ascii=False, indent=2))
    else:
        for label, key in (
            ("Read context", "contexts"),
            ("Changed files", "changed_files"),
            ("Related files", "related_files"),
            ("Relevant tests", "tests"),
            ("Unmapped files (inspect manually)", "unmapped_files"),
        ):
            print(f"{label}:")
            for path in selection[key]:
                print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
