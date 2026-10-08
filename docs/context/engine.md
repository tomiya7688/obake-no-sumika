# 共通エンジンのコンテキスト

`engine/` はプロジェクト定義とデータの読込・検証を持つ。ゲーム固有の演出やかどか・まる専用の処理は `game.py` とゲームデータに置く。

| 対象 | 責務 | 関連テスト |
| --- | --- | --- |
| `engine_project.json`, `engine/manifest_loader.py`, `engine/project_manifest.py` | プロジェクト入口、パス検証、エディター定義 | `tests/test_engine_manifest.py` |
| `game_content.json` | 通常版のコンテンツファイル対応表 | `tests/test_engine_manifest.py` |
| `engine/*_definition.py`, `engine/*_repository.py` | 型、JSON読込・保存・値検証 | `tests/test_character_repository.py`, `tests/test_content_repositories.py`, `tests/test_room_repository.py` |
| `engine/room_renderer.py` | 部屋背景の描画 | `tests/test_room_repository.py` |
| `engine/process_launcher.py` | ゲーム・エディターの非同期起動、終了コードとUTF-8ログの取得 | `tests/test_process_launcher.py`, `tests/test_main_window.py`, `tests/test_engine_manifest.py` |
| `engine/godot_runner.py` | 選択した通常版データでGodotソースのCLIプレイテスト、実行ファイル/バージョン検証、終了コード返却 | `tests/test_godot_runner.py`, `tests/test_godot_runtime.py` |
| `engine/project_creator.py` | 新規プロジェクトの最小データ生成 | `tests/test_project_creator.py` |
| `engine/evaluation_logger.py` | 実行中の状態をJSONLへ記録 | `tests/test_evaluation_logger.py` |

`engine/main_window.py` はTk GUIなので [developer_tools.md](developer_tools.md) を参照。マニフェストの検証は `.\.venv\Scripts\python.exe engine_app.py --validate`、プロジェクト構成のJSON表示は `--describe` でGUIを起動せずに実行できる。使用例は [CUIコマンドシート](cli_commands.md)。

`engine_app.py --playtest-godot` は終了まで待つCLI専用の入口。Python版のゲーム・エディター起動と混ぜず、共有JSON/PNGの意味検証と実行はGodotへ任せる。Godot側の未対応範囲は [godot.md](godot.md) を参照。既存GUIはPython版の子プロセスを150ms間隔で監視し、異常終了時に終了コード・ログ末尾・保存先を表示する。
