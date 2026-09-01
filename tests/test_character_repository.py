import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from engine.character_definition import CharacterDefinition
from engine.character_repository import CharacterRepository


class CharacterRepositoryTests(unittest.TestCase):
    def test_current_characters_are_valid_and_aligned(self):
        repository = CharacterRepository(
            PROJECT_DIR,
            PROJECT_DIR / "characters.json",
            (960, 540),
        )
        definitions = repository.load()
        self.assertEqual([item.id for item in definitions], ["kadoka", "maru"])
        self.assertEqual([item.display_height for item in definitions], [64, 64])
        self.assertEqual([item.start_y for item in definitions], [340, 340])
        self.assertEqual(definitions[1].native_facing, -1)

    def test_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ghost.png").write_bytes(b"placeholder")
            item = self.character_payload("same")
            data_path = root / "characters.json"
            data_path.write_text(
                json.dumps({"schema_version": 1, "characters": [item, item]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                CharacterRepository(root, data_path, (960, 540)).load()

    def test_image_path_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_path = root / "characters.json"
            item = self.character_payload("ghost")
            item["image"] = "../outside.png"
            data_path.write_text(
                json.dumps({"schema_version": 1, "characters": [item]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "escapes"):
                CharacterRepository(root, data_path, (960, 540)).load()

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "ghost.png"
            image.write_bytes(b"placeholder")
            data_path = root / "characters.json"
            data_path.write_text(
                json.dumps({"schema_version": 1, "characters": [self.character_payload("old")]}),
                encoding="utf-8",
            )
            repository = CharacterRepository(root, data_path, (960, 540))
            expected = CharacterDefinition(
                "ghost", "おばけ", image, 100, 200, 72, 1.25, -1, -20
            )
            repository.save([expected])
            self.assertEqual(repository.load(), (expected,))

    @staticmethod
    def character_payload(character_id: str) -> dict[str, object]:
        return {
            "id": character_id,
            "display_name": "おばけ",
            "image": "ghost.png",
            "start_position": [100, 200],
            "display_height": 64,
            "personality": 1.0,
            "native_facing": 1,
            "bubble_y_offset": 0,
        }


if __name__ == "__main__":
    unittest.main()
