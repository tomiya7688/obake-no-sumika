"""Guard the compact entrypoint and its required, discoverable contracts."""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class ContextPolicyTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_entrypoint_is_a_short_router_not_the_data_contract(self) -> None:
        entry = self.read("AGENTS.md")
        self.assertLessEqual(len(entry.splitlines()), 50)
        self.assertLessEqual(len(entry.encode("utf-8")), 4000)
        self.assertIn("docs/context/project.md", entry)
        self.assertIn("docs/ai-development-contract.md", entry)
        self.assertNotIn("```json", entry)
        self.assertNotIn("## Source map", entry)

    def test_every_implementation_still_reads_the_whole_roadmap(self) -> None:
        entry = self.read("AGENTS.md")
        self.assertIn("実装を始める前に `docs/開発予定.md` を毎回全文読む", entry)
        self.assertIn("GitHub Issues", self.read("docs/開発予定.md"))
        self.assertNotIn("通常タスクでは対象節を検索", entry)

    def test_search_stops_only_after_scope_and_acceptance_are_known(self) -> None:
        router = self.read("docs/context/project.md")
        for marker in ("Search first, read second", "Goal:", "Required:", "Acceptance:", "Working set:"):
            with self.subTest(marker=marker):
                self.assertIn(marker, router)
        self.assertIn("不足が実装・検証中に見つかった時だけ再開", router)
        self.assertIn("原典へ戻る", router)
        self.assertIn("省略する条件ではない", router)

    def test_detail_keeps_game_data_and_source_contracts(self) -> None:
        detail = self.read("docs/ai-development-contract.md")
        for heading in ("Required roadmap", "Project contract", "Source map", "Data contracts", "Safe workflow", "Verification"):
            with self.subTest(heading=heading):
                self.assertIn(f"## {heading}", detail)
        for marker in ("960x540", "native_facing=-1", "別々の乱数ストリーム", "behavior_weights", "water_stop",
                       "回転・宙返りを完了", "会話と水浴び中", "1〜999", "required_tag", "1024x1024", "obakeno_sumika_special"):
            with self.subTest(marker=marker):
                self.assertIn(marker, detail)

    def test_validation_and_release_boundaries_stay_mandatory(self) -> None:
        entry = self.read("AGENTS.md")
        for marker in (".venv", "--require-godot --frames 900", "Work CI", "実画面で確認", "未確認を明記",
                       "無関係の変更を保持", "失敗した必須チェック", "main反映・タグ・リリースは本人の承認後"):
            with self.subTest(marker=marker):
                self.assertIn(marker, entry)

    def test_both_runtimes_can_find_the_detailed_invariants(self) -> None:
        for path in ("docs/context/game.md", "docs/context/godot.md"):
            with self.subTest(path=path):
                self.assertIn("../ai-development-contract.md", self.read(path))
        router = self.read("docs/context/project.md")
        self.assertIn("Godot/GDScript", router)
        self.assertIn("tools/context/script/snapshot.py", router)

    def test_policy_markdown_links_stay_inside_repo_and_exist(self) -> None:
        for path in ("AGENTS.md", "docs/context/project.md", "docs/ai-development-contract.md",
                     "docs/context/game.md", "docs/context/godot.md"):
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", self.read(path)):
                with self.subTest(path=path, link=link):
                    parsed = urlsplit(link)
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    target = ((ROOT / path).parent / unquote(parsed.path)).resolve()
                    self.assertTrue(target.is_relative_to(ROOT.resolve()))
                    self.assertTrue(target.is_file(), str(target))


if __name__ == "__main__":
    unittest.main()
