from __future__ import annotations

import json
import re
from pathlib import Path

from .placement_definition import PlacementDefinition


def normalize_tag(tag: str) -> str:
    """Normalize editable tags without hiding their meaning in JSON."""
    return re.sub(r"\s+", "_", tag.strip())


class PlacementRepository:
    """Load and atomically save room object placements."""

    def __init__(
        self,
        project_root: Path,
        data_path: Path,
        room_size: tuple[int, int],
    ) -> None:
        self.project_root = project_root.resolve()
        self.data_path = data_path.resolve()
        self.room_width, self.room_height = room_size
        if self.room_width <= 0 or self.room_height <= 0:
            raise ValueError("Room size must be positive")
        self._inside_project(self.data_path)

    def load(self) -> tuple[PlacementDefinition, ...]:
        try:
            raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ()
        if not isinstance(raw, dict) or not isinstance(raw.get("objects"), list):
            return ()
        definitions = []
        seen_ids = set()
        seen_tags = set()
        for raw_item in raw["objects"]:
            try:
                definition = self._parse(raw_item)
            except (TypeError, ValueError):
                continue
            if definition.id in seen_ids:
                continue
            if definition.tag and definition.tag in seen_tags:
                continue
            definitions.append(definition)
            seen_ids.add(definition.id)
            if definition.tag:
                seen_tags.add(definition.tag)
        return tuple(definitions)

    def load_editable(self) -> list[dict[str, object]]:
        return [self._serialize(definition) for definition in self.load()]

    def save_editable(self, editable: list[dict[str, object]]) -> None:
        definitions = [self._parse(raw_item) for raw_item in editable]
        ids = [definition.id for definition in definitions]
        if len(ids) != len(set(ids)):
            raise ValueError("Placement ids must be unique")
        tags = [definition.tag for definition in definitions if definition.tag]
        if len(tags) != len(set(tags)):
            raise ValueError("Placement tags must be unique")
        payload = {"objects": [self._serialize(definition) for definition in definitions]}
        temporary = self.data_path.with_suffix(self.data_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.data_path)

    def tags(self) -> list[str]:
        return sorted(definition.tag for definition in self.load() if definition.tag)

    def _parse(self, raw: object) -> PlacementDefinition:
        if not isinstance(raw, dict):
            raise ValueError("Each placement must be an object")
        placement_id = str(raw.get("id", "")).strip()
        name = str(raw.get("name", "object")).strip() or "object"
        if not placement_id:
            raise ValueError("Placement id is required")
        image = self._project_path(raw.get("image"), must_exist=True)
        raw_source = raw.get("source")
        source = (
            self._project_path(raw_source, must_exist=False)
            if isinstance(raw_source, str) and raw_source.strip()
            else None
        )
        visible = raw.get("visible", True)
        if not isinstance(visible, bool):
            raise ValueError("Placement visible must be boolean")
        return PlacementDefinition(
            id=placement_id,
            name=name,
            image=image,
            source=source,
            tag=normalize_tag(str(raw.get("tag", ""))),
            x=self._integer(raw.get("x"), "x", 0, self.room_width),
            y=self._integer(raw.get("y"), "y", 0, self.room_height),
            width=self._integer(raw.get("width"), "width", 4, 512),
            visible=visible,
        )

    def _project_path(self, raw_path: object, must_exist: bool) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("Placement path must be a non-empty string")
        path = (self.project_root / raw_path).resolve()
        self._inside_project(path)
        if must_exist and not path.is_file():
            raise ValueError(f"Placement image does not exist: {raw_path}")
        return path

    def _inside_project(self, path: Path) -> None:
        if path != self.project_root and self.project_root not in path.parents:
            raise ValueError(f"Path escapes the project root: {path}")

    def _serialize(self, definition: PlacementDefinition) -> dict[str, object]:
        result: dict[str, object] = {
            "id": definition.id,
            "name": definition.name,
            "image": definition.image.relative_to(self.project_root).as_posix(),
            "x": definition.x,
            "y": definition.y,
            "width": definition.width,
            "visible": definition.visible,
        }
        if definition.source is not None:
            result["source"] = definition.source.relative_to(self.project_root).as_posix()
        if definition.tag:
            result["tag"] = definition.tag
        return result

    @staticmethod
    def _integer(value: object, label: str, minimum: int, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be an integer")
        if value < minimum or value > maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}")
        return value
