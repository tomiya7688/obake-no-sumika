from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventDefinition:
    """Metadata for one event that can be selected by a conversation."""

    id: str
    label: str
    terminal: bool
    required_tag: str | None
