from __future__ import annotations

import json
from pathlib import Path

from .event_definition import EventDefinition


class EventRepository:
    """Load and validate the event catalog shared by game tools."""

    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path.resolve()

    def load(self) -> tuple[EventDefinition, ...]:
        raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("Unsupported event schema version")
        raw_events = raw.get("events")
        if not isinstance(raw_events, list) or not raw_events:
            raise ValueError("events must be a non-empty list")
        events = []
        seen_ids = set()
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                raise ValueError("Each event must be an object")
            event_id = str(raw_event.get("id", "")).strip()
            label = str(raw_event.get("label", "")).strip()
            if not event_id or not label:
                raise ValueError("Event id and label are required")
            if event_id in seen_ids:
                raise ValueError(f"Duplicate event id: {event_id}")
            raw_tag = raw_event.get("required_tag")
            required_tag = str(raw_tag).strip() if raw_tag is not None else None
            if required_tag == "":
                required_tag = None
            terminal = raw_event.get("terminal", False)
            if not isinstance(terminal, bool):
                raise ValueError(f"Event terminal must be boolean: {event_id}")
            events.append(
                EventDefinition(
                    id=event_id,
                    label=label,
                    terminal=terminal,
                    required_tag=required_tag,
                )
            )
            seen_ids.add(event_id)
        return tuple(events)

    @staticmethod
    def validate_required_tags(
        events: tuple[EventDefinition, ...],
        available_tags: list[str],
    ) -> None:
        available = set(available_tags)
        missing = sorted(
            event.required_tag
            for event in events
            if event.required_tag is not None and event.required_tag not in available
        )
        if missing:
            raise ValueError(f"Event tags are missing from placements: {', '.join(missing)}")
