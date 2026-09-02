from __future__ import annotations

import json
import re
import struct
import zlib
from pathlib import Path


STARTER_GAME = '''from __future__ import annotations

import argparse
import json
from pathlib import Path

import pygame


ROOT = Path(__file__).resolve().parent


def load_room() -> dict:
    return json.loads((ROOT / "room.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Starter engine project")
    parser.add_argument("--test-frames", type=int, default=0)
    args = parser.parse_args()

    room = load_room()
    width = int(room["size"]["width"])
    height = int(room["size"]["height"])
    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Engine Starter Project")
    clock = pygame.time.Clock()
    image = pygame.image.load(str(ROOT / "assets" / "player.png")).convert_alpha()
    image = pygame.transform.scale(image, (48, 48))
    pos = pygame.Vector2(width * 0.5, height * 0.5)
    velocity = pygame.Vector2(80, 0)
    frames = 0
    running = True
    while running:
        dt = clock.tick(int(room.get("fps", 60))) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
        pos += velocity * dt
        if pos.x < 40 or pos.x > width - 40:
            velocity.x *= -1
        top = tuple(room["background"]["gradient"]["top"])
        bottom = tuple(room["background"]["gradient"]["bottom"])
        screen.fill(top)
        pygame.draw.rect(screen, bottom, (0, height * 0.55, width, height * 0.45))
        screen.blit(image, image.get_rect(center=(round(pos.x), round(pos.y))))
        pygame.display.flip()
        frames += 1
        if args.test_frames and frames >= args.test_frames:
            running = False
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


class ProjectCreator:
    """Create a minimal engine project that validates immediately."""

    def create_project(self, parent: Path, name: str) -> Path:
        project_name = self._clean_name(name)
        project_root = parent.resolve() / project_name
        if project_root.exists():
            raise FileExistsError(f"Project already exists: {project_root}")
        project_root.mkdir(parents=True)
        (project_root / "assets").mkdir()
        (project_root / "objects").mkdir()
        self._write_json(project_root / "engine_project.json", self._manifest(name))
        self._write_json(project_root / "room.json", self._room())
        self._write_json(project_root / "characters.json", self._characters())
        self._write_json(project_root / "placed_objects.json", {"objects": []})
        self._write_json(project_root / "events.json", self._events())
        self._write_json(project_root / "conversations.json", self._conversations())
        (project_root / "game.py").write_text(STARTER_GAME, encoding="utf-8")
        (project_root / "requirements.txt").write_text("pygame>=2.5\n", encoding="utf-8")
        (project_root / "README.md").write_text(self._readme(name), encoding="utf-8")
        self._write_placeholder_png(project_root / "assets" / "player.png")
        return project_root / "engine_project.json"

    def _clean_name(self, name: str) -> str:
        cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", name.strip())
        cleaned = cleaned.strip(" .")
        if not cleaned:
            raise ValueError("Project name is required")
        return cleaned

    def _write_json(self, path: Path, payload: object) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_placeholder_png(self, path: Path) -> None:
        width = 16
        height = 16
        row = b"\x00" + bytes([255, 255, 255, 255]) * width
        raw = row * height
        payload = (
            b"\x89PNG\r\n\x1a\n"
            + self._png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + self._png_chunk(b"IDAT", zlib.compress(raw))
            + self._png_chunk(b"IEND", b"")
        )
        path.write_bytes(payload)

    def _png_chunk(self, chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    def _manifest(self, name: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "name": name.strip(),
            "entrypoint": "game.py",
            "editors": [],
            "content": {
                "characters": "characters.json",
                "character_assets": "assets",
                "room": "room.json",
                "placements": "placed_objects.json",
                "objects": "objects",
                "conversations": "conversations.json",
                "events": "events.json",
            },
        }

    def _room(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "size": {"width": 960, "height": 540},
            "fps": 60,
            "movement_bounds": [72, 72, 816, 420],
            "zones": {"water_rest": [360, 360, 240, 120]},
            "conversation_distance": 140.0,
            "motes": {
                "count": 16,
                "x_range": [80, 880],
                "y_range": [80, 520],
                "reset_y_range": [500, 545],
                "top": 72,
                "speed_range": [2.0, 6.0],
                "drift_speed": 0.35,
                "drift_amount": 1.8,
                "radii": [1, 1, 2],
                "alpha_range": [16, 40],
                "color": [140, 150, 170],
            },
            "background": {
                "gradient": {"top": [9, 10, 18], "bottom": [18, 18, 27], "step": 8},
                "polygons": [
                    {
                        "color": [6, 7, 13],
                        "points": [[0, 0], [960, 0], [960, 64], [0, 64]],
                    },
                    {
                        "color": [12, 13, 21],
                        "points": [[0, 320], [960, 300], [960, 540], [0, 540]],
                    },
                ],
                "vignette": {
                    "color": [0, 0, 4],
                    "max_inset": 96,
                    "step": 8,
                    "border_width": 10,
                    "radius": 48,
                    "alpha_start": 12,
                    "alpha_divisor": 10,
                    "min_alpha": 2,
                },
            },
        }

    def _characters(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "characters": [
                {
                    "id": "player",
                    "display_name": "player",
                    "image": "assets/player.png",
                    "start_position": [480, 270],
                    "display_height": 48,
                    "personality": 1.0,
                    "native_facing": 1,
                    "bubble_y_offset": 0,
                }
            ],
        }

    def _events(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "events": [
                {"id": "idle", "label": "idle", "terminal": False},
            ],
        }

    def _conversations(self) -> list[dict[str, object]]:
        return [
            {
                "weight": 1,
                "steps": [{"type": "say", "speaker": "player", "text": "..."}],
            }
        ]

    def _readme(self, name: str) -> str:
        return (
            f"# {name.strip()}\n\n"
            "This is a minimal project created by the engine launcher.\n\n"
            "## Run\n\n"
            "```powershell\n"
            "python game.py\n"
            "```\n"
        )
