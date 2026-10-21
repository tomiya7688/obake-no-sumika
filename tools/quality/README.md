# Python品質ゲート（段階的移植）

Issue #86の最初の単位はRuff **lint**。format・Mypy・UPD・性能ゲートは未移植で、この成功だけでmain側の品質CI全体を再現したとは扱わない。

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
| 0 | 診断集合が既存baselineと完全一致 |
| 1 | 新規診断、または修正済みで不要になったstale記録がある |
| 2 | Ruff未導入・起動失敗・timeout・設定/出力/baseline不正 |

## 一時baselineの縮小

導入時のRuff 0.17.1では67件（import順序I001: 59、import位置E402: 8）。`ruff_baseline.json` は既存の **path/code/row/column** を限定列挙し、総数だけでの相殺を許さない。生の `ruff check` は既存違反でも非0になるため、CIの合否は上記runnerで判定する。通過はlint違反0の意味ではない。

- 新規コードはbaselineへ追加しない。I001/E402以外は記録自体を拒否する。
- 既存違反を直したら、そのstale記録も同じ変更で削除する。古い記録を残して通さない。
- 行位置が変わるだけでもnew/staleになる。移動を確認し、実際の悪化がないことをレビューして必要最小限の位置更新を行う。位置の一致は意味的同等性の証明ではない。
- 一括再生成・件数上限の引上げ・ルール無効化で通さない。段階的に0へ減らす。
- E402には既存ツールの `sys.path` 準備後のimportが含まれる。lintのためだけに前へ移して起動を壊さず、起動契約も検証する。

設定はmain由来のE4/E7/E9/F/Iとテストの既存E402例外を保持する。今回は旧ソースの一括整形や自動修正をしない。baselineの増加、チェッカー版変更、新しい例外はPRで明示する。

## Work CI

`Ruff lint baseline (Python 3.10)` と既存の `Work validation (Python 3.10 / Godot 4.7.2)` は独立した必須確認。片方の成功で他方の失敗・未完を相殺しない。全体単体テストにもRuff実CLIテストがあるため、validation側も品質依存を導入する。CIへの接続の原典は[Ruff integrations](https://docs.astral.sh/ruff/integrations/)。ブランチ保護設定は変更しない。

全体評価とGodotの手順は[開発ワークフロー](../../docs/ワークフロー/ワークフロー.md)。この変更はゲーム挙動・描画・実GUIの検証を代替しない。
