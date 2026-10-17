# 開発コンテキストの小さな照会

プロジェクトの `.venv` で実行する。対象領域の文書を選ぶ入口は `docs/context/project.md`。

## 未コミット・ステージ済みの変更一覧

```powershell
.\.venv\Scripts\python.exe tools/context/script/snapshot.py
.\.venv\Scripts\python.exe tools/context/script/snapshot.py --base origin/work --limit 20 --commits 8 --json
```

ブランチ・HEAD、未ステージ、ステージ済み、未追跡、最近のコミット件名を別々に表示する。ファイル本文・パッチ・コミット本文は出さない。追跡ファイルは状態と追加/削除行数、セクション全体の行数・バイナリ数も返す。未追跡は名前だけ、ignore対象は除く。改名は削除と追加として表示する。

`--limit` は各ファイル一覧の上限（既定20）、`--commits` は各履歴一覧の上限（既定8）。どちらも正の整数で、総件数と省略件数は一覧を切っても保持する。JSONでは `items` が表示分、`total` が総件数、`omitted` が省略件数。行数の合計は省略ファイルを含む。バイナリの行数は `"-"`。

`--base` を指定した時だけ比較を追加する。

- ファイルは **baseとHEADのmerge-base → HEAD**（`base...HEAD` 相当）。分岐先だけにある変更を「削除」として混ぜない。
- コミット件名は **base..HEAD**。base側にはないHEAD側の履歴を返す。

`--repo` で別のローカルリポジトリやその配下を指定できる。既定はこのツールがあるリポジトリであり、呼び出し元のカレントディレクトリではない。detached HEADではJSONの `branch` は `null`。HEADのない初期リポジトリ、無効ref、共通祖先なし、Git失敗は終了コード2と標準エラーになり、「変更なし」へ置き換えない。成功は0。

fetch、checkout、stage、reset、参照・index・ユーザーファイルの更新はしない。Gitは `--no-optional-locks` で照会する。複数の読み取りコマンドなので、同時に別プロセスが編集・commitしている時の原子的スナップショットや作業ツリー全体の復元データではない。ファイル名とコミット件名は出力に含まれるため、共有前に内容を確認する。

この機能はmainの `scripts/context_snapshot.py` の機能を既存 `tools/context/` へ移したもの。コミット間の関数・責務情報が必要なら `tools/diff_summary/script/summarize.py`、リモート鮮度は `tools/repo_sync/script/report.py --fetch`、履歴分類は `tools/repo_sync/script/inventory.py` を使う。スナップショットだけではリモートを更新しない。

## 読むファイルを選ぶ

```powershell
.\.venv\Scripts\python.exe tools/context/script/select_files.py --json game.py
.\.venv\Scripts\python.exe tools/context/script/audit.py --scope engine --scope tools --strict --json
```

責務表 `responsibilities.json` を使う。未登録パスを推測で分類しない。監査はGit追跡ファイルが対象なので、新規ファイルは明示的にstageして確認する。
