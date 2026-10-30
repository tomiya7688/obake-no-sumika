# Python品質ゲート（段階的移植）

Issue #86のRuff **lint** は違反0必須まで適応済み。format・Mypy・UPD・性能ゲートは未移植で、この成功だけでmain側の品質CI全体を再現したとは扱わない。

## 準備と実行

プロジェクトのvenvで、対応Pythonにインストール可能な最新版を毎回取得する（latest-first）。互換性・回帰で固定が必要なら根拠をIssueへ記録し、検査を黙って省略しない。Godot/Actionsの固定とは別の方針。

```powershell
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --upgrade -r tools/quality/requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe tools/quality/script/check_ruff.py
.\.venv\Scripts\python.exe tools/quality/script/check_ruff.py --json --limit 20
.\.venv\Scripts\python.exe -m unittest tests.test_ruff_baseline -v
```

同じPythonの `-m ruff` を使用し、バージョンを結果へ含める。PATHの別バージョンへフォールバックしない。検査は明示した `ruff.toml` を使い、`--no-fix --no-cache --no-respect-gitignore` で実行する。gitignoreによるPythonソースの隠蔽はせず、venv・tmp等の除外と選択ルールは設定で管理する。CLIと設定の原典は[Ruff configuration](https://docs.astral.sh/ruff/configuration/)。ソース・baselineを書き換えるコマンドではない。

`--repo` は検査ルート（既定はこのリポジトリ）、`--baseline` は記録ファイル（既定は検査ルートの `tools/quality/ruff_baseline.json`）。どの作業ディレクトリから呼んでも既定ルートは変わらない。`--limit` はnew/stale各一覧の件数上限で、総件数と省略件数は常に返す。

| 終了コード | 意味 |
| --- | --- |
| 0 | 選択ルールの診断0、baselineも空 |
| 1 | Ruffの診断がある |
| 2 | Ruff未導入・起動失敗・timeout・設定/出力/baseline不正（空でない場合も含む） |

## 一時baselineの解消と維持

導入時のRuff 0.17.1では67件（import順序I001: 59、import位置E402: 8）。PR #95で8件へ減らし、CLI入口の整理で現在は0件。`ruff_baseline.json` は互換性・経緯のため空のまま保持し、どのカテゴリの診断追加もパーサーで拒否する。件数やルールを緩めて通さない。

context/diff_summary/repo_syncの6入口は、ローカルimportの前に `__file__` から解決したパスを `sys.path.insert` へ渡し、公開 `PROJECT_ROOT` 定数はimport後に定義する。呼び出し元cwdやPYTHONPATHへ依存しない直接起動と定数の値を、`-I` の隔離実行でテストする。この配置は[Ruff E402の公式仕様](https://docs.astral.sh/ruff/rules/module-import-not-at-top-of-file/)が認めるsys.path準備を利用し、ignore/noqaは追加しない。importだけをパス準備より前へ動かして起動を壊す修正はしない。

新規違反はコード側で直す。既存の上限付きJSON形式と `baseline_size` / `stale_count` は維持するが、正常時の値は0。baselineを一括再生成して失敗を隠す運用は認めない。`snapshot.py` の `run_git` 別名とラッパーも維持する。

設定はmain由来のE4/E7/E9/F/Iとテストの既存E402例外を保持する。ここでの0件はこの選択ルールに対する値であり、全ルール・format・型検査の成功ではない。旧ソース全体のformatは別単位。チェッカー版変更、新しい例外の提案は根拠をPRで明示する。

## Work CI

`Ruff lint baseline (Python 3.10)` と既存の `Work validation (Python 3.10 / Godot 4.7.2)` は独立した必須確認。baselineは空になったが、required statusとの互換性のためチェック名は変えない。片方の成功で他方の失敗・未完を相殺しない。全体単体テストにもRuff実CLIテストがあるため、validation側も品質依存を導入する。CIへの接続の原典は[Ruff integrations](https://docs.astral.sh/ruff/integrations/)。ブランチ保護設定は変更しない。

全体評価とGodotの手順は[開発ワークフロー](../../docs/ワークフロー/ワークフロー.md)。この変更はゲーム挙動・描画・実GUIの検証を代替しない。

## 作業後の対象限定整形

実装担当は、変更したPythonファイルをプロジェクトのvenvのRuffで整形し、書換えないcheck、関連テスト、自己レビュー、追加レビューの順に確認する。指摘を修正した場合も同じ順で再確認する。レビュアーには整形を依頼しない。

入口は `tools/quality/script/format_changed.py`（Issue #110）。対象の選び方を次の3つから1つだけ指定し、担当外の未コミット変更には触れない。

```powershell
# 1) 今回の変更だけを git add してから整形（推奨）
git add <今回変更したファイル>
.\.venv\Scripts\python.exe tools/quality/script/format_changed.py --staged
# 2) 整形した同じファイルを再度 git add し、コミットされる内容を確認
git add <整形されたファイル>
.\.venv\Scripts\python.exe tools/quality/script/format_changed.py --staged --check
# ブランチ全体の変更ファイルを書き換えずに確認（CIと同じ。先に git fetch origin）
.\.venv\Scripts\python.exe tools/quality/script/format_changed.py --base origin/work --check
# ファイルを明示する
.\.venv\Scripts\python.exe tools/quality/script/format_changed.py game.py tests/test_tagged_conversations.py
```

- `--base` はこのリポジトリの標準ベース `origin/work` との merge-base からの差分（`BASE...HEAD`）を使う。ベースが進んでも他者のファイルは対象にならない。
- Ruff はファイル全体を書き換えるので、`--staged` では未 stage の変更が残るファイル、`--base` ではコミットしていない変更が残るファイルを整形せず止める。同じファイルに他者の変更が混ざっていても巻き込まない。`--staged` で整形した直後は整形分が未 stage なので、再度 `git add` するまで `--staged --check` も止まる。他者の変更が混ざったファイルは整形前に止まるので、再 `git add` で入るのは整形分だけになる。`--check` でも同じ条件で止めるのは、確認する内容（作業ツリー）とコミットされる内容を一致させるため。
- 明示パスはリポジトリ内の既存ファイルだけを受け付ける。`.py` 以外と削除されたファイルは対象外。
- 終了コード: 0（整形した、または整形済み、または対象なし）、1（`--check` で未整形ファイルあり）、2（指定誤り・リポジトリ外・ファイルなし・未コミット変更の混在・git失敗・Ruff未導入）。変更したファイルはファイル全体を整形するので、未整形の旧ファイルに触れると差分が大きくなる。その整形も同じPRに含め、意味が変わっていないことを差分で確かめる。

Work CI の `Ruff lint baseline (Python 3.10)` ジョブは、変更されたPythonファイルを `--check` で確認する（チェック名は互換性のため変えない）。比較元はPRでは `origin/<PRのベース>`、`work` への push では push 前の先頭。比較元のない手動実行だけは理由を表示して確認を省く。必須ゲートを条件で飛ばさないよう、ジョブやステップに `if:` は付けない（`tests/test_ruff_baseline.py` が確認）。

既存の `ruff.toml`（Python 3.10、100桁、ダブルクォート、空白インデント、改行自動判定）を共有する。`.git`・`.venv`・`tmp` は除外設定を維持し、担当外のdirtyファイル、生成物、vendorは明示引数にも含めない。競合するformatterやグローバル版は使わない。準備は上記の品質依存の導入手順を使い、実行版を `-m ruff --version` で記録する（Issue #103の実行版: 0.17.2）。

整形コマンドとcheckは別々の1コマンドである。対象限定checkの成功は、全Pythonのformat成功を意味しない。旧ソース全体の整形と全体ゲートはIssue #86で引き続き扱う。

GDScript（`godot/`）にはformatterを導入していない（Godot 4.7.2 標準のCLI整形はなく、gdtoolkit等は未採用）。JSONは各repositoryの保存処理が `indent=2` で書き出す形式を正とし、手編集時もその形式に合わせる。
