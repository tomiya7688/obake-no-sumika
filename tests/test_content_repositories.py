import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from PIL import Image

from engine.conversation_repository import ConversationRepository
from engine.event_repository import EventRepository
from engine.pixel_object_repository import PixelObjectRepository
from engine.placement_repository import PlacementRepository


class ContentRepositoryTests(unittest.TestCase):
    def test_current_events_and_conversations_are_valid(self):
        event_repository = EventRepository(PROJECT_DIR / "events.json")
        events = event_repository.load()
        self.assertEqual([event.id for event in events], ["water_bath", "game_device"])
        event_repository.validate_required_tags(events, ["game_device"])
        repository = ConversationRepository(
            PROJECT_DIR / "conversations.json",
            ("kadoka", "maru"),
            ("kadoka", "maru", "both"),
            tuple(event.id for event in events),
        )
        deck = repository.load()
        self.assertTrue(deck)
        self.assertTrue(
            any(
                step.get("event") == "game_device"
                for conversation in deck
                for step in conversation.steps
            )
        )

    def test_event_required_tag_is_enforced(self):
        repository = EventRepository(PROJECT_DIR / "events.json")
        with self.assertRaisesRegex(ValueError, "game_device"):
            repository.validate_required_tags(repository.load(), ["water"])

    def test_conversation_save_normalizes_legacy_and_steps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "conversations.json"
            path.write_text(
                json.dumps([{"kadoka": "  しずか  だね ", "maru": "うん"}]),
                encoding="utf-8",
            )
            repository = ConversationRepository(
                path,
                ("kadoka", "maru"),
                ("kadoka", "maru", "both"),
                ("water_bath",),
            )
            editable = repository.load_editable()
            repository.save_editable(editable)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved[0]["steps"][0]["text"], "しずか だね")
            self.assertEqual(saved[0]["weight"], 1)

    def test_current_placements_are_valid_and_tags_are_unique(self):
        repository = PlacementRepository(
            PROJECT_DIR,
            PROJECT_DIR / "placed_objects.json",
            (960, 540),
        )
        placements = repository.load()
        self.assertEqual(len(placements), 5)
        self.assertEqual(
            set(repository.tags()),
            {"water", "small_rock", "large_rock", "found_item", "game_device"},
        )

    def test_placement_save_rejects_duplicate_tags(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            Image.new("RGBA", (2, 2), "white").save(root / "object.png")
            data_path = root / "placed_objects.json"
            data_path.write_text('{"objects": []}', encoding="utf-8")
            repository = PlacementRepository(root, data_path, (960, 540))
            first = self.placement_payload("one", "same")
            second = self.placement_payload("two", "same")
            with self.assertRaisesRegex(ValueError, "tags"):
                repository.save_editable([first, second])

    def test_pixel_object_round_trip_exports_1024_png(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repository = PixelObjectRepository(root, root / "objects", (16, 32), 1024)
            pixels = [[None for _ in range(16)] for _ in range(16)]
            pixels[3][4] = "#12ABef"
            png_path, source_path = repository.save("test object", 16, pixels)
            with Image.open(png_path) as image:
                self.assertEqual(image.size, (1024, 1024))
            self.assertEqual(repository.load(source_path), (16, pixels))

    @staticmethod
    def placement_payload(placement_id: str, tag: str) -> dict[str, object]:
        return {
            "id": placement_id,
            "name": placement_id,
            "image": "object.png",
            "tag": tag,
            "x": 100,
            "y": 100,
            "width": 32,
            "visible": True,
        }


if __name__ == "__main__":
    unittest.main()
