"""配布 zip と SHA256SUMS を、固定した一覧から同じ内容で再生成する。

使い方:
    python tools/release/build_release.py --output-dir dist

zip の中身は release_manifest.json の一覧だけで決まる。ファイル順・時刻・権限を
固定するため、同じ入力からは同じバイト列の zip ができる。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = Path(__file__).with_name("release_manifest.json")
# zip が表せる最小の日時。ビルド時刻を入れないために固定する。
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o100644
CHUNK_SIZE = 1024 * 1024


class ReleaseBuildError(Exception):
    pass


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    archives = payload.get("archives") if isinstance(payload, dict) else None
    if not isinstance(archives, dict) or not archives:
        raise ReleaseBuildError("manifest に archives がありません")
    for name, spec in archives.items():
        include = spec.get("include") if isinstance(spec, dict) else None
        if not isinstance(include, list) or not include:
            raise ReleaseBuildError(f"{name}: include が空です")
        for entry in include:
            if not isinstance(entry, str) or entry.startswith("/") or ".." in Path(entry).parts:
                raise ReleaseBuildError(f"{name}: 不正なパスです: {entry!r}")
    return payload


def read_version(root: Path) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not version or any(ch in version for ch in "/\\ "):
        raise ReleaseBuildError("VERSION が不正です")
    return version


def expand_entries(root: Path, include: list[str], manifest: dict) -> list[str]:
    skip_dirs = set(manifest.get("exclude_dir_names", []))
    skip_suffixes = tuple(manifest.get("exclude_suffixes", []))
    found: set[str] = set()
    for entry in include:
        target = root / entry
        if target.is_symlink():
            raise ReleaseBuildError(f"シンボリックリンクは含められません: {entry}")
        if target.is_file():
            found.add(entry)
        elif target.is_dir():
            for path in target.rglob("*"):
                relative = path.relative_to(root)
                if path.is_symlink():
                    raise ReleaseBuildError(f"シンボリックリンクは含められません: {relative}")
                if not path.is_file() or skip_dirs.intersection(relative.parts):
                    continue
                if relative.name.endswith(skip_suffixes):
                    continue
                found.add(relative.as_posix())
        else:
            raise ReleaseBuildError(f"一覧のパスが存在しません: {entry}")
    return sorted(found)


def build_archive(root: Path, files: list[str], prefix: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for relative in files:
            info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=FIXED_DATE_TIME)
            info.create_system = 3
            info.external_attr = FILE_MODE << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, (root / relative).read_bytes(), compresslevel=9)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_all(root: Path, manifest_path: Path, output_dir: Path) -> list[Path]:
    manifest = load_manifest(manifest_path)
    version = read_version(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    built: list[Path] = []
    for name, spec in sorted(manifest["archives"].items()):
        files = expand_entries(root, spec["include"], manifest)
        prefix = f"obake-no-sumika-{name}-v{version}"
        destination = output_dir / f"{prefix}.zip"
        build_archive(root, files, prefix, destination)
        built.append(destination)
    sums = "".join(f"{sha256_of(path)}  {path.name}\n" for path in built)
    (output_dir / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    return built


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "dist")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    try:
        built = build_all(args.root.resolve(), args.manifest, args.output_dir)
    except (ReleaseBuildError, OSError, ValueError) as error:
        print(f"release build failed: {error}", file=sys.stderr)
        return 1
    for path in built:
        print(f"{sha256_of(path)}  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
