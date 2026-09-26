# 開発者ツールのコンテキスト

エディターはTk GUIで、保存・検証は原則 `engine/*_repository.py` を使う。画面だけを変える場合は対象エディターと共有リポジトリの公開APIから読み始める。

| 対象 | 責務 | 関連テスト |
| --- | --- | --- |
| `character_editor.py` | キャラクターJSONの編集 | `tests/test_character_repository.py` |
| `conversation_editor.py` | 会話・イベントJSONの編集 | `tests/test_tagged_conversations.py` |
| `object_editor.py` | ドット絵作成と住処への配置 | `tests/test_object_editor_tools.py` |
| `engine_app.py`, `engine/main_window.py` | 統合GUI、プロジェクト切替、検証入口 | `tests/test_main_window.py`, `tests/test_engine_manifest.py` |
| `run_*.bat` | Windows起動入口、必要時の環境構築 | 起動対象の実行確認 |
| `scripts/evaluate_project.py` | 構文、単体テスト、通常版とspecial版の検証 | `tests/test_evaluate_project.py` |
| `tools/context/responsibilities.json`, `tools/context/script/select_files.py` | 変更ファイルから読む文書・関連ファイル・テストを選択 | `tests/test_context_selection.py` |

プロジェクト内の `.venv` を使う。venvの参照先が移動した場合は `.\.venv\Scripts\python.exe --version` と `.\.venv\pyvenv.cfg` を確認する。GUIの見た目や操作を変えた場合は、単体テストに加えて実画面で確認する。

## 責務表の更新

`tools/context/responsibilities.json` を機械検索用の正本とする。各ルールの `paths` はリポジトリ相対のパスまたはglob、`context` は領域文書、`related` は追加で読む候補、`tests` は関連テスト。複数ルールに一致すれば結果は重複なく統合される。新しい主要ファイルを追加したら対応ルールと `tests/test_context_selection.py` を更新し、文書の責務表も合わせる。未登録ファイルは `unmapped_files` として表示し、推測で分類しない。
