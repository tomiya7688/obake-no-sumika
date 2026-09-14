# Context Routing

`ai-context-reducer` 方針に基づき、タスク種別から必要な source / tests / docs だけへ到達するためのルーティング表です。

## Change Routing

| 変更種別 | 最初に読む | 対応テスト | 必要時だけ読む |
|---|---|---|---|
| ゲームAI・移動・会話中挙動 | `game.py` | `tests/test_tagged_conversations.py` | `characters.json`, `conversations.json`, `events.json`, `room.json` |
| キャラクター定義・編集 | `characters.json`, `engine/character_repository.py`, `character_editor.py` | `tests/test_character_repository.py` | `game.py`, `game_content.json` |
| 会話・イベント・タグ | `conversations.json`, `events.json`, `engine/conversation_repository.py`, `engine/event_repository.py` | `tests/test_tagged_conversations.py`, `tests/test_content_repositories.py` | `game.py`, `placed_objects.json` |
| 部屋・水場・背景領域 | `room.json`, `engine/room_repository.py` | `tests/test_room_repository.py` | `game.py`, `object_editor.py` |
| 配置物・オブジェクト編集 | `placed_objects.json`, `engine/placement_repository.py`, `engine/pixel_object_repository.py`, `object_editor.py` | `tests/test_object_editor_tools.py`, `tests/test_content_repositories.py` | `objects/*.source.json` |
| エンジンmanifest / project読込 | `engine_project.json`, `game_content.json`, `engine/manifest_loader.py` | `tests/test_engine_manifest.py` | `docs/エンジン化機能説明書.md` |
| 統合エンジンGUI | `engine_app.py`, `engine/main_window.py` | `tests/test_main_window.py`, `tests/test_engine_manifest.py` | `docs/エンジン化機能説明書.md` |
| 新規プロジェクト生成 | `engine/project_creator.py` | `tests/test_project_creator.py` | `engine/manifest_loader.py` |
| special版分離 | `projects/obakeno_sumika_special/` | `tests/test_special_project_isolation.py` | root側manifest / contentとの差分 |
| 自動評価 | `scripts/evaluate_project.py` | `tests/test_evaluate_project.py` | `docs/自動評価システム機能説明書.md` |
| 評価ログ | `engine/evaluation_logger.py` | `tests/test_evaluation_logger.py` | `docs/評価ログ機能説明書.md`, `game.py` |
| リリース / version | `VERSION` | relevant full suite | `README.md`, `CHANGELOG.md`, `RELEASE_NOTES.md` |

## Responsibility Map

### Game

- `game.py`: 実行時ゲーム、Ghost AI、イベント、描画、会話シーケンス。
- `characters.json`: 実行時キャラクター定義。
- `conversations.json`: 実行時会話デッキ。
- `events.json`: イベントカタログ。
- `room.json`: 部屋・領域・背景定義。
- `placed_objects.json`: 配置物インスタンス。

### Engine

- `engine/manifest_loader.py`: project / content manifest の解決。
- `engine/*_repository.py`: JSONデータの共有I/O・検証。GUIは直接JSONを扱わない。
- `engine/*_definition.py`: 軽量な定義型。
- `engine/main_window.py`: 統合エンジンGUI。
- `engine/project_creator.py`: 新規プロジェクト生成。
- `engine/evaluation_logger.py`: structured runtime observation。

### Developer tools

- `character_editor.py`: キャラクター編集GUI。
- `conversation_editor.py`: 会話編集GUI。
- `object_editor.py`: ドット絵・配置編集GUI。
- `scripts/evaluate_project.py`: 横断評価入口。
- `scripts/context_snapshot.py`: AI向けcompact Git context。

## Validation Routing

最小十分な検証から始める。

```text
single repository / data rule
    -> matching test module

shared manifest / repository contract
    -> matching tests + related content tests

game behavior
    -> matching tests + deterministic headless smoke

engine / GUI behavior
    -> matching tests + --validate; visual acceptance が必要な時だけ実画面

cross-cutting / release candidate
    -> scripts/evaluate_project.py
```

全テストを毎回必須にはしない。ただし shared/core/public contract を変更した場合は broader fallback を使う。

## Remote / Multi-agent Routing

他Chat・Codex・手動編集が並行する場合は、まず以下だけ取得する。

1. branch / working tree
2. baseとの差分ファイル
3. diff stat
4. recent commit subjects

```powershell
.\.venv\Scripts\python.exe scripts\context_snapshot.py --base origin/main
```

この出力だけで対象が特定できなければ `git diff -- <path>` へ進む。最初から full diff / full history は読まない。

## Exploration Boundaries

- `assets/`, PNG本体、生成物は変更対象のときだけ読む。
- 巨大ファイルは、まず class / function / keyword 検索で対象symbolを絞る。
- `README.md` はユーザー向け全体説明が必要な場合だけ読む。
- `AGENTS.md` は詳細契約が必要になった節だけ読む。
- `docs/開発予定.md` は通常は対象節を検索し、ロードマップ横断判断時だけ全文を読む。

## Adoption Notes

導入済み:

- compact AI entrypoint
- Search first / read second
- Goal / Required / Acceptance による探索停止
- Source of Truth 明示
- Task / Change Routing
- Responsibility Map
- Remote Delta First
- targeted validation / Unverified

現時点で未導入:

- 大規模 Source Structure Index: 現状はrouting mapで十分。
- changed-symbol自動索引: 維持コストがまだ大きい。
- 複雑な要約キャッシュ: stale化リスクを避ける。
- subsystemごとの大量AI guide: root + routingで十分。
