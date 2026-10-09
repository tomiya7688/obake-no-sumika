# 移植・配布時の共有契約

Python版が現在の参照実装。Godot/GDScript版は `godot/` で移行第一段階を開始した。Unity版は未作成で、コード共有を前提にしない。共有対象はデータ形式、振る舞いの仕様、検証条件とする。Godot変更時は [godot.md](godot.md) だけを追加で読む。

| 契約 | 正本 | 確認先 |
| --- | --- | --- |
| プロジェクト入口と共通設定 | `engine_project.json` | `engine/manifest_loader.py`, `tests/test_engine_manifest.py` |
| 言語共通のプロジェクト読込契約 | `spec/engine/project_manifest.md`, `spec/engine/project_manifest_cases.json` | `tests/test_portable_project_contract.py`（PythonとGodot）、`godot/scripts/project_manifest.gd` |
| キャラクターの基本読込契約 | `spec/character/characters.md`, `spec/character/characters_cases.json` | `tests/test_portable_character_contract.py`（PythonとGodot）、`godot/scripts/character_schema.gd` |
| ゲーム固有のファイル対応 | `game_content.json` | `engine/manifest_loader.py` |
| キャラクター、部屋、会話、イベント、配置物 | 各JSONと `engine/*_repository.py` | `tests/test_*repository.py`, `tests/test_content_repositories.py` |
| 通常版とspecial版の分離 | 各 `engine_project.json` の `project_type` | `tests/test_special_project_isolation.py` |

形式変更時は既存JSONの読込互換、外部アセットへの相対パス、GUIからの再編集を確認する。Pythonの配布方式はIssue #12、実装間の共通仕様整理はIssue #22で追跡する。

プロジェクト定義を移植する場合は、先に [共有契約](../../spec/engine/project_manifest.md) と同ディレクトリのJSONケースを読む。PythonとGodotは同じ22ケースで受理結果・拒否条件を比較する。Godotは環境依存の絶対パスやリンクを保守的に拒否するため、それらまでPythonと完全互換とは扱わない。キャラクターの基本条件は別の [42ケース](../../spec/character/characters_cases.json) と [契約](../../spec/character/characters.md) を使う。数値文字列・非文字列メタデータ等の変換、部屋・会話などの完全な入力互換はまだ対象外。Godot未指定のテストはskipされるので、実体の検証には `GODOT_BIN` を指定する。
