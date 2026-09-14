# AI Context

AI / Codex / Claude Code が最初に読む小さい索引です。詳細仕様はここへ複製しません。
方針は `tomiya7688/ai-context-reducer` の Search first / read second と探索停止ルールを採用します。

## Project

- Name: おばけの住処 / obake-no-sumika
- Runtime: Python 3.10+ / pygame
- Product: 戦闘・スコア・ゲームオーバーのない観察ゲーム + 汎用エンジン / 開発者ツール

## Source of Truth

- 現在の開発予定・優先順位: `docs/開発予定.md`
- エンジン設計: `docs/エンジン化機能説明書.md`
- 現在できること・起動方法: `key_info.md`
- 詳細な開発規約・データ契約: `docs/ai-development-contract.md`
- 実装・テスト: source / `tests/`
- タスク: GitHub Issues

## Read First

1. 現在の Issue / 依頼内容
2. この `AI_CONTEXT.md`
3. `docs/context-routing.md` から対象領域だけ選ぶ
4. 対象 source と対応 test
5. 必要な場合だけ `docs/ai-development-contract.md` の該当節

`docs/開発予定.md` は Source of Truth だが、通常タスクでは対象節を検索して読む。ロードマップ全体・優先順位・横断変更を判断するときだけ全文確認する。

## Stop Rule

次が揃ったら追加探索を止める。

- Goal: 何を変更するか
- Required: 壊してはいけない契約・依存先
- Acceptance: 何をもって完了とするか
- Working set: 対象 source / tests / 必要な docs

不足が実装・検証中に見つかった場合だけ探索を再開する。

## Ignore Normally

- `assets/` の画像本体
- `objects/*.png`
- `tmp/`, `__pycache__/`, `.venv/`, build / cache / logs
- `CHANGELOG.md`, `RELEASE_NOTES.md`, Git history（公開・履歴調査時を除く）
- 無関係な Issues / docs / projects

## Context Priority

- P0: current task / acceptance / invariant
- P1: target source / matching tests
- P2: direct dependencies / repositories / manifests
- P3: detailed docs / architecture
- P4: history / release notes / unrelated subsystems

## Remote Delta First

複数Chat / Codex / 人間が同じremoteを更新し得るため、必要なら実装前に compact delta を見る。

```powershell
git fetch --prune
.\.venv\Scripts\python.exe scripts\context_snapshot.py --base origin/main
```

full diff は最初から読まず、changed files / diff stat / recent commits で対象を絞ってから必要箇所だけ読む。

## Validation

変更範囲に対応する targeted test を先に実行する。横断契約、共有repository、manifest、release前の変更では `scripts/evaluate_project.py` を使う。
GUI / 描画変更は headless test だけで完了とせず、必要時のみ実画面確認を行う。

## Working Rules

- Search first, read second.
- リポジトリ全体、全docs、全Issuesを無条件に読まない。
- unrelated refactor を現在タスクへ混ぜない。
- 要約は索引。判断に不足する場合は原典へ戻る。
- 成功ログ全文をコンテキストへ残さない。失敗箇所だけ追加取得する。
- 未確認領域は `Unverified` として明示する。
