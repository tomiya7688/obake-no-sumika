import py_compile
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from engine.character_repository import CharacterRepository
from engine.conversation_repository import ConversationRepository
from engine.event_repository import EventRepository
from engine.manifest_loader import load_project_manifest
from engine.placement_repository import PlacementRepository
from engine.project_creator import ProjectCreator
from engine.room_repository import RoomRepository


class ProjectCreatorTests(unittest.TestCase):
    def test_created_project_validates_and_contains_starter_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = ProjectCreator().create_project(Path(temp_dir), "test project")
            manifest = load_project_manifest(manifest_path)

            self.assertEqual(manifest.name, "test project")
            self.assertEqual(manifest.root, Path(temp_dir).resolve() / "test project")
            self.assertEqual(manifest.editors, ())
            self.assertEqual(manifest.entrypoint, manifest.root / "game.py")
            self.assertEqual(manifest.content["characters"], manifest.root / "characters.json")

            room = RoomRepository(manifest.content["room"]).load()
            self.assertEqual((room.width, room.height), (960, 540))
            characters = CharacterRepository(
                manifest.root,
                manifest.content["characters"],
                (room.width, room.height),
            ).load()
            self.assertEqual([character.id for character in characters], ["player"])
            events = EventRepository(manifest.content["events"]).load()
            conversations = ConversationRepository(
                manifest.content["conversations"],
                ("player",),
                ("player", "both"),
                tuple(event.id for event in events),
            ).load()
            placements = PlacementRepository(
                manifest.root,
                manifest.content["placements"],
                (room.width, room.height),
            ).load()
            self.assertEqual(len(conversations), 1)
            self.assertEqual(placements, ())
            py_compile.compile(str(manifest.entrypoint), doraise=True)

    def test_project_name_is_sanitized_for_folder_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = ProjectCreator().create_project(Path(temp_dir), 'a:b?c')

            self.assertEqual(manifest_path.parent.name, "a_b_c")
            manifest = load_project_manifest(manifest_path)
            self.assertEqual(manifest.name, "a:b?c")

    def test_existing_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = Path(temp_dir)
            ProjectCreator().create_project(parent, "same")

            with self.assertRaises(FileExistsError):
                ProjectCreator().create_project(parent, "same")


if __name__ == "__main__":
    unittest.main()
