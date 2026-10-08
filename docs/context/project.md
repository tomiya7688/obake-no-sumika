# 最初に読む: 範囲の選択

この文書だけを先に読み、作業対象に合う文書を1つ選ぶ。全ファイルの一括読み込みは不要。

| 変更対象 | 次に読む文書 | 主なファイル |
| --- | --- | --- |
| おばけの行動、会話、背景、ゲーム固有データ | [game.md](game.md) | `game.py`, `characters.json`, `room.json`, `conversations.json` |
| JSONの読込・検証、プロジェクト定義、共通起動処理 | [engine.md](engine.md) | `engine/`, `engine_project.json`, `game_content.json` |
| Tkエディター、起動バッチ、自動評価 | [developer_tools.md](developer_tools.md) | `*_editor.py`, `engine_app.py`, `scripts/` |
| Python以外の実装、配布構成、共有データ契約 | [portability.md](portability.md) | `engine_project.json`, `game_content.json`, 各種JSON |
| Godot / GDScript移行版 | [godot.md](godot.md) | `godot/`, `run_godot.bat` |

## 1回の作業

1. `git status --short --branch` で既存変更を確認する。
2. `git fetch origin` でリモートを確認し、`work` を `git merge --ff-only origin/work` で更新する。
3. [Issue優先度方針](../ワークフロー/Issue優先度.md)に従い、P0の緊急対応を確認する。通常作業では `gh issue list --search "コンテキスト OR context"` を先に読み、P1 → P2 → P3と依存関係から選んだ対象を `gh issue view <番号>` で読む。P4は着手前に再分類する。
4. 上表で読む範囲を決め、対象文書の責務表に載るファイルだけを調べる。
   変更ファイルが分かっている場合は、プロジェクトのPythonで `tools/context/script/select_files.py game.py` を実行して候補を取得できる。JSON出力は `--json`。
5. 変更後は対象テストと全体テストを実行し、必要な実行確認を行う。具体的な手順はワークフローに従う。
6. 今回の変更だけをコミットし、`work` 宛てのPRを作る。自己レビュー・検証と最新の指摘確認後、Kadoka本人からレビューや保留指示が来ていなければ承認待ちで止めず `work` へ取り込み、次へ進む。後からのフィードバックはIssueで扱う。リリース前は本人の確認・承認を待つ。詳細は [ワークフロー](../ワークフロー/ワークフロー.md)。

`AGENTS.md` はゲーム固有の不変条件と検証方法、`key_info.md` は現在使える機能の短い一覧。深い仕様は必要になった時だけ対応する機能説明書を読む。

実行コマンドだけ必要な場合は [CUIコマンドシート](cli_commands.md) を読む。
