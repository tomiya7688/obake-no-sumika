# 開発者ツールのコンテキスト

エディターはTk GUIで、保存・検証は原則 `engine/*_repository.py` を使う。画面だけを変える場合は対象エディターと共有リポジトリの公開APIから読み始める。

| 対象 | 責務 | 関連テスト |
| --- | --- | --- |
| `character_editor.py` | キャラクターJSONの編集 | `tests/test_character_repository.py` |
| `conversation_editor.py` | 会話・イベントJSONの編集 | `tests/test_tagged_conversations.py` |
| `object_editor.py` | ドット絵作成と住処への配置 | `tests/test_object_editor_tools.py` |
| `engine_app.py`, `engine/main_window.py` | 統合GUI、プロジェクト切替、検証・Godot CLIプレイテスト入口 | `tests/test_main_window.py`, `tests/test_engine_manifest.py`, `tests/test_godot_runner.py` |
| `run_*.bat` | Windows起動入口、必要時の環境構築 | 起動対象の実行確認 |
| `scripts/evaluate_project.py` | 構文、単体テスト、通常版とspecial版の検証 | `tests/test_evaluate_project.py` |
| `tools/context/responsibilities.json`, `tools/context/script/select_files.py` | 変更ファイルから読む文書・関連ファイル・テストを選択 | `tests/test_context_selection.py` |
| `tools/diff_summary/`, `tools/repo_sync/` | コミット差分の圧縮とリモート進捗の確認 | `tests/test_diff_summary.py`, `tests/test_repo_sync.py` |
| `docs/context/cli_commands.md`, `engine_app.py --describe` | GUI不要の構成照会と主要コマンドの案内 | `tests/test_engine_manifest.py` |

プロジェクト内の `.venv` を使う。venvの参照先が移動した場合は `.\.venv\Scripts\python.exe --version` と `.\.venv\pyvenv.cfg` を確認する。GUIの見た目や操作を変えた場合は、単体テストに加えて実画面で確認する。

GodotのCLI起動は `engine/godot_runner.py` と [godot.md](godot.md) の範囲。`--playtest-godot` は終了まで待って終了コードを返し、Tk・Pythonゲームを起動しない。既存GUIの「ゲームを実行」は引き続きPython版。

## 責務表の更新

`tools/context/responsibilities.json` を機械検索用の正本とする。各ルールの `paths` はリポジトリ相対のパスまたはglob、`context` は領域文書、`related` は追加で読む候補、`tests` は関連テスト。複数ルールに一致すれば結果は重複なく統合される。新しい主要ファイルを追加したら対応ルールと `tests/test_context_selection.py` を更新し、文書の責務表も合わせる。未登録ファイルは `unmapped_files` として表示し、推測で分類しない。

点検コマンド: `.\.venv\Scripts\python.exe tools/context/script/audit.py --scope engine --scope tools --json`。Git管理下のファイルを使い、欠落した参照先を `errors`、一致するファイルのないルールを `unmatched_patterns`、対象領域の未登録ファイルを `unmapped_files` に出す。`--scope` は未登録ファイルの表示範囲だけを絞る。参照先とルールの点検は常に全体に対して行う。

欠落参照があれば終了コード1。未登録や未使用ルールも失敗にする場合は `--strict`。点検結果を確認して正本のルールを手動更新し、再実行する。未追跡の新規ファイルは点検対象に含まれないため、Gitに追加してから確認する。対象ファイルと責務表を書き換える処理はない。
