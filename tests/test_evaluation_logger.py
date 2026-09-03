import json
import tempfile
import unittest
from pathlib import Path

import pygame

from engine.evaluation_logger import EvaluationLogger


class DummyGhost:
    def __init__(self) -> None:
        self.name = "kadoka"
        self.position = pygame.Vector2(10.12345, 20.6789)
        self.velocity = pygame.Vector2(1.25, -2.5)
        self.facing = 1
        self.current_action = "forward"
        self.turning = False
        self.spin_elapsed = None
        self.talk_text = "ここ"
        self.click_target = pygame.Vector2(30, 40)


class DummyObject:
    def __init__(self) -> None:
        self.id = "spring"
        self.tag = "water"
        self.rect = pygame.Rect(90, 100, 20, 30)
        self.visible = True
        self.glowing = False


class EvaluationLoggerTests(unittest.TestCase):
    def test_logger_writes_sampled_jsonl_snapshots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runtime.jsonl"
            logger = EvaluationLogger(path, sample_interval=2)
            logger.log_frame(0, 0.01667, [DummyGhost()], [DummyObject()])
            logger.log_frame(1, 0.03334, [DummyGhost()], [DummyObject()])
            logger.log_frame(2, 0.05, [DummyGhost()], [DummyObject()])
            logger.close()

            lines = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 2)
        payload = json.loads(lines[0])
        self.assertEqual(payload["frame"], 0)
        self.assertEqual(payload["ghosts"][0]["name"], "kadoka")
        self.assertEqual(payload["ghosts"][0]["action"], "forward")
        self.assertEqual(payload["ghosts"][0]["target"], {"x": 30.0, "y": 40.0})
        self.assertEqual(payload["objects"][0]["tag"], "water")

    def test_interval_must_be_positive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                EvaluationLogger(Path(temp_dir) / "runtime.jsonl", sample_interval=0)


if __name__ == "__main__":
    unittest.main()
