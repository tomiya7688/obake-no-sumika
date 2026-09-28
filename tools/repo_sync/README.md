# リモート状態の確認

`work` と `origin/work` の進み具合、作業ツリーの未コミット変更、リモート側の圧縮差分を確認する。既定ではローカルのリモート追跡情報だけを読み、`--fetch` を指定した場合だけ `git fetch --prune origin` を実行する。どちらの場合も `merge`、`pull`、`reset`、ファイルの上書きは行わない。

```powershell
.\.venv\Scripts\python.exe tools/repo_sync/script/report.py --fetch --json
.\.venv\Scripts\python.exe tools/repo_sync/script/report.py --max-files 10
```

`--repo`、`--remote`、`--branch` で対象を指定できる。`state` は `up_to_date`、`behind`、`ahead`、`diverged` のいずれか。`fast_forward_safe` はリモートが先行し、ローカルコミットと未コミット変更がない場合だけ真となる。ただし安全判定は事前確認であり、実際の取り込み前に `git status` を再確認し、ワークフローに従い `git merge --ff-only origin/work` を別途実行する。`--fetch` なしの結果は古い可能性がある。
