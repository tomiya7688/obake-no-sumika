"""Read only the requested character settings from a validated project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from engine.character_repository import CharacterRepository
from engine.manifest_loader import load_project_manifest
from engine.room_repository import RoomRepository


FIELDS = (
    "id", "display_name", "image", "start_position", "display_height",
    "personality", "native_facing", "bubble_y_offset", "behavior_weights",
)


def read_settings(project: Path, character_id: str | None = None,
                  fields: tuple[str, ...] = ()) -> dict[str, object] | list[dict[str, str]]:
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown fields: {', '.join(sorted(unknown))}")
    if character_id is None and fields:
        raise ValueError("Fields require a character id")
    manifest = load_project_manifest(project)
    if not {"characters", "room"}.issubset(manifest.content):
        raise ValueError("Project must define characters and room content")
    room = RoomRepository(manifest.content["room"]).load()
    definitions = CharacterRepository(
        manifest.root, manifest.content["characters"], (room.width, room.height)
    ).load()
    if character_id is None:
        return [{"id": item.id, "display_name": item.display_name} for item in definitions]
    character = next((item for item in definitions if item.id == character_id), None)
    if character is None:
        raise ValueError(f"Unknown character id: {character_id}")
    settings = {
        "id": character.id,
        "display_name": character.display_name,
        "image": character.image.relative_to(manifest.root).as_posix(),
        "start_position": [character.start_x, character.start_y],
        "display_height": character.display_height,
        "personality": character.personality,
        "native_facing": character.native_facing,
        "bubble_y_offset": character.bubble_y_offset,
        "behavior_weights": dict(character.behavior_weights),
    }
    selected = ("id", *fields) if fields else FIELDS
    return {field: settings[field] for field in selected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=PROJECT_ROOT / "engine_project.json")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--id", dest="character_id")
    selection.add_argument("--list", action="store_true", help="list ids and display names only")
    parser.add_argument("--field", action="append", choices=FIELDS, default=[])
    args = parser.parse_args()
    try:
        settings = read_settings(args.project, args.character_id, tuple(args.field))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(settings, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
