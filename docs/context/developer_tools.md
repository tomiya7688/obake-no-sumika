# 開発者ツールのコンテキスト

エディターはTk GUIで、保存・検証は原則 `engine/*_repository.py` を使う。画面だけを変える場合は対象エディターと共有リポジトリの公開APIから読み始める。

| 対象 | 責務 | 関連テスト |
| --- | --- | --- |
| `character_editor.py` | キャラクターJSONの編集 | `tests/test_character_repository.py` |
| `conversation_editor.py` | 会話・イベントJSONの編集。話者・イベントの既定値は読み込んだ定義から選び、特定IDに依存しない | `tests/test_tagged_conversations.py`, `tests/test_conversation_editor_generic_ids.py` |
| `object_editor.py` | ドット絵作成と住処への配置 | `tests/test_object_editor_tools.py` |
| `engine_app.py`, `engine/main_window.py` | 統合GUI、プロジェクト切替、検証・Godot CLIプレイテスト入口 | `tests/test_main_window.py`, `tests/test_engine_manifest.py`, `tests/test_godot_runner.py` |
| `engine/process_launcher.py` | 非同期のゲーム・エディター起動、終了コードとUTF-8ログの取得 | `tests/test_process_launcher.py`, `tests/test_main_window.py` |
| `run_*.bat` | Windows起動入口。Pythonの4入口はvenvのpip/certifiを取得前/起動前に検査し、失敗時は起動しない。[手順](../../tools/security/README.md) | `tests/test_windows_security_launchers.py`、起動対象の実行確認 |
| `scripts/evaluate_project.py`, `.github/workflows/work-ci.yml` | ローカル/PR共通の構文・単体・通常版/special検証、Godot必須モード、JSON非破壊確認 | `tests/test_evaluate_project.py` |
| `ruff.toml`, `tools/quality/` | 違反0必須のRuff lint、空baselineの維持、実行/設定失敗の検出 | `tests/test_ruff_baseline.py` |
| `tools/security/script/bootstrap.py`, `tools/security/README.md` | 選択Pythonのpip/certifi最低版確認と明示更新。CAファイル点検は全TLS経路/OS信頼の検証とは区別する | `tests/test_python_security.py` |
| context/diff_summary/repo_syncの6 CLI入口 | 別cwd・PYTHONPATHなしの直接起動、ファイル基準のPROJECT_ROOT | `tests/test_tool_bootstrap.py` |
| `tools/context/responsibilities.json`, `tools/context/script/select_files.py` | 変更ファイルから読む文書・関連ファイル・テストを選択 | `tests/test_context_selection.py` |
| `tools/context/script/snapshot.py` | 未stage/stage済み・未追跡・履歴を本文なし・上限付きで照会 | `tests/test_context_snapshot.py` |
| `AGENTS.md`, `docs/context/project.md`, `docs/ai-development-contract.md` | 短い入口、探索停止条件、必要時だけ読む詳細契約 | `tests/test_context_policy.py` |
| `tools/diff_summary/`, `tools/repo_sync/` | コミット差分の圧縮とリモート進捗の確認 | `tests/test_diff_summary.py`, `tests/test_repo_sync.py` |
| `tools/repo_sync/script/inventory.py`, `tools/repo_sync/main_work_inventory.json` | main/work固有コミットの分類と比較範囲の変化を読み取り専用で確認 | `tests/test_integration_inventory.py` |
| `docs/context/cli_commands.md`, `engine_app.py --describe` | GUI不要の構成照会と主要コマンドの案内 | `tests/test_engine_manifest.py` |

プロジェクト内の `.venv` を使う。venvの参照先が移動した場合は `.\.venv\Scripts\python.exe --version` と `.\.venv\pyvenv.cfg` を確認する。GUIの見た目や操作を変えた場合は、単体テストに加えて実画面で確認する。

Tkエディターを実際に生成するテストでは、モジュールの `messagebox` を `mock` で置き換える。本物のモーダルダイアログ（保存エラー・確認）が出るとheadless実行が終わらなくなるため、呼び出しを記録して検証する。

品質依存は `python -m pip install --upgrade -r tools/quality/requirements.txt` で導入する。全体単体テストにもRuff実CLIテストがあるため必須。`tools/quality/script/check_ruff.py` は選択ルールの違反0を必須とし、baselineへの診断追加も拒否する。format/型/性能ゲートは未移植。互換性を保つCI名と空baselineの運用は [tools/quality/README.md](../../tools/quality/README.md)。

GodotのCLI起動は `engine/godot_runner.py` と [godot.md](godot.md) の範囲。`--playtest-godot` は終了まで待って終了コードを返し、Tk・Pythonゲームを起動しない。既存GUIの「ゲームを実行」は引き続きPython版。

GUI起動は「起動を確認しています」→「実行中」→正常/異常終了を表示する。子プロセスの生存はゲーム画面の準備完了を保証しないため「起動しました」と断定しない。異常終了は150ms間隔の監視で検出し、終了コード・ログ末尾（最大8192バイト）・保存先をダイアログへ表示する。標準出力と標準エラーは選択プロジェクトの `tmp/launch_logs/*.log` にUTF-8で保存する。PIPEを使わず大量出力による停止を避け、pythonw経由でも診断できる。同時起動のログは分離し、プロジェクトを切り替えても元のプロジェクト名で終了を通知する。エンジンを閉じても子プロセスは終了させず、ログも残す。停止操作・ログ一覧などの統合プロセス管理はIssue #15の後続範囲。

## 責務表の更新

変更一覧だけが必要なら `tools/context/script/snapshot.py --json` を使う。オプションと三点比較の意味は [tools/context/README.md](../../tools/context/README.md)。リモートは更新せず、ファイル本文も出力しない。読むべき文書と関連テストの選択は従来通り `select_files.py`。

`tools/context/responsibilities.json` を機械検索用の正本とする。各ルールの `paths` はリポジトリ相対のパスまたはglob、`context` は領域文書、`related` は追加で読む候補、`tests` は関連テスト。複数ルールに一致すれば結果は重複なく統合される。新しい主要ファイルを追加したら対応ルールと `tests/test_context_selection.py` を更新し、文書の責務表も合わせる。未登録ファイルは `unmapped_files` として表示し、推測で分類しない。

点検コマンド: `.\.venv\Scripts\python.exe tools/context/script/audit.py --scope engine --scope tools --json`。Git管理下のファイルを使い、欠落した参照先を `errors`、一致するファイルのないルールを `unmatched_patterns`、対象領域の未登録ファイルを `unmapped_files` に出す。`--scope` は未登録ファイルの表示範囲だけを絞る。参照先とルールの点検は常に全体に対して行う。

欠落参照があれば終了コード1。未登録や未使用ルールも失敗にする場合は `--strict`。点検結果を確認して正本のルールを手動更新し、再実行する。未追跡の新規ファイルは点検対象に含まれないため、Gitに追加してから確認する。対象ファイルと責務表を書き換える処理はない。
