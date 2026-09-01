import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import pygame

from engine.room_renderer import RoomRenderer
from engine.room_repository import RoomRepository


class RoomRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((960, 540))

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_current_room_is_valid_and_uses_16_by_9(self):
        room = RoomRepository(PROJECT_DIR / "room.json").load()
        self.assertEqual((room.width, room.height), (960, 540))
        self.assertEqual(room.movement_bounds, (74, 80, 812, 446))
        self.assertEqual(room.water_rest_area, (335, 348, 354, 168))
        self.assertEqual(room.mote_count, 34)
        self.assertEqual(len(room.polygon_layers), 8)

    def test_renderer_uses_room_dimensions(self):
        room = RoomRepository(PROJECT_DIR / "room.json").load()
        surface = RoomRenderer(room).render()
        self.assertEqual(surface.get_size(), (room.width, room.height))

    def test_non_16_by_9_room_is_rejected(self):
        raw = self.current_payload()
        raw["size"]["height"] = 541
        with self.assertRaisesRegex(ValueError, "16:9"):
            self.load_temporary(raw)

    def test_movement_bounds_outside_room_are_rejected(self):
        raw = self.current_payload()
        raw["movement_bounds"] = [900, 500, 100, 100]
        with self.assertRaisesRegex(ValueError, "inside"):
            self.load_temporary(raw)

    @staticmethod
    def current_payload() -> dict[str, object]:
        return json.loads((PROJECT_DIR / "room.json").read_text(encoding="utf-8"))

    @staticmethod
    def load_temporary(payload: dict[str, object]):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "room.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return RoomRepository(path).load()


if __name__ == "__main__":
    unittest.main()
