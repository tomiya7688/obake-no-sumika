# 移植・配布時の共有契約

Python版が現在の実装。Godot/Unity版は未作成で、コード共有を前提にしない。共有対象はデータ形式、振る舞いの仕様、検証条件とする。

| 契約 | 正本 | 確認先 |
| --- | --- | --- |
| プロジェクト入口と共通設定 | `engine_project.json` | `engine/manifest_loader.py`, `tests/test_engine_manifest.py` |
| ゲーム固有のファイル対応 | `game_content.json` | `engine/manifest_loader.py` |
| キャラクター、部屋、会話、イベント、配置物 | 各JSONと `engine/*_repository.py` | `tests/test_*repository.py`, `tests/test_content_repositories.py` |
| 通常版とspecial版の分離 | 各 `engine_project.json` の `project_type` | `tests/test_special_project_isolation.py` |

形式変更時は既存JSONの読込互換、外部アセットへの相対パス、GUIからの再編集を確認する。Pythonの配布方式はIssue #12、実装間の共通仕様整理はIssue #22で追跡する。
