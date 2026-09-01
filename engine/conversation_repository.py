from __future__ import annotations

import json
from pathlib import Path

from .conversation_definition import ConversationDefinition


class ConversationRepository:
    """Normalize, load, and atomically save a conversation deck."""

    def __init__(
        self,
        data_path: Path,
        speaker_ids: tuple[str, ...],
        actor_ids: tuple[str, ...],
        event_ids: tuple[str, ...],
    ) -> None:
        self.data_path = data_path.resolve()
        self.speaker_ids = speaker_ids
        self.actor_ids = actor_ids
        self.event_ids = event_ids

    def load(self) -> tuple[ConversationDefinition, ...]:
        try:
            raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ()
        if not isinstance(raw, list):
            return ()
        definitions = []
        for raw_item in raw:
            definition = self._parse_entry(raw_item, strict=False)
            if definition is not None:
                definitions.append(definition)
        return tuple(definitions)

    def load_editable(self) -> list[dict[str, object]]:
        return [self._serialize(definition) for definition in self.load()]

    def save_editable(self, editable: list[dict[str, object]]) -> None:
        if not editable:
            raise ValueError("At least one conversation is required")
        definitions = []
        for index, raw_item in enumerate(editable, 1):
            definition = self._parse_entry(raw_item, strict=True)
            if definition is None:
                raise ValueError(f"Conversation {index} is invalid")
            definitions.append(definition)
        payload = [self._serialize(definition) for definition in definitions]
        temporary = self.data_path.with_suffix(self.data_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.data_path)

    def normalize_step(self, raw: object) -> dict[str, str] | None:
        if not isinstance(raw, dict):
            return None
        step_type = str(raw.get("type", "say"))
        if step_type == "say":
            speaker = str(raw.get("speaker", self.speaker_ids[0] if self.speaker_ids else ""))
            text = " ".join(str(raw.get("text", "")).split())
            if speaker in self.speaker_ids and text:
                return {"type": "say", "speaker": speaker, "text": text}
        elif step_type in ("move", "take", "put"):
            actor = str(raw.get("actor", self.actor_ids[0] if self.actor_ids else ""))
            tag = str(raw.get("tag", "")).strip()
            if actor in self.actor_ids and tag:
                return {"type": step_type, "actor": actor, "tag": tag}
        elif step_type == "event":
            event_id = str(raw.get("event", ""))
            if event_id in self.event_ids:
                return {"type": "event", "event": event_id}
        return None

    def _parse_entry(
        self, raw: object, strict: bool
    ) -> ConversationDefinition | None:
        if not isinstance(raw, dict):
            if strict:
                raise ValueError("Each conversation must be an object")
            return None
        if isinstance(raw.get("steps"), list):
            raw_steps = raw["steps"]
        else:
            raw_steps = self._legacy_steps(raw)
        steps = []
        for raw_step in raw_steps:
            step = self.normalize_step(raw_step)
            if step is None:
                if strict:
                    raise ValueError("Conversation contains an invalid step")
                continue
            steps.append(step)
        if not steps:
            if strict:
                raise ValueError("Conversation must contain at least one step")
            return None
        try:
            if isinstance(raw.get("weight", 1), bool):
                raise TypeError
            weight = float(raw.get("weight", 1))
        except (TypeError, ValueError) as exc:
            if strict:
                raise ValueError("Conversation weight must be a number") from exc
            weight = 1.0
        weight = max(1.0, min(999.0, weight))
        return ConversationDefinition(weight, tuple(steps))

    def _legacy_steps(self, raw: dict[str, object]) -> list[dict[str, str]]:
        steps = []
        for speaker in self.speaker_ids:
            text = " ".join(str(raw.get(speaker, "")).split())
            if text:
                steps.append({"type": "say", "speaker": speaker, "text": text})
        event_id = str(raw.get("event", ""))
        if event_id in self.event_ids:
            steps.append({"type": "event", "event": event_id})
        return steps

    @staticmethod
    def _serialize(definition: ConversationDefinition) -> dict[str, object]:
        weight = (
            int(definition.weight)
            if definition.weight.is_integer()
            else definition.weight
        )
        return {
            "weight": weight,
            "steps": [dict(step) for step in definition.steps],
        }
