import os
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import game
from conversation_editor import CONVERSATION_REPOSITORY, PLACEMENT_REPOSITORY
from engine.conversation_definition import ConversationDefinition
from engine.placement_definition import PlacementDefinition
from engine.placement_repository import normalize_tag


class TaggedConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((game.WIDTH, game.HEIGHT))

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def make_ghosts(self, habitat_objects, steps):
        deck = (ConversationDefinition(1.0, tuple(steps)),)
        kadoka = game.Ghost(
            game.ASSET_DIR / "kadoka.png", (300, 300), 64,
            __import__("random").Random(1), 1.0, name="kadoka",
            display_name="かどか",
            conversation_deck=deck, habitat_objects=habitat_objects,
        )
        maru = game.Ghost(
            game.ASSET_DIR / "maru.png", (500, 300), 64,
            __import__("random").Random(2), 1.0, native_facing=-1, name="maru",
            display_name="まる", bubble_y_offset=-34,
            conversation_deck=deck, habitat_objects=habitat_objects,
        )
        kadoka.event_owner = True
        maru.event_owner = False
        kadoka.talk_target = maru
        maru.talk_target = kadoka
        return kadoka, maru

    def test_existing_conversations_are_upgraded_to_steps(self):
        deck = game.load_conversation_deck()
        self.assertTrue(deck)
        self.assertTrue(all(item.steps for item in deck))
        self.assertTrue(all("type" in step for item in deck for step in item.steps))
        editor_data = CONVERSATION_REPOSITORY.load_editable()
        self.assertEqual(len(editor_data), len(deck))
        self.assertTrue(all(item["steps"] for item in editor_data))
        self.assertTrue(all(item["weight"] == 1 for item in editor_data))

    def test_existing_object_tags_are_available_to_editor(self):
        self.assertEqual(
            set(PLACEMENT_REPOSITORY.tags()),
            {"water", "small_rock", "large_rock", "found_item", "game_device"},
        )

    def test_game_device_event_takes_out_tagged_object(self):
        objects = game.load_placed_objects()
        device = next(item for item in objects if item.tag == "game_device")
        self.assertFalse(device.visible)
        kadoka, maru = self.make_ghosts(objects, [])
        bounds = pygame.Rect(74, 80, 812, 446)
        kadoka.begin_scripted_event("game_device", maru, bounds)
        self.assertFalse(device.visible)
        self.assertEqual(maru.current_action, "script")
        self.assertEqual(kadoka.current_action, "script_wait")
        maru.script_timer = 0.0
        maru.update_script(0.01, bounds, kadoka)
        self.assertTrue(device.visible)
        self.assertTrue(device.glowing)
        self.assertEqual(maru.talk_text, "ピカーン")
        maru.script_timer = 0.0
        maru.update_script(0.01, bounds, kadoka)
        self.assertEqual(maru.talk_text, "まぶしいのだーーー")
        self.assertEqual(kadoka.talk_text, "まぶしい")
        maru.script_timer = 0.0
        maru.update_script(0.01, bounds, kadoka)
        self.assertFalse(device.glowing)
        self.assertFalse(device.visible)
        self.assertEqual(kadoka.current_action, "flee")
        self.assertEqual(maru.current_action, "flee")
        self.assertLess(kadoka.click_target.x, maru.click_target.x)

    def test_game_device_conversation_is_in_the_deck(self):
        deck = game.load_conversation_deck()
        matching = [
            item for item in deck
            if any(
                step.get("type") == "event" and step.get("event") == "game_device"
                for step in item.steps
            )
        ]
        self.assertTrue(matching)
        self.assertEqual(
            matching[0].steps[:2],
            (
                {"type": "say", "speaker": "kadoka", "text": "これ、なんだろ"},
                {"type": "say", "speaker": "maru", "text": "わかんないのだ"},
            ),
        )

    def test_take_and_put_change_object_visibility(self):
        image = pygame.Surface((20, 20), pygame.SRCALPHA)
        item = game.HabitatObject(
            PlacementDefinition(
                "test", "test", game.ASSET_DIR / "kadoka.png", None,
                "treasure", 400, 350, 20, True,
            ),
            image,
            image.get_rect(center=(400, 350)),
        )
        kadoka, maru = self.make_ghosts([item], [])
        kadoka.sequence_steps = [
            {"type": "take", "actor": "kadoka", "tag": "treasure"},
            {"type": "put", "actor": "kadoka", "tag": "treasure"},
        ]
        kadoka.sequence_index = 0
        kadoka.run_next_conversation_step(maru, pygame.Rect(74, 80, 812, 446))
        self.assertTrue(item.visible)
        self.assertEqual(kadoka.current_action, "sequence_pause")
        kadoka.run_next_conversation_step(maru, pygame.Rect(74, 80, 812, 446))
        self.assertFalse(item.visible)

    def test_move_step_targets_tagged_object(self):
        image = pygame.Surface((20, 20), pygame.SRCALPHA)
        item = game.HabitatObject(
            PlacementDefinition(
                "test", "test", game.ASSET_DIR / "kadoka.png", None,
                "water", 600, 420, 20, True,
            ),
            image,
            image.get_rect(center=(600, 420)),
        )
        kadoka, maru = self.make_ghosts([item], [])
        kadoka.sequence_steps = [{"type": "move", "actor": "maru", "tag": "water"}]
        kadoka.sequence_index = 0
        kadoka.run_next_conversation_step(maru, pygame.Rect(74, 80, 812, 446))
        self.assertEqual(maru.current_action, "sequence_move")
        self.assertIsNotNone(maru.click_target)
        self.assertEqual(kadoka.sequence_movers, {"maru"})

    def test_conversation_selection_uses_weights(self):
        first = ConversationDefinition(
            1.0, ({"type": "say", "speaker": "kadoka", "text": "first"},)
        )
        second = ConversationDefinition(
            9.0, ({"type": "say", "speaker": "maru", "text": "second"},)
        )
        kadoka, maru = self.make_ghosts([], first.steps)
        kadoka.conversation_deck = (first, second)

        class ChoiceRecorder:
            def __init__(self):
                self.weights = None

            def choices(self, population, weights, k):
                self.weights = weights
                return [population[1]]

            @staticmethod
            def uniform(low, high):
                return (low + high) / 2

        recorder = ChoiceRecorder()
        kadoka.rng = recorder
        kadoka.start_talking(maru, pygame.Rect(74, 80, 812, 446))
        self.assertEqual(recorder.weights, [1.0, 9.0])
        self.assertEqual(maru.talk_text, "second")

    def test_tag_normalization(self):
        self.assertEqual(normalize_tag("  大きい 岩  "), "大きい_岩")

    def test_hover_name_only_appears_over_each_ghost(self):
        kadoka, maru = self.make_ghosts([], [])
        rendered_rect = pygame.Rect(260, 260, 80, 80)

        self.assertEqual(kadoka.hover_name((300, 300), rendered_rect), "かどか")
        self.assertEqual(maru.hover_name((300, 300), rendered_rect), "まる")
        self.assertEqual(kadoka.hover_name((100, 100), rendered_rect), "")
        self.assertEqual(maru.hover_name(None, rendered_rect), "")


if __name__ == "__main__":
    unittest.main()
