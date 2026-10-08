"""Use the launcher's Godot discovery; only an unconfigured absence is optional."""

from __future__ import annotations

import os
from pathlib import Path

from engine.godot_runner import resolve_godot


def find_test_godot() -> Path | None:
    """Return None when Godot is not installed, but fail on an invalid GODOT_BIN."""
    try:
        return resolve_godot()
    except FileNotFoundError:
        if "GODOT_BIN" in os.environ:
            raise
        return None
