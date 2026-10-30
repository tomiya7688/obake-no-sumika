<!-- review-procedure-required:2026-10-26 -->
## レビュー手順の確認・実行証跡を必須にする

適用対象はEドライブまたは `C:/Users/tomiy/games` のソースプロジェクト。Learning language / Learning_language / lenguage_learningは複数AIレビュー対象外。主担当・実装担当は各作業の開始時と完了報告前に `E:/projects/REVIEW_OPERATIONS.md` を実際に開き、最新の起動方法・省略条件を確認する。記憶・過去の結果・この入口だけで確認済みとしない。分担する場合は主担当がレビュー担当と証跡保存先を指定し、対象の最終差分を確認する。レビュー専任AIは追加レビュアーを起動しない。

まず `& 'E:/projects/.review-tools/Get-ReviewClients.ps1'` を実行し、共通手順の実体パスと起動口を使う。Continueは `cn`、Antigravityは `agy`。古いPATH、過去の失敗、残量が数値取得できないことだけで未導入・未ログイン・無料不明と判断しない。指定済みの無料経路は1回実際に依頼する。未導入・未ログイン・安全な読取専用設定不可などを今回の検出で確認した場合は依頼せず、その根拠を残す。新規の無料か不明な経路へ送信したり、有料経路へ変更したりしない。

整形・関連テスト・自己レビュー後、Codex gpt-6-luna low、Claude haiku low、Antigravity、Jules、Continue、Qwen Code、Grokの7者それぞれについて、今回の資料SHA256、実行日時、クライアント/モデル、起動コマンド（秘密を除く）、結果ファイル、完了または省略理由を記録する。省略には今回の検出・エラー・タイムアウトの証拠が必要。「手順不明」「おそらく未導入」「以前失敗」「軽微なので不要」は省略理由にしない。手順や権限により確認自体ができない場合は、その障害を具体的に記録し未確認として報告する。枠切れ等は原則90秒・最大180秒、非同期Jules/PRは原則10分の既存期限で打切り、再試行・課金・昇格をしない。

PR作成・更新時は対象HEADに対するCopilotとCodeRabbit両方の依頼/既存依頼の証跡と結果を追加する。完了報告前に7者（PR時は追加2者）の欄と証跡が揃ったことを主担当が照合する。証跡なしは未実施であり、レビュー済み・全工程完了とは報告しない。実際の利用不可を理由付きで省略した場合は作業を続ける。秘密・非公開データの除外、既存の送信許可、全レビュアーの編集禁止は従来どおり。
<!-- /review-procedure-required -->

<!-- shared-review-operations:v2:2026-10-24 -->
## 全プロジェクトの作業レビューとPRレビュー（最新ユーザー指示）

Eドライブまたは `C:/Users/tomiy/games` にソースコードを持つ全プロジェクトに適用する。Learning language / Learning_language / lenguage_learningは除外する。規模・初期段階・Gitの有無で除外しない。この規則は旧「大規模だけ」と旧Luna/Haiku未実施時の停止条件を置き換える。
各作業の実装・関連テスト・自己レビュー後に、Codex `gpt-6-luna` low、Claude `haiku` low、Antigravity無料モデル、Jules無料モデル、Continue CLI無料モデル、Qwen Code無料モデル、Grok CLI無料モデルの7者へそれぞれレビューを依頼する。PR作成・更新時にはGitHub CopilotとCodeRabbitの両方にも依頼する。モデル直接API呼出しを指定CLIによる実施と偽らない。
全員について枠切れ・未応答・接続失敗・未ログイン・未導入・無料か不明なら理由を1行記録して省略し、作業を続ける。無応答は原則90秒（最大180秒）、非同期Jules/PRは原則10分の確認期限で打ち切り、連続再試行・枠待ち・課金・自動昇格をしない。省略を成功にせず、有効な指摘の修正・必須テスト・CI・承認条件は維持する。
AntigravityとGrokは、指定された対象・必要な周辺ファイルの読取を許可する。両者を含む全レビュアーに編集・削除・移動・状態変更・別レビュアー起動をさせない。秘密/認証ファイルは読取許可の対象外。`E:/projects/.review-private/` の読取・復号はCodex/Claude主担当だけが行い、秘密をモデル本文・ログ・Gitへ出さない。
具体的な資料作成、各CLI起動、読取専用設定、タイムアウト、省略、PR依頼、結果記録は `E:/projects/REVIEW_OPERATIONS.md` を参照し、設定済みやdry-runだけで実施済みと報告しない。
<!-- /shared-review-operations -->

# Codex / AI entrypoint

最初に [docs/context/project.md](docs/context/project.md) を読み、対象領域の文書だけを選ぶ。全体説明が必要な場合だけ `README.md` を読む。

## Required roadmap

- 実装を始める前に `docs/開発予定.md` を毎回全文読む。現在はGitHub Issuesを正本とする案内があるので、対象Issueの完了条件と最新コメントも読む。
- 深い設計が必要な機能は、同文書の指示に従って機能説明書を作る。表はMarkdown、図はMermaidを使う。
- 実装完了後は、対応する項目を `docs/開発予定.md` から削除する。Issueは完了条件をすべて満たした時だけCloseする。
- 文書内の対象ファイル名や `doc/`・`docs/` の違いが実装範囲に影響する場合は、推測で直さずユーザーへ確認する。

## 読む範囲と契約

- Search first, read second。Goal / Required / Acceptance / Working set が揃ったら追加探索を止め、不足が見つかった時だけ再開する。
- ソース全体・全docs・全Issue・画像・生成物・履歴を無条件に読まない。要約で判断できない時は原典へ戻る。
- ゲームの不変条件、Source map、データ例、詳細な検証は [開発契約](docs/ai-development-contract.md) の対象節を読む。Godotは [Godot context](docs/context/godot.md)、言語間の仕様は `spec/` と対応する共有テストを正とし、他ランタイム全体を読まない。
- [1回のワークフロー](docs/ワークフロー/ワークフロー.md) に従う。作業前にstatus/fetchを確認し、`work` をff-onlyで更新する。無関係の変更を保持し、今回分だけを明示的にstageする。
- GitHub操作は `gh` CLI。通常開発は検証・最新指摘確認後に `work` へ取り込み、本人のレビュー待ちだけで停止しない。失敗した必須チェック・保留指示は無視しない。main反映・タグ・リリースは本人の承認後に行う。

## 共同作業と役割

- 複数のAIエージェントが同時に作業している。[共同作業ルール](docs/ワークフロー/共同作業ルール.md) に従い、着手するIssueにコメントで表明し、他者のブランチ・未コミット変更を触らない。
- 役割ごとの手順は [役割別ワークフロー](docs/ワークフロー/役割別ワークフロー.md)、PRの判定は [レビュー基準](docs/ワークフロー/レビュー基準.md)。`work` 宛ては自己レビューで取り込んでよいが、Work CIの成功確認は必須。
- 運用・手順が変わったら、その場で共有文書と `.claude/agents/`・`.claude/skills/` の入口を更新する。ルール本文をエージェント個別のメモリにだけ書かない。

## Verification

プロジェクトの `.venv` を使い、対象テストの後に全体評価を行う。Godot実行ファイルを設定して `scripts/evaluate_project.py --require-godot --frames 900` とWork CIの成功を確認する。静的検査・自動実行・描画・実GUI操作・CIの証拠を区別し、未確認を明記する。

UIや描画を変えた場合は、最後に `run_game.bat` と該当エディタを実画面で確認する。GodotのUI・描画変更ではGodot側の該当画面も確認する。headlessテストやスクリーンショットだけを実GUI操作の確認として扱わない。


<!-- post-work-formatter-policy:2026-10-25 -->
## フォーマッターの導入と作業後の自動実行

各プロジェクトの実装担当は、既存の言語・設定・依存管理を確認し、未導入なら適切なformatterを開発用依存/管理済みツールとして導入する。既存formatterを優先し、競合する追加やグローバル最新版への依存を避け、バージョン・設定・対象除外とformat/checkの1コマンド実行方法を整える。
各作業の実装後、今回変更したファイル/モジュールにformatterを自動的に実行し、その後にformat/check・関連テスト・自己レビュー・追加レビューを行う。指摘修正後も必要な再整形と再検証をする。担当外のdirty変更、生成物、vendor、原文保持が必要な教材/サンプルを一括整形しない。整形は実装担当が行い、レビュー専任AIには編集させない。
既存の開発/CI手順に適合する整形確認を整え、実行コマンド・バージョン・対象・結果を完了報告に残す。未実行は理由と残件を記録し、導入済み/設定済みだけで整形済みとしない。詳細は `E:/projects/FORMATTER_OPERATIONS.md`。Learning languageもこの整形指示の対象（複数AIレビューの除外とは別）。
<!-- /post-work-formatter-policy -->

<!-- extra-free-review-policy:2026-10-26 -->
## 追加無料レビュアーの利用と節約

既存7者・PR時2者は維持する。追加導入したMistral Vibe、OpenCodeのGLM/DeepSeek、OpenRouterのCohere/Inkling系は通常1者、重要変更で最大2者を選ぶ。起動口は `E:/projects/.review-tools/Invoke-ExtraFreeReview.ps1`、実体確認は `Get-ExtraFreeReviewClients.ps1`。手順・無料条件・初回認証は `E:/projects/EXTRA_FREE_REVIEW.md` を実際に読む。同一資料を再送せず、差分と必要な根拠に絞る。出力上限2048トークン、OpenRouter追加枠の独自の回数制限・残10回温存は撤廃し、無料モデルのみ利用する。未認証・枠切れ・無料終了・未応答は記録して省略し、課金・昇格・連続再試行をしない。最低限の既知バグ検出を未確認のモデルを検証済みと報告しない。全レビュアーは編集/ツール/秘密読取禁止。Learning languageの複数AIレビュー除外を維持する。
<!-- /extra-free-review-policy -->