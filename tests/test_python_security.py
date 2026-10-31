from __future__ import annotations

import hashlib
import io
import json
import os
import re
import ssl
import subprocess
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.context.script.select_files import load_mapping, select_files
from tools.security.script import bootstrap

ROOT = Path(__file__).resolve().parents[1]
OLD = {"pip": "26.2.1", "certifi": None}
SAFE = {"pip": "26.2.2", "certifi": "2026.10.19"}
FIXTURES = ROOT / "tests/fixtures/security"


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class PythonSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        names = (
            "PIP_CERT",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "PIP_CONFIG_FILE",
        )
        self.environment = patch.dict(os.environ, dict.fromkeys(names, ""))
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_version_boundaries_and_unknown_formats(self) -> None:
        for pip in ("26.2", "26.2.1", None):
            self.assertEqual(bootstrap.pending_updates({**SAFE, "pip": pip}), ["pip"])
        for certifi in ("2026.10.18", "2026.7.22", None):
            self.assertEqual(bootstrap.pending_updates({**SAFE, "certifi": certifi}), ["certifi"])
        self.assertEqual(bootstrap.pending_updates(SAFE), [])
        self.assertEqual(bootstrap.pending_updates({"pip": "27.0", "certifi": "2027.1.1"}), [])
        for name in SAFE:
            for suffix in ("rc1", ".dev0", "+vendor", ".post1", "unknown"):
                value = SAFE[name] + suffix
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    bootstrap.pending_updates({**SAFE, name: value})
            with self.assertRaises(ValueError):
                bootstrap.pending_updates({**SAFE, name: ""})

    def test_wheel_hashes_match_reviewed_official_metadata(self) -> None:
        expected = {
            "pip": "fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70",
            "certifi": "42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b",
        }
        for name, digest in expected.items():
            url = bootstrap.PACKAGES[name][1]
            self.assertTrue(url.startswith("https://files.pythonhosted.org/packages/"))
            self.assertIn(f"/{name}-{SAFE[name]}-py3-none-any.whl#", url)
            self.assertEqual(url.split("#sha256=")[1], digest)

    def test_default_check_never_installs_and_reports_unverified_chains(self) -> None:
        with (
            patch.object(bootstrap, "installed_versions", return_value=OLD),
            patch.object(bootstrap, "inspect_bundles", return_value={}),
            patch.object(bootstrap.subprocess, "run") as run,
            redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(bootstrap.main([]), 1)
            self.assertFalse(json.loads(out.getvalue())["chains_verified"])
            run.assert_not_called()

    def test_apply_orders_updates_with_hashes_and_rechecks(self) -> None:
        with (
            patch.object(bootstrap, "installed_versions", side_effect=[OLD, SAFE]),
            patch.object(bootstrap.sys, "prefix", bootstrap.sys.base_prefix),
            patch.object(bootstrap.subprocess, "run") as run,
        ):
            self.assertEqual(bootstrap.ensure_tooling(True, True), SAFE)
            self.assertEqual(run.call_count, 2)
            for call, name in zip(run.call_args_list, ("pip", "certifi")):
                command = call.args[0]
                self.assertEqual(command[:4], [bootstrap.sys.executable, "-I", "-m", "pip"])
                self.assertEqual(command[-1], f"{name} @ {bootstrap.PACKAGES[name][1]}")
                self.assertEqual(len(command[-1].split("#sha256=")[1]), 64)
                self.assertIn("--no-index", command)
                self.assertIn("--no-deps", command)
                self.assertNotIn("--trusted-host", command)
                self.assertEqual(
                    call.kwargs, {"check": True, "timeout": 120, "stdout": bootstrap.sys.stderr}
                )

    def test_json_output_preserves_unicode_paths_on_ascii_streams(self) -> None:
        executable = "C:/\u4f4f\u51e6/\U0001f47b/python.exe"
        with io.TextIOWrapper(io.BytesIO(), encoding="ascii") as out:
            with (
                patch.object(bootstrap, "installed_versions", return_value=SAFE),
                patch.object(bootstrap, "inspect_bundles", return_value={}),
                patch.object(bootstrap.sys, "executable", executable),
                redirect_stdout(out),
            ):
                self.assertEqual(bootstrap.main([]), 0)
            out.flush()
            value = out.buffer.getvalue().decode("ascii")
            self.assertEqual(json.loads(value)["python"], executable)

    def test_missing_bundle_module_fails_closed(self) -> None:
        with (
            patch.object(bootstrap, "installed_versions", return_value=SAFE),
            patch.object(
                bootstrap.importlib, "import_module", side_effect=ImportError("missing CA")
            ),
            redirect_stderr(io.StringIO()) as err,
            redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(bootstrap.main([]), 2)
            self.assertIn("missing CA", err.getvalue())
            self.assertEqual(out.getvalue(), "")

    def test_newer_tooling_is_not_downgraded(self) -> None:
        newer = {"pip": "27.0", "certifi": "2027.1.1"}
        with (
            patch.object(bootstrap, "installed_versions", return_value=newer),
            patch.object(bootstrap.subprocess, "run") as run,
        ):
            self.assertEqual(bootstrap.ensure_tooling(True), newer)
            run.assert_not_called()

    def test_implicit_global_updates_and_missing_pip_are_rejected(self) -> None:
        with (
            patch.object(bootstrap, "installed_versions", return_value=OLD),
            patch.object(bootstrap.sys, "prefix", bootstrap.sys.base_prefix),
            patch.object(bootstrap.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "venv"):
                bootstrap.ensure_tooling(True)
            run.assert_not_called()
        with patch.object(bootstrap, "installed_versions", return_value={**OLD, "pip": None}):
            with self.assertRaisesRegex(ValueError, "ensurepip"):
                bootstrap.ensure_tooling(True, True)

    def test_failed_install_timeout_and_failed_recheck_are_nonzero(self) -> None:
        for error in (
            subprocess.CalledProcessError(1, "pip"),
            subprocess.TimeoutExpired("pip", 120),
        ):
            with (
                patch.object(bootstrap, "installed_versions", return_value=OLD),
                patch.object(bootstrap.subprocess, "run", side_effect=error),
                redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(bootstrap.main(["--apply", "--managed-runtime"]), 2)
        with (
            patch.object(bootstrap, "installed_versions", return_value=OLD),
            patch.object(bootstrap.subprocess, "run"),
        ):
            with self.assertRaisesRegex(RuntimeError, "remains"):
                bootstrap.ensure_tooling(True, True)

    def test_inspection_hashes_the_actual_where_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name in SAFE:
                paths[name] = Path(directory) / f"{name}-ca.pem"
                paths[name].write_bytes(
                    f"# {name} bundle\n".encode()
                    + (FIXTURES / "unaffected-emsign-c1.pem").read_bytes()
                )
            with patch.object(
                bootstrap.importlib,
                "import_module",
                side_effect=lambda module: SimpleNamespace(
                    where=lambda: str(paths["pip" if module == "pip._vendor.certifi" else module])
                ),
            ) as imports:
                result = bootstrap.inspect_bundles(SAFE)
            self.assertEqual(
                [call.args[0] for call in imports.call_args_list],
                ["pip._vendor.certifi", "certifi"],
            )
            for name, path in paths.items():
                self.assertEqual(result[name]["path"], str(path.resolve()))
                self.assertEqual(
                    result[name]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
                )
                self.assertEqual(result[name]["certificate_count"], 1)
                self.assertEqual(result[name]["known_roots_checked"], 1)
                self.assertEqual(result[name]["distrusted_roots"], [])
            self.assertNotEqual(result["pip"]["sha256"], result["certifi"]["sha256"])

    def test_public_fixtures_match_pinned_der_and_blocklist(self) -> None:
        expected = {
            "emsign-ecc-g3.pem": "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b",
            "unaffected-emsign-c1.pem": "125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f",
        }
        for filename, fingerprint in expected.items():
            raw = (FIXTURES / filename).read_text(encoding="ascii")
            self.assertEqual(hashlib.sha256(ssl.PEM_cert_to_DER_cert(raw)).hexdigest(), fingerprint)
        self.assertEqual(
            bootstrap.DISTRUSTED_ROOTS,
            {expected["emsign-ecc-g3.pem"]: "emSign ECC Root CA - G3"},
        )

    def test_der_matching_ignores_labels_and_pem_line_endings(self) -> None:
        bad = (FIXTURES / "emsign-ecc-g3.pem").read_bytes()
        safe = (FIXTURES / "unaffected-emsign-c1.pem").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CA 日本語.pem"
            for raw in (bad, b"# harmless label\n" + safe + bad.replace(b"\n", b"\r\n")):
                path.write_bytes(raw)
                result = bootstrap.inspect_ca_bundle(path)
                self.assertEqual(result["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(result["certificate_count"], 1 if raw == bad else 2)
                self.assertEqual(
                    result["distrusted_roots"],
                    [
                        {
                            "sha256": next(iter(bootstrap.DISTRUSTED_ROOTS)),
                            "name": "emSign ECC Root CA - G3",
                        }
                    ],
                )
                self.assertEqual(path.read_bytes(), raw)

    def test_bad_bundle_is_nonzero_even_at_safe_versions_without_install(self) -> None:
        for name in SAFE:
            for arguments in ([], ["--apply"]):
                with (
                    self.subTest(package=name, arguments=arguments),
                    patch.object(bootstrap, "installed_versions", return_value=SAFE),
                    patch.object(
                        bootstrap.importlib,
                        "import_module",
                        side_effect=lambda module: SimpleNamespace(
                            where=lambda: str(
                                FIXTURES
                                / (
                                    "emsign-ecc-g3.pem"
                                    if ("pip" if module.startswith("pip.") else module) == name
                                    else "unaffected-emsign-c1.pem"
                                )
                            )
                        ),
                    ),
                    patch.object(bootstrap.subprocess, "run") as run,
                    redirect_stdout(io.StringIO()) as out,
                ):
                    self.assertEqual(bootstrap.main(arguments), 1)
                    report = json.loads(out.getvalue())
                    self.assertFalse(report["chains_verified"])
                    self.assertEqual(len(report["bundles"][name]["distrusted_roots"]), 1)
                    run.assert_not_called()

    def test_trailing_der_data_cannot_disguise_a_loaded_distrusted_root(self) -> None:
        der = ssl.PEM_cert_to_DER_cert((FIXTURES / "emsign-ecc-g3.pem").read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trailing.pem"
            path.write_text(ssl.DER_cert_to_PEM_cert(der + b"trailing data"), encoding="ascii")
            result = bootstrap.inspect_ca_bundle(path)
        self.assertEqual(result["ca_count"], 1)
        self.assertEqual(len(result["distrusted_roots"]), 1)

    def test_invalid_empty_incomplete_or_oversized_ca_fails_closed(self) -> None:
        safe = (FIXTURES / "unaffected-emsign-c1.pem").read_bytes()
        invalid = b"-----BEGIN CERTIFICATE-----\nYmFk\n-----END CERTIFICATE-----\n"
        for raw in (
            b"",
            b"not a certificate",
            invalid,
            safe + invalid,
            safe + b"-----BEGIN CERTIFICATE-----",
            safe + b"-----END CERTIFICATE-----",
            safe + safe.replace(b"CERTIFICATE", b"TRUSTED CERTIFICATE"),
            safe + safe.replace(b"CERTIFICATE", b"X509 CERTIFICATE"),
            safe + safe.replace(b"CERTIFICATE", b"X509 CRL"),
            safe.replace(b"\n", b"\n-----BEGIN X509 CRL-----\n", 1),
            b"-----END CERTIFICATE-----\n-----BEGIN CERTIFICATE-----",
        ):
            with self.subTest(raw=raw[:35]), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "broken.pem"
                path.write_bytes(raw)
                with self.assertRaises((ValueError, ssl.SSLError)):
                    bootstrap.inspect_ca_bundle(path)
        with patch.object(bootstrap, "MAX_BUNDLE_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                bootstrap.inspect_ca_bundle(FIXTURES / "unaffected-emsign-c1.pem")
        self.assertEqual(bootstrap.MAX_BUNDLE_BYTES, 8 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boundary.pem"
            with patch.object(bootstrap, "MAX_BUNDLE_BYTES", len(safe)):
                path.write_bytes(safe)
                self.assertEqual(bootstrap.inspect_ca_bundle(path)["ca_count"], 1)
                path.write_bytes(safe + b"\n")
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    bootstrap.inspect_ca_bundle(path)
                with patch.object(Path, "open") as open_file:
                    read = open_file.return_value.__enter__.return_value.read
                    read.return_value = safe
                    bootstrap.inspect_ca_bundle(path)
                    read.assert_called_once_with(len(safe) + 1)

    def test_ca_parsing_never_loads_default_os_roots(self) -> None:
        with (
            patch.object(ssl, "create_default_context", side_effect=AssertionError("OS store")),
            patch.object(
                ssl.SSLContext, "load_default_certs", side_effect=AssertionError("OS store")
            ),
            patch.object(
                ssl.SSLContext, "set_default_verify_paths", side_effect=AssertionError("OS store")
            ),
            patch("socket.create_connection", side_effect=AssertionError("network")),
        ):
            result = bootstrap.inspect_ca_bundle(FIXTURES / "unaffected-emsign-c1.pem")
        self.assertEqual(result["distrusted_roots"], [])

    def test_empty_ca_environment_is_compatible(self) -> None:
        with patch.object(bootstrap, "inspect_ca_bundle") as inspect:
            self.assertEqual(bootstrap.inspect_ca_environment(), {})
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(bootstrap.inspect_ca_environment(), {})
            inspect.assert_not_called()

    def test_all_ca_environment_files_are_read_without_values_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory, working_directory(directory):
            path = Path(directory) / "個人情報のある CA.pem"
            raw = (FIXTURES / "unaffected-emsign-c1.pem").read_bytes()
            path.write_bytes(raw)
            values = {name: str(path) for name in bootstrap.CA_FILE_ENV}
            values["SSL_CERT_FILE"] = path.name
            with (
                patch.dict(os.environ, values),
                patch("socket.create_connection", side_effect=AssertionError("network")),
                patch.object(
                    ssl.SSLContext, "load_default_certs", side_effect=AssertionError("OS")
                ),
                patch.object(
                    ssl.SSLContext, "set_default_verify_paths", side_effect=AssertionError("OS")
                ),
            ):
                result = bootstrap.inspect_ca_environment()
                self.assertEqual({name: os.environ[name] for name in values}, values)
            self.assertEqual(set(result), set(bootstrap.CA_FILE_ENV))
            for item in result.values():
                self.assertEqual(item["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(item["ca_count"], 1)
                self.assertEqual(item["distrusted_roots"], [])
                self.assertNotIn("path", item)
            self.assertNotIn(path.name, json.dumps(result, ensure_ascii=False))
            self.assertEqual(path.read_bytes(), raw)

    def test_pip_config_override_stops_without_reading_or_exposing_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "private-pip.ini"
            raw = b"[global]\ncert = secret-ca.pem\nindex-url = https://private.invalid\n"
            config.write_bytes(raw)
            for value in (str(config), str(config.with_suffix(".missing")), " ", os.devnull):
                for arguments in ([], ["--apply"], ["--apply", "--managed-runtime"]):
                    with (
                        self.subTest(value=value, arguments=arguments),
                        patch.dict(os.environ, {"PIP_CONFIG_FILE": value}),
                        patch.object(bootstrap, "ensure_tooling") as ensure,
                        patch.object(Path, "open", side_effect=AssertionError("must not read")),
                        patch.object(bootstrap.subprocess, "run") as run,
                        redirect_stdout(io.StringIO()) as out,
                        redirect_stderr(io.StringIO()) as err,
                    ):
                        self.assertEqual(bootstrap.main(arguments), 2)
                        ensure.assert_not_called()
                        run.assert_not_called()
                        self.assertEqual(out.getvalue(), "")
                        self.assertEqual(
                            err.getvalue(),
                            "Python tooling check failed: PIP_CONFIG_FILE requires a manual "
                            "pip configuration audit; value omitted\n",
                        )
            self.assertEqual(config.read_bytes(), raw)

    def test_empty_or_unset_pip_config_keeps_existing_update_path(self) -> None:
        for value in (None, ""):
            with (
                self.subTest(value=value),
                patch.dict(os.environ),
                patch.object(bootstrap, "ensure_tooling", return_value=SAFE) as ensure,
                patch.object(bootstrap, "inspect_bundles", return_value={}),
                redirect_stdout(io.StringIO()),
            ):
                os.environ.pop("PIP_CONFIG_FILE", None)
                if value is not None:
                    os.environ["PIP_CONFIG_FILE"] = value
                self.assertEqual(bootstrap.main(["--apply"]), 0)
                ensure.assert_called_once_with(True, False)

    def test_environment_bad_root_stops_before_updates(self) -> None:
        path = FIXTURES / "emsign-ecc-g3.pem"
        for name in ("PIP_CERT", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE"):
            for arguments in ([], ["--apply", "--managed-runtime"]):
                with (
                    self.subTest(name=name, arguments=arguments),
                    patch.dict(os.environ, {name: str(path)}),
                    patch.object(bootstrap, "installed_versions", return_value=OLD),
                    patch.object(bootstrap, "ensure_tooling", return_value=SAFE) as ensure,
                    patch.object(bootstrap, "inspect_bundles", return_value={}),
                    patch.object(bootstrap.subprocess, "run") as run,
                    redirect_stdout(io.StringIO()) as out,
                ):
                    self.assertEqual(bootstrap.main(arguments), 1)
                    ensure.assert_not_called()
                    run.assert_not_called()
                    report = json.loads(out.getvalue())
                    self.assertFalse(report["chains_verified"])
                    self.assertEqual(
                        len(report["environment_bundles"][name]["distrusted_roots"]), 1
                    )
                    self.assertNotIn(str(path), out.getvalue())
                    self.assertNotIn(path.name, out.getvalue())
                    self.assertNotIn("path", report["environment_bundles"][name])

    def test_invalid_ca_environment_stops_before_updates_without_leaking_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "private-secret.pem"
            bad.write_bytes(b"not a certificate")
            for name in (*bootstrap.CA_FILE_ENV, "SSL_CERT_DIR"):
                for case, value in enumerate(
                    (str(bad), str(bad.with_suffix(".missing")), directory)
                ):
                    for arguments in ([], ["--apply"]):
                        with (
                            self.subTest(name=name, case=case, arguments=arguments),
                            patch.dict(os.environ, {name: value}),
                            patch.object(bootstrap, "ensure_tooling") as ensure,
                            patch.object(bootstrap.subprocess, "run") as run,
                            redirect_stdout(io.StringIO()) as out,
                            redirect_stderr(io.StringIO()) as err,
                        ):
                            self.assertEqual(bootstrap.main(arguments), 2)
                            ensure.assert_not_called()
                            run.assert_not_called()
                            self.assertEqual(out.getvalue(), "")
                            self.assertIn(name, err.getvalue())
                            self.assertNotIn(value, err.getvalue())

    def test_safe_environment_is_audited_before_allowing_updates(self) -> None:
        path = FIXTURES / "unaffected-emsign-c1.pem"
        inspect = bootstrap.inspect_ca_bundle
        order = []

        def audit(path):
            order.append("audit")
            return inspect(path)

        def update(apply, managed):
            self.assertTrue(apply)
            self.assertFalse(managed)
            order.append("update")
            return SAFE

        with (
            patch.dict(os.environ, {name: str(path) for name in bootstrap.CA_FILE_ENV}),
            patch.object(bootstrap, "inspect_ca_bundle", side_effect=audit),
            patch.object(bootstrap, "ensure_tooling", side_effect=update),
            patch.object(bootstrap, "inspect_bundles", return_value={}),
            redirect_stdout(io.StringIO()) as out,
        ):
            self.assertEqual(bootstrap.main(["--apply"]), 0)
            self.assertEqual(order, ["audit"] * 4 + ["update"])
            self.assertEqual(len(json.loads(out.getvalue())["environment_bundles"]), 4)

    def test_ca_environment_errors_redact_parser_details(self) -> None:
        secret = "private-path-with-secret"
        with (
            patch.dict(os.environ, {"PIP_CERT": secret}),
            patch.object(Path, "is_file", return_value=True),
            patch.object(bootstrap, "inspect_ca_bundle", side_effect=OSError(secret)),
            patch.object(bootstrap, "ensure_tooling") as ensure,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as err,
        ):
            self.assertEqual(bootstrap.main(["--apply"]), 2)
            self.assertIn("PIP_CERT", err.getvalue())
            self.assertNotIn(secret, err.getvalue())
            ensure.assert_not_called()

    def test_mixed_or_whitespace_ca_environment_fails_before_updates(self) -> None:
        for fixture in ("unaffected-emsign-c1.pem", "emsign-ecc-g3.pem"):
            with (
                self.subTest(fixture=fixture),
                patch.dict(os.environ, {"PIP_CERT": str(FIXTURES / fixture), "SSL_CERT_FILE": " "}),
                patch.object(bootstrap, "ensure_tooling") as ensure,
                redirect_stdout(io.StringIO()) as out,
                redirect_stderr(io.StringIO()) as err,
            ):
                self.assertEqual(bootstrap.main(["--apply"]), 2)
                self.assertEqual(out.getvalue(), "")
                self.assertIn("SSL_CERT_FILE", err.getvalue())
                ensure.assert_not_called()

    def test_ca_environment_path_resolution_errors_are_redacted(self) -> None:
        with (
            patch.dict(os.environ, {"PIP_CERT": "private-value"}),
            patch.object(Path, "resolve", side_effect=RuntimeError("private-value")),
            patch.object(bootstrap, "ensure_tooling") as ensure,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()) as err,
        ):
            self.assertEqual(bootstrap.main(["--apply"]), 2)
            self.assertIn("PIP_CERT", err.getvalue())
            self.assertNotIn("private-value", err.getvalue())
            ensure.assert_not_called()

    def test_ci_bootstraps_each_job_before_dependency_downloads(self) -> None:
        workflow = (ROOT / ".github/workflows/work-ci.yml").read_text(encoding="utf-8")
        # A following job must never satisfy another job's bootstrap assertion.
        workflow += "\n  later_job:\n    sentinel: not-this-job\n"
        command = "python -I -B tools/security/script/bootstrap.py --apply --managed-runtime"
        for name in ("ruff_lint", "validate"):
            job = re.search(rf"(?ms)^  {name}:\n(.*?)(?=^  [\w-]+:[ \t]*$|\Z)", workflow)[1]
            self.assertNotIn("sentinel", job)
            self.assertLess(job.index(command), job.index("python -m pip install"))
            check = "run: python -I -B tools/security/script/bootstrap.py\n"
            self.assertGreater(job.index(check), job.rindex("python -m pip install"))
            self.assertRegex(
                job,
                rf"(?m)^      - name: Verify Python tooling after dependencies\n"
                rf"        {re.escape(check)}(?:[ \t]*\n)*(?=      - |\Z)",
            )
        result = select_files(["tools/security/script/bootstrap.py"], load_mapping())
        self.assertIn("tests/test_python_security.py", result["tests"])
        self.assertIn("tools/security/README.md", result["related_files"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])


if __name__ == "__main__":
    unittest.main()
