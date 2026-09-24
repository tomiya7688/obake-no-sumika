# 共通エンジンのコンテキスト

`engine/` はプロジェクト定義とデータの読込・検証を持つ。ゲーム固有の演出やかどか・まる専用の処理は `game.py` とゲームデータに置く。

| 対象 | 責務 | 関連テスト |
| --- | --- | --- |
| `engine_project.json`, `engine/manifest_loader.py`, `engine/project_manifest.py` | プロジェクト入口、パス検証、エディター定義 | `tests/test_engine_manifest.py` |
| `game_content.json` | 通常版のコンテンツファイル対応表 | `tests/test_engine_manifest.py` |
| `engine/*_definition.py`, `engine/*_repository.py` | 型、JSON読込・保存・値検証 | `tests/test_character_repository.py`, `tests/test_content_repositories.py`, `tests/test_room_repository.py` |
| `engine/room_renderer.py` | 部屋背景の描画 | `tests/test_room_repository.py` |
| `engine/process_launcher.py` | プロジェクトのゲーム・エディター起動 | `tests/test_engine_manifest.py` |
| `engine/project_creator.py` | 新規プロジェクトの最小データ生成 | `tests/test_project_creator.py` |
| `engine/evaluation_logger.py` | 実行中の状態をJSONLへ記録 | `tests/test_evaluation_logger.py` |

`engine/main_window.py` はTk GUIなので [developer_tools.md](developer_tools.md) を参照。マニフェストの検証だけなら `.\.venv\Scripts\python.exe engine_app.py --validate` でGUIを起動せずに実行できる。
