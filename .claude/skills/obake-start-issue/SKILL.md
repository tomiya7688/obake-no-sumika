---
name: obake-start-issue
description: おばけの住処で次のIssueに着手する時の手順。「次」「続き」と言われた時、または新しいIssueを始める時に使う。
---

# Issueに着手する

ルール本文は共有文書にある。この手順は入口だけ。

1. `git status --short --branch` で既存変更を確認する。無関係な変更は最後まで触らない。
2. `git fetch origin` し、`work` を `git merge --ff-only origin/work` で更新する。
3. `gh pr list --state open` と `git branch -r` で、他のエージェントが同じIssue・ファイルを触っていないか確認する（`docs/ワークフロー/共同作業ルール.md`）。
4. `docs/開発予定.md` を全文読み、`docs/ワークフロー/Issue優先度.md` に従って対象Issueを選ぶ。`gh issue view <番号> --comments` で完了条件と最新コメントを読む。
5. Issueに `着手: <エージェント名> / branch: issue/<番号>-<短い名前>` とコメントし、そのブランチを `work` から作る。
6. 以降は `docs/ワークフロー/役割別ワークフロー.md` の「実装」節に従う。