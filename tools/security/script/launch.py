"""Serialize project venv preparation; verify again before launching a fixed app."""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCK_NAME = ".venv-setup.lock"
ENTRIES = {
    "game": ("game.py", "import pygame", False),
    "engine": ("engine_app.py", "import pygame; import PIL", True),
    "object-editor": ("object_editor.py", "import pygame; import PIL", True),
    "conversation-editor": ("conversation_editor.py", "import tkinter", True),
}


def process_alive(pid: int) -> bool | None:
    """Query only; missing permissions and PID reuse never authorize recovery."""
    if os.name == "nt":
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, pid)
        if not handle:
            return False if ctypes.get_last_error() == 87 else None
        try:
            state = kernel.WaitForSingleObject(handle, 0)
            return {0: False, 258: True}.get(state)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # POSIX query only; never use os.kill for Windows ownership checks.
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return None


def lock_path(root: Path) -> Path:
    path = root.resolve() / LOCK_NAME
    if path.resolve() != path:
        raise RuntimeError("Setup lock redirects outside its project location; inspect manually")
    return path


def read_owner(path: Path) -> dict | None:
    """Read bounded diagnostic metadata; it is not proof that no child remains."""
    files = list(islice(path.glob("owner-*.json"), 2))
    if len(files) != 1 or files[0].resolve().parent != path:
        return None
    try:
        with files[0].open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            return None
        owner = json.loads(raw)
        if not isinstance(owner, dict):
            return None
        token, pid = owner.get("token"), owner.get("pid")
        if (
            not isinstance(token, str)
            or not re.fullmatch(r"[0-9a-f]{32}", token)
            or files[0].name != f"owner-{token}.json"
            or type(pid) is not int
            or not 0 < pid < 2**31
        ):
            return None
        return {"token": token, "pid": pid}
    except (OSError, ValueError):
        return None


def retry_permission(operation) -> None:
    """Bound Windows sharing violations without masking persistent failures."""
    deadline = time.monotonic() + 1
    while True:
        try:
            operation()
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.025)


def release_lock(path: Path, owner: dict) -> None:
    """Remove only this token's metadata and the now-empty directory; no rmtree."""
    if read_owner(path) != owner:
        raise RuntimeError("Setup lock ownership changed or is unknown; lock retained")
    retry_permission((path / f"owner-{owner['token']}.json").unlink)
    retry_permission(path.rmdir)


class SetupLock:
    """Persistent project lock: crashes never silently unlock a surviving pip child."""

    def __init__(self, root: Path, timeout: float = 300) -> None:
        if not math.isfinite(timeout) or not 0 <= timeout <= 3600:
            raise ValueError("lock timeout must be finite and between 0 and 3600 seconds")
        self.path = lock_path(root)
        self.timeout = timeout
        self.owner = {"token": uuid.uuid4().hex, "pid": os.getpid()}

    def __enter__(self) -> SetupLock:
        deadline = time.monotonic() + self.timeout
        announced = False
        while True:
            lock_path(self.path.parent)
            try:
                self.path.mkdir()
                break
            except FileExistsError:
                if not self.path.is_dir():
                    if not self.path.exists():
                        continue  # The previous owner released between mkdir and inspection.
                    raise RuntimeError(
                        "Setup lock path is not a directory; inspect manually"
                    ) from None
                owner = read_owner(self.path)
                if owner and process_alive(owner["pid"]) is False:
                    if read_owner(self.path) != owner:
                        continue  # Do not diagnose a previous owner's released snapshot.
                    raise RuntimeError(
                        f"Interrupted setup: owner PID {owner['pid']}, token {owner['token']}. "
                        "A child may still be running. Confirm all setup processes stopped, "
                        "then use --recover-lock TOKEN --confirm-no-setup-processes."
                    ) from None
                if time.monotonic() >= deadline:
                    detail = (
                        f"PID {owner['pid']}, token {owner['token']}" if owner else "unknown owner"
                    )
                    raise TimeoutError(
                        f"Setup lock timeout ({detail}); nothing was removed. "
                        "See docs/venv起動機能説明書.md for manual investigation."
                    ) from None
                if not announced:
                    print("Waiting for project setup to finish...", flush=True)
                    announced = True
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        # A crash while writing also leaves the directory for manual investigation.
        metadata = {**self.owner, "created_utc": datetime.now(timezone.utc).isoformat()}
        own_file = self.path / f"owner-{self.owner['token']}.json"
        temporary = self.path / f"metadata-{self.owner['token']}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(metadata, stream)
            temporary.replace(own_file)
        except Exception as error:
            # No child has started. Remove only our partial metadata and empty directory.
            # BaseException (including Ctrl+C) deliberately leaves evidence intact.
            try:
                retry_permission(lambda: temporary.unlink(missing_ok=True))
                retry_permission(lambda: own_file.unlink(missing_ok=True))
                retry_permission(self.path.rmdir)
            except OSError as cleanup_error:
                print(
                    f"Metadata error: {error}; cleanup failed: {cleanup_error}; lock retained",
                    file=sys.stderr,
                )
            raise
        return self

    def __exit__(self, kind, value, traceback) -> None:
        if kind is not None and (
            not issubclass(kind, Exception) or issubclass(kind, subprocess.TimeoutExpired)
        ):
            return  # Interrupt/timeout: a child may remain; do not infer safe recovery.
        release_lock(self.path, self.owner)


def recover_lock(root: Path, token: str, confirmed: bool) -> None:
    """Explicit operator recovery, never an automatic response to age or dead PID."""
    if not confirmed or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("Recovery requires the exact token and --confirm-no-setup-processes")
    path = lock_path(root)
    owner = read_owner(path)
    if owner is None or owner["token"] != token:
        raise RuntimeError("Recovery token does not match a known owner; nothing removed")
    if process_alive(owner["pid"]) is not False:
        raise RuntimeError("Owner PID is active or unknown; recovery refused")
    release_lock(path, owner)


def python_path(root: Path, windowed: bool = False) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / ("pythonw.exe" if windowed else "python.exe")
    return root / ".venv" / "bin" / "python"


def run(command: list[str], root: Path, *, timeout: float | None = None) -> None:
    subprocess.run(command, cwd=root, check=True, timeout=timeout)


def prepare(root: Path, entry: str) -> None:
    """Called only inside SetupLock; subprocess completion precedes normal unlock."""
    python = python_path(root)
    if not python.is_file():
        run([sys.executable, "-I", "-m", "venv", ".venv"], root, timeout=300)
    bootstrap = str(root / "tools" / "security" / "script" / "bootstrap.py")
    run([str(python), "-I", "-B", bootstrap, "--apply"], root, timeout=300)
    probe = subprocess.run(
        [str(python), "-I", "-B", "-c", ENTRIES[entry][1]],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    if probe.returncode:
        if entry == "conversation-editor":
            raise RuntimeError(
                "Tkinter is unavailable; repair the selected base Python installation"
            )
        run(
            [str(python), "-I", "-m", "pip", "install", "-r", "requirements.txt"],
            root,
            timeout=300,
        )


def launch(root: Path, entry: str, timeout: float = 300, fullscreen: bool = False) -> None:
    with SetupLock(root, timeout):
        prepare(root, entry)
    # This post-lock check preserves the existing fail-closed launch gate.
    run(
        [str(python_path(root)), "-I", "-B", str(root / "tools/security/script/bootstrap.py")], root
    )
    app, _, windowed = ENTRIES[entry]
    python = python_path(root, windowed)
    if not python.is_file():
        raise FileNotFoundError(f"Application interpreter missing: {python}")
    command = [str(python), str(root / app)]
    if fullscreen:
        command.append("--fullscreen")
    if windowed:
        subprocess.Popen(command, cwd=root, close_fds=True, start_new_session=os.name != "nt")
    else:
        run(command, root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entry", choices=ENTRIES, nargs="?")
    parser.add_argument("--lock-timeout", type=float, default=300)
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--recover-lock", metavar="TOKEN")
    parser.add_argument("--confirm-no-setup-processes", action="store_true")
    args = parser.parse_args(argv)
    if args.recover_lock:
        if args.entry or args.fullscreen or not args.confirm_no_setup_processes:
            parser.error("recovery needs confirmation and cannot be combined with app launch")
    elif (
        not args.entry
        or args.confirm_no_setup_processes
        or (args.fullscreen and args.entry != "game")
    ):
        parser.error("select an app; --fullscreen is only for game")
    try:
        if args.recover_lock:
            recover_lock(ROOT, args.recover_lock, args.confirm_no_setup_processes)
        else:
            launch(ROOT, args.entry, args.lock_timeout, args.fullscreen)
        return 0
    except KeyboardInterrupt:
        print("Setup interrupted; inspect the retained lock before recovery.", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as error:
        print(
            f"Setup command timed out: {error}. Lock retained; confirm all setup processes "
            "stopped before manual recovery. See docs/venv起動機能説明書.md.",
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Project launch failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
