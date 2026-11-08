import json
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

# 人間社会の語彙（おばけは詳しくない設定）。会話に出てはいけない。
HUMAN_SOCIETY_WORDS = ("会社", "仕事", "学校", "お金", "法律", "政治", "電車", "スマホ")
MAX_LENGTH = {"kadoka": 20, "maru": 24}


def load_lines() -> list[tuple[str, str]]:
    data = json.loads((PROJECT_DIR / "conversations.json").read_text(encoding="utf-8"))
    return [
        (step["speaker"], step["text"])
        for conversation in data
        for step in conversation.get("steps", [])
        if step.get("type") == "say"
    ]


class CharacterVoiceTests(unittest.TestCase):
    def test_kadoka_speaks_shortly_without_maru_verbal_tic(self):
        for speaker, text in load_lines():
            if speaker == "kadoka":
                self.assertLessEqual(len(text), MAX_LENGTH["kadoka"], text)
                self.assertNotIn("なのだ", text, text)

    def test_maru_uses_own_first_person_and_stays_short(self):
        for speaker, text in load_lines():
            if speaker == "maru":
                self.assertLessEqual(len(text), MAX_LENGTH["maru"], text)
                self.assertNotIn("僕", text, text)

    def test_nobody_talks_about_human_society(self):
        for _speaker, text in load_lines():
            for word in HUMAN_SOCIETY_WORDS:
                self.assertNotIn(word, text, text)


if __name__ == "__main__":
    unittest.main()
