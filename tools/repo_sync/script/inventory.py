"""Check a proposed main/work inventory against Git history without changing it."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Resolve from this file, not the caller's working directory, before local imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.diff_summary.script.summarize import git, resolve_commit, text

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_PLAN = PROJECT_ROOT / "tools/repo_sync/main_work_inventory.json"
COMMIT = re.compile(r"[0-9a-f]{40}")
GROUP = re.compile(r"[a-z][a-z0-9_]*")
DECISIONS = {"port", "replaced", "reference_only", "obsolete"}


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate inventory key: {key}")
        result[key] = value
    return result


def validate_plan(plan: object) -> dict:
    if not isinstance(plan, dict) or type(plan.get("schema_version")) is not int or plan["schema_version"] != 1:
        raise ValueError("inventory schema_version must be 1")
    if plan.get("status") != "proposal":
        raise ValueError("inventory must remain a proposal, not a release approval")
    snapshots = plan.get("snapshots")
    if not isinstance(snapshots, dict) or set(snapshots) != {"main", "work", "merge_base"}:
        raise ValueError("inventory needs main/work/merge_base snapshots")
    if any(not isinstance(value, str) or not COMMIT.fullmatch(value) for value in snapshots.values()):
        raise ValueError("snapshot commits must be full lowercase SHA1s")
    groups = plan.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ValueError("inventory needs groups")
    for name, group in groups.items():
        if not isinstance(name, str) or not GROUP.fullmatch(name) or not isinstance(group, dict):
            raise ValueError("invalid inventory group")
        if not isinstance(group.get("decision"), str) or group["decision"] not in DECISIONS:
            raise ValueError(f"unknown decision for {name}")
        for field in ("summary", "verification"):
            if not isinstance(group.get(field), str) or not group[field].strip():
                raise ValueError(f"{name} needs {field}")
        for field in ("source_paths", "work_targets"):
            paths = group.get(field)
            if not isinstance(paths, list) or not paths or any(not isinstance(path, str) or not path.strip() for path in paths):
                raise ValueError(f"{name} needs {field}")
    commits = plan.get("commits")
    if not isinstance(commits, dict) or not commits:
        raise ValueError("inventory needs commits")
    used = set()
    for sha, names in commits.items():
        if not isinstance(sha, str) or not COMMIT.fullmatch(sha):
            raise ValueError("inventory commits must be full lowercase SHA1s")
        if not isinstance(names, list) or not names or any(not isinstance(name, str) or name not in groups for name in names):
            raise ValueError(f"unknown or empty groups for {sha}")
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate groups for {sha}")
        used.update(names)
    if used != set(groups):
        raise ValueError("inventory has unused groups")
    return plan


def load_plan(path: Path) -> dict:
    return validate_plan(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object))


def inspect_inventory(repo: Path, plan: dict, main_ref: str = "origin/main", work_ref: str = "origin/work") -> dict:
    validate_plan(plan)
    repo = Path(text(git(repo, "rev-parse", "--show-toplevel")).strip())
    main = resolve_commit(repo, main_ref)
    work = resolve_commit(repo, work_ref)
    snapshots = plan["snapshots"]
    # Missing pinned objects (e.g. shallow CI checkout) are errors, not success.
    pinned_main = resolve_commit(repo, snapshots["main"])
    pinned_work = resolve_commit(repo, snapshots["work"])
    pinned_base = resolve_commit(repo, snapshots["merge_base"])
    baseline = set(text(git(repo, "rev-list", f"{pinned_work}..{pinned_main}")).splitlines())
    baseline_base = text(git(repo, "merge-base", pinned_main, pinned_work)).strip()
    common = text(git(repo, "merge-base", main, work)).strip()
    work_descends = text(git(repo, "merge-base", pinned_work, work)).strip() == pinned_work
    expected = set(plan["commits"])
    records = text(git(repo, "log", "--reverse", "--format=%H%x00%s", f"{work}..{main}")).splitlines()
    commits = []
    for record in records:
        sha, subject = record.split("\0", 1)
        names = plan["commits"].get(sha, [])
        commits.append({"sha": sha, "subject": subject, "groups": list(names),
                        "decisions": sorted({plan["groups"][name]["decision"] for name in names})})
    actual = {item["sha"] for item in commits}
    issues = []
    for condition, label in (
        (main != pinned_main, "main snapshot changed"),
        (not work_descends, "work no longer descends from snapshot"),
        (baseline_base != pinned_base, "pinned merge base mismatch"),
        (common != pinned_base, "live merge base changed"),
        (baseline != expected, "pinned commit coverage mismatch"),
        (actual != expected, "live commit coverage changed"),
    ):
        if condition:
            issues.append(label)
    return {
        "status": "needs_refresh" if issues else "consistent",
        "proposal_only": True,
        "fetched": False,
        "main": main,
        "work": work,
        "merge_base": common,
        "work_only_count": int(text(git(repo, "rev-list", "--count", f"{main}..{work}")).strip()),
        "main_only_count": len(commits),
        "issues": issues,
        "unclassified": sorted(actual - expected),
        "no_longer_main_only": sorted(expected - actual),
        "baseline_unclassified": sorted(baseline - expected),
        "baseline_excess": sorted(expected - baseline),
        "commits": commits,
        "groups": plan["groups"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--work-ref", default="origin/work")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = inspect_inventory(args.repo, load_plan(args.plan), args.main_ref, args.work_ref)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(f"Inventory: {report['status']} (work-only={report['work_only_count']} main-only={report['main_only_count']})")
        for item in report["commits"]:
            print(f"  {item['sha'][:7]} [{', '.join(item['groups']) or 'UNCLASSIFIED'}] {item['subject']}")
        for issue in report["issues"]:
            print(f"  REFRESH: {issue}")
        print("Proposal/coverage check only; no fetch, merge, cherry-pick, checkout or file change performed.")
        print("Refresh remote refs separately. This is not semantic verification or release approval.")
    return 0 if report["status"] == "consistent" else 1


if __name__ == "__main__":
    raise SystemExit(main())
