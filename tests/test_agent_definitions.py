"""Role agent definitions must match docs/ワークフロー/モデル分担.md (Issue #145)."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".claude" / "agents"
SKILLS_DIR = ROOT / ".claude" / "skills"
DOC = ROOT / "docs" / "ワークフロー" / "モデル分担.md"
ROLE_MODEL = "sonnet"
# Never a role model: reviews by Haiku are stopped (no-haiku-review block in AGENTS.md).
FORBIDDEN_ROLE_MODELS = {"haiku"}


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise AssertionError(f"{path.name} has no frontmatter")
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def role_agents() -> list[Path]:
    return sorted(AGENTS_DIR.glob("obake-*.md"))


class AgentDefinitionTests(unittest.TestCase):
    def test_the_five_roles_exist(self) -> None:
        names = [path.stem for path in role_agents()]
        self.assertEqual(
            names,
            [
                "obake-implementer",
                "obake-reviewer",
                "obake-rules-keeper",
                "obake-triage",
                "obake-verifier",
            ],
        )

    def test_every_role_is_pinned_and_cannot_start_other_agents(self) -> None:
        for path in role_agents():
            with self.subTest(agent=path.stem):
                fields = frontmatter(path)
                self.assertEqual(fields["name"], path.stem)
                self.assertTrue(fields["description"])
                self.assertEqual(fields.get("model"), ROLE_MODEL)
                self.assertNotIn(fields.get("model"), FORBIDDEN_ROLE_MODELS)
                denied = [item.strip() for item in fields.get("disallowedTools", "").split(",")]
                self.assertIn("Agent", denied, "no nested sub-agents")

    def test_the_model_doc_lists_every_role_and_its_model(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for path in role_agents():
            with self.subTest(agent=path.stem):
                self.assertIn(path.stem, text)
        self.assertIn(f"`model: {ROLE_MODEL}`", text)
        self.assertIn("disallowedTools: Agent", text)

    def test_the_model_doc_names_the_three_advisor_moments_and_the_unchanged_gates(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for needle in (
            "方針を固める前",
            "同じエラーが2回出たとき",
            "「完了」と言う前",
            "品質ゲート",
            "CI の成功と外部レビューの記録は省略しない",
            "JEV",
            "未計測",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_the_doc_is_reachable_from_the_shared_rules_and_skills(self) -> None:
        workflow = ROOT / "docs" / "ワークフロー"
        for path in (
            workflow / "共同作業ルール.md",
            workflow / "役割別ワークフロー.md",
            SKILLS_DIR / "obake-start-issue" / "SKILL.md",
            SKILLS_DIR / "obake-review-merge" / "SKILL.md",
        ):
            with self.subTest(path=path.name):
                self.assertIn("モデル分担", path.read_text(encoding="utf-8"))

    def test_the_script_the_doc_points_to_exists(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for script in (
            "tools/context/script/select_files.py",
            "tools/quality/script/format_changed.py",
            "scripts/evaluate_project.py",
        ):
            with self.subTest(script=script):
                self.assertIn(script, text)
                self.assertTrue((ROOT / script).is_file())


if __name__ == "__main__":
    unittest.main()
