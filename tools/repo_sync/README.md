# リモート状態の確認

`work` と `origin/work` の進み具合、作業ツリーの未コミット変更、リモート側の圧縮差分を確認する。既定ではローカルのリモート追跡情報だけを読み、`--fetch` を指定した場合だけ `git fetch --prune origin` を実行する。どちらの場合も `merge`、`pull`、`reset`、ファイルの上書きは行わない。

```powershell
.\.venv\Scripts\python.exe tools/repo_sync/script/report.py --fetch --json
.\.venv\Scripts\python.exe tools/repo_sync/script/report.py --max-files 10
```

`--repo`、`--remote`、`--branch` で対象を指定できる。`state` は `up_to_date`、`behind`、`ahead`、`diverged` のいずれか。`fast_forward_safe` はリモートが先行し、ローカルコミットと未コミット変更がない場合だけ真となる。ただし安全判定は事前確認であり、実際の取り込み前に `git status` を再確認し、ワークフローに従い `git merge --ff-only origin/work` を別途実行する。`--fetch` なしの結果は古い可能性がある。

## main/workの棚卸し確認

```powershell
git fetch origin
.\.venv\Scripts\python.exe tools/repo_sync/script/inventory.py --json
```

`main_work_inventory.json` の固定SHA・23コミット・意味単位の分類を、追跡refの履歴集合と照合する。出力の `groups` は方針と必要な検証、`commits` は各コミットの対応先。1コミットに複数分類を持たせられる。取り込み済みかの意味判定やrelease承認は行わず、`status: proposal` の計画だけを受け付ける。

`--repo`、`--plan`、`--main-ref`（既定origin/main）、`--work-ref`（既定origin/work）を指定できる。refはcommitへ解決してから比較に使い、先頭 `-` のrefを拒否する。入力JSONの重複キー・不明な分類・重複した対応先・未使用グループもエラー。固定SHAを持つ履歴がないshallow環境は成功にせず入力エラーにする。

終了コードは一致が0、再分類が必要なら1、不正入力/履歴不足が2。`unclassified` と `no_longer_main_only` は現時点、`baseline_unclassified` と `baseline_excess` は固定した初回集合の漏れ/余剰。workの通常の先行は許容し、main更新・work巻き戻し・共通祖先変更は再確認を要求する。

ツールはfetch・checkout・merge・index更新・ファイル保存を行わない。`fetched: false` はツール自身がfetchしていないという意味。実行前にリモート追跡refを更新する。比較元・分類・段階的な取り込みは[統合計画](../../docs/ワークフロー/main_work統合.md)を参照する。
