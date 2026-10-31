"""Build the release zips and SHA256SUMS from a git revision.

Files are read from the given revision with git, never from the working tree,
so uncommitted edits in a shared checkout cannot leak into a release. The zips
are reproducible: sorted entries, a fixed timestamp and fixed permissions.

    python tools/release/script/package.py --ref v0.3.0 --out dist
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from fnmatch import fnmatchcase
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = PROJECT_ROOT / "tools/release/manifest.json"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
# The repository stores LF; cmd.exe can misread labels and goto in LF batch files.
CRLF_SUFFIXES = (".bat", ".cmd")


class PackageError(Exception):
    """The release cannot be built as requested."""


def git_bytes(repo: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(["git", *args], cwd=repo, capture_output=True)
    except OSError as exc:
        raise PackageError(f"cannot run git: {exc}") from None
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise PackageError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def tracked_files(repo: Path, ref: str) -> list[str]:
    raw = git_bytes(repo, "ls-tree", "-r", "-z", "--name-only", "--end-of-options", ref)
    return sorted(name for name in raw.decode("utf-8").split("\0") if name)


def select_files(tracked: list[str], patterns: list[str]) -> list[str]:
    """Files matching any pattern; every pattern must match at least one file."""
    selected: set[str] = set()
    for pattern in patterns:
        matches = [name for name in tracked if fnmatchcase(name, pattern)]
        if not matches:
            raise PackageError(f"manifest pattern matches no tracked file: {pattern}")
        selected.update(matches)
    return sorted(selected)


def load_manifest(path: Path = MANIFEST) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not data.get("packages"):
        raise PackageError(f"unsupported release manifest: {path}")
    return data


def build_zip(repo: Path, ref: str, files: list[str], target: Path, folder: str) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            info = zipfile.ZipInfo(f"{folder}/{name}", date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            data = git_bytes(repo, "show", f"{ref}:{name}")
            if name.lower().endswith(CRLF_SUFFIXES):
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            archive.writestr(info, data)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def build(
    repo: Path, ref: str, out: Path, manifest: dict, version: str | None = None
) -> list[Path]:
    """Build every package plus SHA256SUMS into out; return the written paths."""
    tracked = tracked_files(repo, ref)
    if version is None:
        version = git_bytes(repo, "show", f"{ref}:VERSION").decode("utf-8").strip()
    if not version or any(char in version for char in '/\\:*?"<>| '):
        raise PackageError(f"invalid version: {version!r}")
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for package, spec in sorted(manifest["packages"].items()):
        folder = f"{manifest['name']}-v{version}-{package}"
        target = out / f"{folder}.zip"
        build_zip(repo, ref, select_files(tracked, spec["include"]), target, folder)
        written.append(target)
    sums = out / "SHA256SUMS"
    sums.write_text("".join(f"{sha256(path)}  {path.name}\n" for path in written), encoding="utf-8")
    return [*written, sums]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default="HEAD", help="git revision to package (tag or commit)")
    parser.add_argument("--out", type=Path, default=Path("dist"), help="output directory")
    parser.add_argument("--version", help="override the version read from VERSION at --ref")
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--manifest", type=Path, default=MANIFEST, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        paths = build(
            args.repo.resolve(), args.ref, args.out, load_manifest(args.manifest), args.version
        )
    except (PackageError, OSError, ValueError) as exc:
        print(f"package: {exc}", file=sys.stderr)
        return 2
    for path in paths:
        print(path.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
