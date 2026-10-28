"""Check tooling floors; explicitly repair only the selected Python environment."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import re
import ssl
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
MAX_BUNDLE_BYTES = 8 * 1024 * 1024
# certifi 69494a7..662df63 (2026.10.19): only this root remains removed.
# Exact DER identity, not a name/SPKI/chain or OS trust-store guarantee.
DISTRUSTED_ROOTS = {
    "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b": "emSign ECC Root CA - G3",
}


def inspect_ca_bundle(path: Path) -> dict[str, object]:
    """Parse one bounded snapshot without OS roots, network or file changes."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BUNDLE_BYTES + 1)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError(f"CA bundle exceeds {MAX_BUNDLE_BYTES} bytes: {path}")
    begin, end = b"-----BEGIN CERTIFICATE-----", b"-----END CERTIFICATE-----"
    if not raw.count(begin) or raw.count(begin) != raw.count(end):
        raise ValueError(f"Empty or incomplete PEM CA bundle: {path}")
    segments = raw.split(begin)
    blocks, outside = [], [segments[0]]
    for segment in segments[1:]:
        body, marker, suffix = segment.partition(end)
        if not marker:
            raise ValueError(f"Incomplete PEM CA bundle: {path}")
        if b"-----BEGIN " in body or b"-----END " in body:
            raise ValueError(f"Nested PEM block in CA bundle: {path}")
        blocks.append(begin + body + marker)
        outside.append(suffix)
    if any(b"-----BEGIN " in text or b"-----END " in text for text in outside):
        raise ValueError(f"Unsupported PEM block in CA bundle: {path}")
    # Validate X.509 data, not just base64. A new context does not load OS roots.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=b"\n".join(blocks).decode("ascii"))
    # Hash parsed CA DER: OpenSSL accepts trailing bytes inside a PEM payload,
    # which must not disguise the same loaded root behind a different raw hash.
    certificates = context.get_ca_certs(binary_form=True)
    if not certificates:
        raise ValueError(f"CA bundle contains no CA certificates: {path}")
    fingerprints = {hashlib.sha256(der).hexdigest() for der in certificates}
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "certificate_count": len(blocks),
        "ca_count": len(certificates),
        "known_roots_checked": len(DISTRUSTED_ROOTS),
        "distrusted_roots": [
            {"sha256": digest, "name": DISTRUSTED_ROOTS[digest]}
            for digest in sorted(fingerprints & DISTRUSTED_ROOTS.keys())
        ],
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


def inspect_bundles(versions: dict[str, str | None]) -> dict[str, dict[str, object] | None]:
    bundles = {}
    for name, module in (("pip", "pip._vendor.certifi"), ("certifi", "certifi")):
        if versions[name] is None:
            bundles[name] = None
            continue
        path = Path(importlib.import_module(module).where()).resolve()
        bundles[name] = inspect_ca_bundle(path)
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
        bundles = inspect_bundles(versions)
        print(
            json.dumps(
                {
                    "python": sys.executable,
                    "versions": versions,
                    "bundles": bundles,
                    "chains_verified": False,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        blocked = any(bundle and bundle["distrusted_roots"] for bundle in bundles.values())
        return 1 if pending_updates(versions) or blocked else 0
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        print(f"Python tooling check failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
