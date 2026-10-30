"""Guard the compact entrypoint and its required, discoverable contracts."""

import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class ContextPolicyTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    # Cross-project policy blocks distributed by the owner and maintained outside
    # this repository (see docs/ワークフロー/共同作業ルール.md). Add new names here
    # deliberately; any other <!-- name:... --> block still counts as router text.
    DISTRIBUTED_BLOCKS = (
        "review-procedure-required",
        "shared-review-operations",
        "post-work-formatter-policy",
        "extra-free-review-policy",
    )

    def strip_distributed_blocks(self, text: str) -> str:
        names = "|".join(map(re.escape, self.DISTRIBUTED_BLOCKS))
        return re.sub(rf"<!-- ({names}):[^>]*-->.*?<!-- /\1 -->\n*", "", text, flags=re.S)

    def test_only_listed_distributed_blocks_are_excluded_from_the_router(self) -> None:
        listed = "<!-- shared-review-operations:v9 -->\nX\n<!-- /shared-review-operations -->\n"
        unlisted = "<!-- my-notes:1 -->\nY\n<!-- /my-notes -->\n"
        self.assertEqual(self.strip_distributed_blocks(listed + "router\n"), "router\n")
        self.assertEqual(self.strip_distributed_blocks(unlisted), unlisted)

    def test_entrypoint_is_a_short_router_not_the_data_contract(self) -> None:
        entry = self.read("AGENTS.md")
        self.assertIn("<!-- shared-review-operations:", entry)
        router = self.strip_distributed_blocks(entry)
        self.assertLessEqual(len(router.splitlines()), 50)
        self.assertLessEqual(len(router.encode("utf-8")), 4000)
        self.assertIn("docs/context/project.md", router)
        self.assertIn("docs/ai-development-contract.md", router)
        self.assertNotIn("```json", entry)
        self.assertNotIn("## Source map", entry)

    def test_every_implementation_still_reads_the_whole_roadmap(self) -> None:
        entry = self.read("AGENTS.md")
        self.assertIn("実装を始める前に `docs/開発予定.md` を毎回全文読む", entry)
        self.assertIn("GitHub Issues", self.read("docs/開発予定.md"))
        self.assertNotIn("通常タスクでは対象節を検索", entry)

    def test_search_stops_only_after_scope_and_acceptance_are_known(self) -> None:
        router = self.read("docs/context/project.md")
        for marker in (
            "Search first, read second",
            "Goal:",
            "Required:",
            "Acceptance:",
            "Working set:",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, router)
        self.assertIn("不足が実装・検証中に見つかった時だけ再開", router)
        self.assertIn("原典へ戻る", router)
        self.assertIn("省略する条件ではない", router)

    def test_detail_keeps_game_data_and_source_contracts(self) -> None:
        detail = self.read("docs/ai-development-contract.md")
        for heading in (
            "Required roadmap",
            "Project contract",
            "Source map",
            "Data contracts",
            "Safe workflow",
            "Verification",
        ):
            with self.subTest(heading=heading):
                self.assertIn(f"## {heading}", detail)
        for marker in (
            "960x540",
            "native_facing=-1",
            "別々の乱数ストリーム",
            "behavior_weights",
            "water_stop",
            "回転・宙返りを完了",
            "会話と水浴び中",
            "1〜999",
            "required_tag",
            "1024x1024",
            "obakeno_sumika_special",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, detail)

    def test_validation_and_release_boundaries_stay_mandatory(self) -> None:
        entry = self.read("AGENTS.md")
        for marker in (
            ".venv",
            "--require-godot --frames 900",
            "Work CI",
            "実画面で確認",
            "未確認を明記",
            "無関係の変更を保持",
            "失敗した必須チェック",
            "main反映・タグ・リリースは本人の承認後",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, entry)

    def test_both_runtimes_can_find_the_detailed_invariants(self) -> None:
        for path in ("docs/context/game.md", "docs/context/godot.md"):
            with self.subTest(path=path):
                self.assertIn("../ai-development-contract.md", self.read(path))
        router = self.read("docs/context/project.md")
        self.assertIn("Godot/GDScript", router)
        self.assertIn("tools/context/script/snapshot.py", router)

    def test_collaboration_rules_are_reachable_from_every_agent_entrypoint(self) -> None:
        entry = self.read("AGENTS.md")
        for doc in ("共同作業ルール.md", "役割別ワークフロー.md", "レビュー基準.md"):
            with self.subTest(doc=doc):
                self.assertIn(f"docs/ワークフロー/{doc}", entry)
        self.assertIn("Work CIの成功確認は必須", entry)
        roles = self.read("docs/ワークフロー/役割別ワークフロー.md")
        agents = sorted((ROOT / ".claude" / "agents").glob("*.md"))
        self.assertTrue(agents)
        for agent in agents:
            text = agent.read_text(encoding="utf-8")
            role = re.search(r"\*\*(.+?)\*\* 役", text)
            with self.subTest(agent=agent.name):
                self.assertIsNotNone(role)
                self.assertIn(f"## {role.group(1)}", roles)
                self.assertIn("docs/ワークフロー/共同作業ルール.md", text)
        for skill in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
            for doc in re.findall(r"`(docs/[^`]+\.md)`", skill.read_text(encoding="utf-8")):
                with self.subTest(skill=skill.parent.name, doc=doc):
                    self.assertTrue((ROOT / doc).is_file())

    def test_policy_markdown_links_stay_inside_repo_and_exist(self) -> None:
        for path in (
            "AGENTS.md",
            "docs/context/project.md",
            "docs/ai-development-contract.md",
            "docs/context/game.md",
            "docs/context/godot.md",
            "docs/ワークフロー/ワークフロー.md",
            "docs/ワークフロー/共同作業ルール.md",
            "docs/ワークフロー/役割別ワークフロー.md",
            "docs/ワークフロー/レビュー基準.md",
        ):
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
