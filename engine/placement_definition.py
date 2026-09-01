from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlacementDefinition:
    """One validated object placement in a room."""

    id: str
    name: str
    image: Path
    source: Path | None
    tag: str
    x: int
    y: int
    width: int
    visible: bool
