"""Check tooling floors; explicitly repair only the selected Python environment."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path

# Python security announcement and PyPI wheel metadata: see ../README.md.
PACKAGES = {
    "pip": (
        (26, 2, 2),
        "https://files.pythonhosted.org/packages/3f/06/"
        "3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/"
        "pip-26.2.2-py3-none-any.whl"
        "#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70",
    ),
    "certifi": (
        (2026, 10, 19),
        "https://files.pythonhosted.org/packages/c4/51/"
        "29046e48f693c54e5b7412216d447a1d8362c9653148d98c02cdf65fa733/"
        "certifi-2026.10.19-py3-none-any.whl"
        "#sha256=42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b",
    ),
}


def installed_versions() -> dict[str, str | None]:
    result = {}
    for name in PACKAGES:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def pending_updates(versions: dict[str, str | None]) -> list[str]:
    pending = []
    for name, (minimum, _) in PACKAGES.items():
        value = versions[name]
        if value is not None and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value):
            raise ValueError(f"Unsupported {name} version {value!r}; inspect manually")
        if value is None or tuple(map(int, value.split("."))) < minimum:
            pending.append(name)
    return pending


def ensure_tooling(apply: bool = False, managed_runtime: bool = False) -> dict[str, str | None]:
    versions = installed_versions()
    pending = pending_updates(versions)
    if apply and pending:
        if sys.prefix == sys.base_prefix and not managed_runtime:
            raise ValueError("Use a venv; base Python updates require --managed-runtime")
        if versions["pip"] is None:
            raise ValueError("pip is missing; prepare pip with ensurepip before bootstrapping")
        for name in pending:  # pip first, before any other package download.
            subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "pip",
                    "--isolated",
                    "--disable-pip-version-check",
                    "install",
                    "--no-index",
                    "--no-deps",
                    f"{name} @ {PACKAGES[name][1]}",
                ],
                check=True,
                timeout=120,
                stdout=sys.stderr,
            )
        versions = installed_versions()
        if pending_updates(versions):
            raise RuntimeError("Tooling remains below the required versions after installation")
    return versions


def inspect_bundles(versions: dict[str, str | None]) -> dict[str, dict[str, str] | None]:
    bundles = {}
    for name, module in (("pip", "pip._vendor.certifi"), ("certifi", "certifi")):
        if versions[name] is None:
            bundles[name] = None
            continue
        path = Path(importlib.import_module(module).where()).resolve()
        bundles[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return bundles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Repair outdated/missing tooling")
    parser.add_argument(
        "--managed-runtime", action="store_true", help="Allow CI-managed base Python"
    )
    args = parser.parse_args(argv)
    try:
        versions = ensure_tooling(args.apply, args.managed_runtime)
        print(
            json.dumps(
                {
                    "python": sys.executable,
                    "versions": versions,
                    "bundles": inspect_bundles(versions),
                    "chains_verified": False,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1 if pending_updates(versions) else 0
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        print(f"Python tooling check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
