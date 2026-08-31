from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CharacterDefinition:
    """Validated visual and movement settings for one character."""

    id: str
    display_name: str
    image: Path
    start_x: int
    start_y: int
    display_height: int
    personality: float
    native_facing: int
    bubble_y_offset: int
