from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EditorDefinition:
    """One editor exposed by an engine project."""

    id: str
    label: str
    script: Path
