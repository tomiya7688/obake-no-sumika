from __future__ import annotations

import json
from pathlib import Path

from .character_definition import CharacterDefinition


class CharacterRepository:
    """Load and save editable character definitions inside one project."""

    def __init__(self, project_root: Path, data_path: Path) -> None:
        self.project_root = project_root.resolve()
        self.data_path = data_path.resolve()
        self._require_inside_project(self.data_path)

    def load(self) -> tuple[CharacterDefinition, ...]:
        raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("Unsupported character schema version")
        raw_characters = raw.get("characters")
        if not isinstance(raw_characters, list) or not raw_characters:
            raise ValueError("characters must be a non-empty list")

        definitions = []
        seen_ids = set()
        for raw_character in raw_characters:
            definition = self._parse(raw_character)
            if definition.id in seen_ids:
                raise ValueError(f"Duplicate character id: {definition.id}")
            definitions.append(definition)
            seen_ids.add(definition.id)
        return tuple(definitions)

    def save(self, definitions: list[CharacterDefinition]) -> None:
        if not definitions:
            raise ValueError("At least one character is required")
        seen_ids = set()
        serialized = []
        for definition in definitions:
            if definition.id in seen_ids:
                raise ValueError(f"Duplicate character id: {definition.id}")
            self.validate(definition)
            serialized.append(self._serialize(definition))
            seen_ids.add(definition.id)
        payload = {"schema_version": 1, "characters": serialized}
        self.data_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _parse(self, raw: object) -> CharacterDefinition:
        if not isinstance(raw, dict):
            raise ValueError("Each character must be an object")
        character_id = str(raw.get("id", "")).strip()
        display_name = str(raw.get("display_name", "")).strip()
        if not character_id or not display_name:
            raise ValueError("Character id and display_name are required")
        image = self._resolve_image(raw.get("image"))
        start = raw.get("start_position")
        if not isinstance(start, list) or len(start) != 2:
            raise ValueError(f"start_position must contain x and y: {character_id}")
        definition = CharacterDefinition(
            id=character_id,
            display_name=display_name,
            image=image,
            start_x=self._integer(start[0], "start x", 0, 960),
            start_y=self._integer(start[1], "start y", 0, 540),
            display_height=self._integer(raw.get("display_height"), "display_height", 16, 256),
            personality=self._number(raw.get("personality"), "personality", 0.25, 3.0),
            native_facing=1 if self._integer(raw.get("native_facing"), "native_facing", -1, 1) >= 0 else -1,
            bubble_y_offset=self._integer(raw.get("bubble_y_offset", 0), "bubble_y_offset", -200, 200),
        )
        self.validate(definition)
        return definition

    def validate(self, definition: CharacterDefinition) -> None:
        """Validate one edited definition without writing it."""
        if not definition.id.strip() or not definition.display_name.strip():
            raise ValueError("Character id and display_name are required")
        self._require_inside_project(definition.image.resolve())
        if not definition.image.is_file():
            raise ValueError(f"Character image does not exist: {definition.image}")
        if not 0 <= definition.start_x <= 960 or not 0 <= definition.start_y <= 540:
            raise ValueError("Character start position is outside the 960x540 room")
        if not 16 <= definition.display_height <= 256:
            raise ValueError("display_height must be between 16 and 256")
        if not 0.25 <= definition.personality <= 3.0:
            raise ValueError("personality must be between 0.25 and 3.0")
        if definition.native_facing not in (-1, 1):
            raise ValueError("native_facing must be -1 or 1")
        if not -200 <= definition.bubble_y_offset <= 200:
            raise ValueError("bubble_y_offset must be between -200 and 200")

    def _resolve_image(self, raw_path: object) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("Character image must be a non-empty path")
        image = (self.project_root / raw_path).resolve()
        self._require_inside_project(image)
        if not image.is_file():
            raise ValueError(f"Character image does not exist: {raw_path}")
        return image

    def _require_inside_project(self, path: Path) -> None:
        if path != self.project_root and self.project_root not in path.parents:
            raise ValueError(f"Path escapes the project root: {path}")

    def _serialize(self, definition: CharacterDefinition) -> dict[str, object]:
        image = definition.image.resolve().relative_to(self.project_root).as_posix()
        return {
            "id": definition.id,
            "display_name": definition.display_name,
            "image": image,
            "start_position": [definition.start_x, definition.start_y],
            "display_height": definition.display_height,
            "personality": definition.personality,
            "native_facing": definition.native_facing,
            "bubble_y_offset": definition.bubble_y_offset,
        }

    @staticmethod
    def _integer(value: object, label: str, minimum: int, maximum: int) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{label} must be an integer")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be an integer") from exc
        if number < minimum or number > maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}")
        return number

    @staticmethod
    def _number(value: object, label: str, minimum: float, maximum: float) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{label} must be a number")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a number") from exc
        if number < minimum or number > maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}")
        return number
