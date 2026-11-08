import py_compile
import sys
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from engine.character_repository import CharacterRepository
from engine.conversation_repository import ConversationRepository
from engine.event_repository import EventRepository
from engine.manifest_loader import load_project_manifest
from engine.placement_repository import PlacementRepository
from engine.project_creator import STARTER_GAME, ProjectCreator
from engine.room_repository import RoomRepository


def load_starter_namespace() -> dict:
    stub = types.ModuleType("pygame")
    previous = sys.modules.get("pygame")
    sys.modules["pygame"] = stub
    try:
        namespace = {"__name__": "starter_test", "__file__": str(PROJECT_DIR / "game.py")}
        exec(compile(STARTER_GAME, "starter_game.py", "exec"), namespace)
    finally:
        if previous is None:
            del sys.modules["pygame"]
        else:
            sys.modules["pygame"] = previous
    return namespace


class StarterBounceTests(unittest.TestCase):
    def test_large_dt_never_leaves_the_walls(self):
        bounce = load_starter_namespace()["bounce"]
        for dt in (0.016, 0.5, 5.0, 100.0):
            for x, vx in ((880.0, 80.0), (920.0, 80.0), (40.0, -80.0), (500.0, 80.0)):
                nx, nv = bounce(x, vx, dt, 960)
                self.assertTrue(40 <= nx <= 920, (dt, x, vx, nx))
                nx2, _ = bounce(nx, nv, 0.016, 960)
                self.assertTrue(40 <= nx2 <= 920)

    def test_direction_points_inward_after_hitting_a_wall(self):
        bounce = load_starter_namespace()["bounce"]
        self.assertLess(bounce(915.0, 80.0, 0.1, 960)[1], 0)
        self.assertGreater(bounce(45.0, -80.0, 0.1, 960)[1], 0)

    def test_exactly_reaching_a_wall_also_turns_inward(self):
        bounce = load_starter_namespace()["bounce"]
        self.assertEqual(bounce(912.0, 80.0, 0.1, 960), (920.0, -80.0))
        self.assertEqual(bounce(48.0, -80.0, 0.1, 960), (40.0, 80.0))


class ProjectCreatorTests(unittest.TestCase):
    def test_created_project_validates_and_contains_starter_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = ProjectCreator().create_project(Path(temp_dir), "test project")
            manifest = load_project_manifest(manifest_path)

            self.assertEqual(manifest.name, "test project")
            self.assertEqual(manifest.project_type, "standard")
            self.assertEqual(manifest.root, Path(temp_dir).resolve() / "test project")
            self.assertEqual(manifest.content_manifest, manifest.root / "game_content.json")
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
            manifest_path = ProjectCreator().create_project(Path(temp_dir), "a:b?c")

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
