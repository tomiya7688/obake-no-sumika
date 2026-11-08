"""spec/conversation/conversations_cases.json を ConversationRepository の実挙動で検証する。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.conversation_repository import ConversationRepository

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "spec/conversation/conversations_cases.json"


class PortableConversationContractTests(unittest.TestCase):
    def test_shared_cases_against_python_repository(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(suite["schema_version"], 1)
        self.assertEqual(len({case["id"] for case in suite["cases"]}), len(suite["cases"]))
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "conversations.json"
            repository = ConversationRepository(
                data_path,
                tuple(suite["speaker_ids"]),
                tuple(suite["actor_ids"]),
                tuple(suite["event_ids"]),
            )
            for case in suite["cases"]:
                with self.subTest(case=case["id"]):
                    data_path.write_text(
                        json.dumps(case["input"], ensure_ascii=False), encoding="utf-8"
                    )
                    # 寛容読込: ゲーム実行時と同じ正規化結果
                    self.assertEqual(repository.load_editable(), case["loaded"])
                    # 厳密検証: エディター保存時（配列は保存可否、配列以外は診断）
                    if isinstance(case["input"], list):
                        try:
                            repository.save_editable(case["input"])
                            strict_ok = True
                        except ValueError:
                            strict_ok = False
                    else:
                        strict_ok = not repository.load_problems()
                    self.assertEqual(strict_ok, case["strict_ok"])


if __name__ == "__main__":
    unittest.main()
