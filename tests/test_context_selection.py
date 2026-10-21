from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.context.script.audit import audit_mapping
from tools.context.script.select_files import load_mapping, normalize_path, select_files

ROOT = Path(__file__).resolve().parents[1]


class ContextSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_mapping()

    def test_game_change_selects_only_game_context_and_related_test(self) -> None:
        result = select_files(["game.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/game.md"])
        self.assertEqual(result["tests"], ["tests/test_tagged_conversations.py"])
        self.assertEqual(result["unmapped_files"], [])

    def test_editor_change_selects_tool_context(self) -> None:
        result = select_files(["character_editor.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertEqual(result["tests"], ["tests/test_character_repository.py"])

    def test_policy_change_selects_only_router_and_contract(self) -> None:
        result = select_files(["AGENTS.md"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertEqual(result["tests"], ["tests/test_context_policy.py"])
        self.assertEqual(result["related_files"], ["docs/context/project.md", "docs/ai-development-contract.md"])
        self.assertEqual(result["unmapped_files"], [])

    def test_snapshot_selects_metadata_tool_without_game_implementation(self) -> None:
        result = select_files(["tools/context/script/snapshot.py", "tests/test_context_snapshot.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertIn("tests/test_context_snapshot.py", result["tests"])
        self.assertIn("tools/context/README.md", result["related_files"])
        self.assertIn("tools/diff_summary/script/summarize.py", result["related_files"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_ci_change_selects_shared_evaluator_without_game_implementation(self) -> None:
        result = select_files([".github/workflows/work-ci.yml"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertIn("scripts/evaluate_project.py", result["related_files"])
        self.assertEqual(result["tests"], ["tests/test_evaluate_project.py", "tests/test_ruff_baseline.py"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_quality_change_selects_its_gate_without_game_implementation(self) -> None:
        result = select_files(["ruff.toml", "tools/quality/script/check_ruff.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertEqual(result["tests"], ["tests/test_ruff_baseline.py"])
        self.assertIn("tools/quality/README.md", result["related_files"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_integration_inventory_selects_only_history_tool_and_plan(self) -> None:
        result = select_files(["tools/repo_sync/script/inventory.py", "tools/repo_sync/main_work_inventory.json"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertIn("tests/test_integration_inventory.py", result["tests"])
        self.assertIn("docs/ワークフロー/main_work統合.md", result["related_files"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_bootstrap_change_selects_isolated_entrypoint_checks(self) -> None:
        result = select_files(["tools/context/script/snapshot.py", "tests/test_tool_bootstrap.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertIn("tests/test_tool_bootstrap.py", result["tests"])
        self.assertIn("tools/quality/README.md", result["related_files"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_engine_repository_selects_engine_and_game_contexts(self) -> None:
        result = select_files(["engine\\room_repository.py"], self.rules)
        self.assertEqual(result["changed_files"], ["engine/room_repository.py"])
        self.assertIn("docs/context/engine.md", result["contexts"])
        self.assertIn("docs/context/game.md", result["contexts"])
        self.assertEqual(result["tests"], ["tests/test_room_repository.py"])

    def test_unknown_path_is_explicitly_reported(self) -> None:
        result = select_files(["new_feature.py", "./new_feature.py"], self.rules)
        self.assertEqual(result["changed_files"], ["new_feature.py"])
        self.assertEqual(result["unmapped_files"], ["new_feature.py"])

    def test_unsafe_or_absolute_path_is_rejected(self) -> None:
        for value in ("../secret.txt", "C:\\outside.py", "/outside.py", "a//b.py"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_path(value)

    def test_shared_contract_selects_portability_without_game_code(self) -> None:
        result = select_files(["spec/engine/project_manifest_cases.json"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/portability.md"])
        self.assertEqual(result["tests"], ["tests/test_portable_project_contract.py", "tests/test_engine_manifest.py"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_godot_change_selects_only_godot_context(self) -> None:
        result = select_files(["godot/scripts/ghost_model.gd"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/godot.md"])
        self.assertEqual(result["tests"], ["tests/test_godot_runtime.py"])
        self.assertEqual(result["unmapped_files"], [])

    def test_responsibility_references_exist(self) -> None:
        for rule in self.rules:
            for field in ("context", "related", "tests"):
                paths = [rule[field]] if field == "context" else rule[field]
                for path in paths:
                    with self.subTest(path=path):
                        self.assertTrue((ROOT / path).is_file())

    def test_godot_manifest_selects_shared_oracle_and_runtime_tests(self) -> None:
        result = select_files(["godot/scripts/project_manifest.gd", "godot/scripts/content_loader.gd"], self.rules)
        self.assertIn("docs/context/portability.md", result["contexts"])
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("spec/engine/project_manifest_cases.json", result["related_files"])
        self.assertIn("tests/test_portable_project_contract.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_godot_runner_selects_bridge_contract_and_tests(self) -> None:
        result = select_files(["engine/godot_runner.py", "tests/test_godot_runner.py"], self.rules)
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("docs/context/engine.md", result["contexts"])
        self.assertIn("tests/test_godot_runner.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertEqual(result["unmapped_files"], [])

    def test_launch_monitor_selects_its_tests_without_game_implementation(self) -> None:
        result = select_files(["engine/process_launcher.py", "tests/test_main_window.py"], self.rules)
        self.assertIn("docs/context/engine.md", result["contexts"])
        self.assertIn("docs/context/developer_tools.md", result["contexts"])
        self.assertIn("tests/test_process_launcher.py", result["tests"])
        self.assertIn("tests/test_main_window.py", result["tests"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_godot_process_launch_selects_shared_preparation_and_diagnostics(self) -> None:
        result = select_files(["engine/process_launcher.py", "tests/test_godot_process_launcher.py"], self.rules)
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("docs/context/engine.md", result["contexts"])
        self.assertIn("engine/godot_runner.py", result["related_files"])
        self.assertIn("tests/test_godot_process_launcher.py", result["tests"])
        self.assertIn("tests/test_godot_runner.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertIn("tests/test_process_launcher.py", result["tests"])
        self.assertIn("tests/test_godot_preparation.py", result["tests"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_engine_package_marker_selects_only_engine_context(self) -> None:
        result = select_files(["engine/__init__.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/engine.md"])
        self.assertEqual(result["related_files"], [])
        self.assertEqual(result["tests"], [])
        self.assertEqual(result["unmapped_files"], [])

    def test_background_preparation_selects_worker_and_launch_tests(self) -> None:
        result = select_files(["tests/test_godot_preparation.py"], self.rules)
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("docs/context/engine.md", result["contexts"])
        self.assertIn("engine/godot_runner.py", result["related_files"])
        self.assertIn("tests/test_godot_preparation.py", result["tests"])
        self.assertIn("tests/test_godot_process_launcher.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_json_cli_output_is_machine_readable(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/context/script/select_files.py", "--json", "room.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout)["tests"], ["tests/test_room_repository.py"])

    def test_godot_test_discovery_selects_all_consumers_without_game_code(self) -> None:
        result = select_files(["tests/godot_support.py", "tests/test_godot_support.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/godot.md"])
        self.assertIn("engine/godot_runner.py", result["related_files"])
        self.assertEqual(result["tests"], ["tests/test_godot_support.py", "tests/test_godot_runtime.py",
                                          "tests/test_portable_project_contract.py", "tests/test_portable_character_contract.py",
                                          "tests/test_portable_room_contract.py", "tests/test_portable_palette_contract.py",
                                          "tests/test_portable_polygon_contract.py"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_character_contract_selects_shared_cases_and_godot_tests(self) -> None:
        result = select_files(["godot/scripts/character_schema.gd", "spec/character/characters_cases.json"], self.rules)
        self.assertIn("docs/context/portability.md", result["contexts"])
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("spec/character/characters.md", result["related_files"])
        self.assertIn("tests/test_portable_character_contract.py", result["tests"])
        self.assertIn("tests/test_character_repository.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_room_contract_selects_shared_cases_and_godot_tests(self) -> None:
        result = select_files(["godot/scripts/room_geometry.gd", "spec/map/room_geometry_cases.json"], self.rules)
        self.assertIn("docs/context/portability.md", result["contexts"])
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("spec/map/room_geometry.md", result["related_files"])
        self.assertIn("tests/test_portable_room_contract.py", result["tests"])
        self.assertIn("tests/test_room_repository.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertNotIn("spec/map/background_palette_cases.json", result["related_files"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_palette_contract_selects_only_its_specs_and_required_fixture(self) -> None:
        result = select_files(["godot/scripts/background_palette.gd", "spec/map/background_palette_cases.json"], self.rules)
        self.assertIn("docs/context/portability.md", result["contexts"])
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("spec/map/background_palette.md", result["related_files"])
        self.assertIn("spec/map/room_geometry_cases.json", result["related_files"])
        self.assertIn("tests/test_portable_palette_contract.py", result["tests"])
        self.assertIn("tests/test_room_repository.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertNotIn("spec/map/room_geometry.md", result["related_files"])
        self.assertNotIn("tests/test_portable_room_contract.py", result["tests"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_audit_scope_does_not_make_other_rules_look_unused(self) -> None:
        rule = {"paths": ["engine/*.py", "game.py", "stale.py"],
                "context": "docs/context/project.md", "related": [], "tests": []}
        report = audit_mapping(ROOT, ["engine/room_repository.py", "game.py", "unknown.py"],
                               [rule], ("engine/",))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["unmapped_files"], [])
        self.assertEqual(report["unmatched_patterns"], ["stale.py"])
        unscoped = audit_mapping(ROOT, ["game.py", "unknown.py"], [rule])
        self.assertEqual(unscoped["unmapped_files"], ["unknown.py"])

    def test_polygon_contract_selects_geometry_and_fixture_without_palette_specs(self) -> None:
        result = select_files(["godot/scripts/polygon_geometry.gd", "spec/map/polygon_geometry_cases.json"], self.rules)
        self.assertIn("docs/context/portability.md", result["contexts"])
        self.assertIn("docs/context/godot.md", result["contexts"])
        self.assertIn("spec/map/polygon_geometry.md", result["related_files"])
        self.assertIn("spec/map/room_geometry_cases.json", result["related_files"])
        self.assertIn("tests/test_portable_polygon_contract.py", result["tests"])
        self.assertIn("tests/test_godot_runtime.py", result["tests"])
        self.assertNotIn("spec/map/background_palette.md", result["related_files"])
        self.assertNotIn("spec/map/room_geometry.md", result["related_files"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_audit_reports_missing_and_escaping_references(self) -> None:
        rule = {"paths": ["game.py"], "context": "missing.md",
                "related": ["../outside.py"], "tests": []}
        report = audit_mapping(ROOT, ["game.py"], [rule])
        self.assertEqual(len(report["errors"]), 2)
        self.assertIn("missing file", report["errors"][0])
        self.assertIn("repository-relative", report["errors"][1])

    def test_mapping_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "responsibility table"):
                load_mapping(path)


if __name__ == "__main__":
    unittest.main()
