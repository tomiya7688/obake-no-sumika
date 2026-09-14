# Codex / AI entrypoint

このファイルは短いルーターです。詳細仕様をここへ複製しません。

## Read order

1. `AI_CONTEXT.md`
2. 現在の Issue / 依頼
3. `docs/context-routing.md` で対象 source / tests を選ぶ
4. 必要な場合だけ `docs/ai-development-contract.md` の該当節
5. ロードマップ判断が必要な場合だけ `docs/開発予定.md`

## Core rules

- Search first, read second。
- Goal / Required / Acceptance / working set が揃ったら探索を止める。
- リポジトリ全体・全docs・全Issuesを無条件に読まない。
- unrelated refactor を現在タスクへ混ぜない。
- 要約で判断できない場合は原典へ戻る。
- generated files / logs / assets / history は対象時だけ読む。
- 成功ログ全文は残さず、失敗箇所だけ追加取得する。
- 未確認領域は `Unverified` として明示する。

## Source of Truth

- 開発予定・優先順位: `docs/開発予定.md`
- 詳細なProject / Data / Safe workflow契約: `docs/ai-development-contract.md`
- エンジン設計: `docs/エンジン化機能説明書.md`
- 現在できること: `key_info.md`
- 実装・テスト: source / `tests/`
- タスク: GitHub Issues

## Remote delta

複数Chat / Codex / 人間が並行して更新し得るため、必要ならfull diffより先にcompact snapshotを見る。

```powershell
git fetch --prune
.\.venv\Scripts\python.exe scripts\context_snapshot.py --base origin/main
```

## Validation

まず `docs/context-routing.md` の対応テストを実行する。shared/core/public contract や横断変更では broader validation に広げる。

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_project.py
```

GUI / 描画変更は、Acceptance に必要な場合だけ実画面確認を追加する。
