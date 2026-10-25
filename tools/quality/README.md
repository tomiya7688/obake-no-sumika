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

リポジトリ直下で実行する。次はIssue #103の対象例で、別の作業では引数をその作業の変更ファイルへ置き換える。

```powershell
.\.venv\Scripts\python.exe -m ruff format engine/character_repository.py engine/conversation_repository.py engine/room_repository.py
.\.venv\Scripts\python.exe -m ruff format --check engine/character_repository.py engine/conversation_repository.py engine/room_repository.py
```

既存の `ruff.toml`（Python 3.10、100桁、ダブルクォート、空白インデント、改行自動判定）を共有する。`.git`・`.venv`・`tmp` は除外設定を維持し、担当外のdirtyファイル、生成物、vendorは明示引数にも含めない。競合するformatterやグローバル版は使わない。準備は上記の品質依存の導入手順を使い、実行版を `-m ruff --version` で記録する（Issue #103の実行版: 0.17.2）。

整形コマンドとcheckは別々の1コマンドである。対象限定checkの成功は、全Pythonのformat成功やformat CI導入を意味しない。全体ゲートはIssue #86で引き続き扱う。
