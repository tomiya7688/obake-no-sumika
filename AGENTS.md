# Codex / AI entrypoint

最初に [docs/context/project.md](docs/context/project.md) を読み、対象領域の文書だけを選ぶ。全体説明が必要な場合だけ `README.md` を読む。

## Required roadmap

- 実装を始める前に `docs/開発予定.md` を毎回全文読む。現在はGitHub Issuesを正本とする案内があるので、対象Issueの完了条件と最新コメントも読む。
- 深い設計が必要な機能は、同文書の指示に従って機能説明書を作る。表はMarkdown、図はMermaidを使う。
- 実装完了後は、対応する項目を `docs/開発予定.md` から削除する。Issueは完了条件をすべて満たした時だけCloseする。
- 文書内の対象ファイル名や `doc/`・`docs/` の違いが実装範囲に影響する場合は、推測で直さずユーザーへ確認する。

## 読む範囲と契約

- Search first, read second。Goal / Required / Acceptance / Working set が揃ったら追加探索を止め、不足が見つかった時だけ再開する。
- ソース全体・全docs・全Issue・画像・生成物・履歴を無条件に読まない。要約で判断できない時は原典へ戻る。
- ゲームの不変条件、Source map、データ例、詳細な検証は [開発契約](docs/ai-development-contract.md) の対象節を読む。Godotは [Godot context](docs/context/godot.md)、言語間の仕様は `spec/` と対応する共有テストを正とし、他ランタイム全体を読まない。
- [1回のワークフロー](docs/ワークフロー/ワークフロー.md) に従う。作業前にstatus/fetchを確認し、`work` をff-onlyで更新する。無関係の変更を保持し、今回分だけを明示的にstageする。
- GitHub操作は `gh` CLI。通常開発は検証・最新指摘確認後に `work` へ取り込み、本人のレビュー待ちだけで停止しない。失敗した必須チェック・保留指示は無視しない。main反映・タグ・リリースは本人の承認後に行う。

## Verification

プロジェクトの `.venv` を使い、対象テストの後に全体評価を行う。Godot実行ファイルを設定して `scripts/evaluate_project.py --require-godot --frames 900` とWork CIの成功を確認する。静的検査・自動実行・描画・実GUI操作・CIの証拠を区別し、未確認を明記する。

UIや描画を変えた場合は、最後に `run_game.bat` と該当エディタを実画面で確認する。GodotのUI・描画変更ではGodot側の該当画面も確認する。headlessテストやスクリーンショットだけを実GUI操作の確認として扱わない。
