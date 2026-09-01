from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationDefinition:
    """One weighted sequence of speech, movement, object, and event steps."""

    weight: float
    steps: tuple[dict[str, str], ...]
