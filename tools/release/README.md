# 配布物の作成と真正性の検証

Issue #122（P0 #100 の子）。配布する zip を CI で作り、SHA-256 と GitHub Artifact Attestation で「どのリポジトリのどのワークフローが、どのコミットから作ったか」を検証できるようにする。

## 成果物の一覧

| 成果物 | 中身 | 起動 |
| --- | --- | --- |
| `obake-no-sumika-v<版>-game.zip` | ゲーム本体（`game.py`、`engine/`、アセット、ゲームのJSON、起動用の `tools/security/`） | `run_game.bat` |
| `obake-no-sumika-v<版>-editors.zip` | エディター3種と統合エンジン、それらが編集するゲームデータ一式 | `run_editor.bat`、`run_object_editor.bat`、`run_engine.bat` |
| `SHA256SUMS` | 上の2つの SHA-256 | — |

中身は [manifest.json](manifest.json) が正。ゲーム本体とエディターは別々にリリースする（本人の方針 2026-10-31）。テスト・文書・開発ツール・Godot版は含めない。Godot版・EXE配布は未対応（#54、#12）。

exe・dll・インストーラーは配布していないので、Windows の Authenticode 署名、macOS の codesign/notarization、Android の署名は現時点で対象外。これらを配布する時は #100 の該当項目を実施する。

## 作り方

```powershell
.\.venv\Scripts\python.exe tools/release/script/package.py --ref v0.3.0 --out dist
```

- ファイルは `--ref` のコミットから git で読み出す。作業ツリーの未コミット変更は入らない。
- 同じコミットからは同じ zip になる（ファイル順・時刻・権限を固定）。`.bat` は Windows で正しく動くよう CRLF にする（リポジトリには LF で保存されている）。
- マニフェストのパターンが1つも一致しない、`VERSION` が不正、ref が無いなどは終了コード 2。

## CI（`.github/workflows/release-artifacts.yml`）

| きっかけ | 内容 |
| --- | --- |
| `v*` タグの push、手動実行 | zip と `SHA256SUMS` を作り、2回作って一致を確認し、Artifact Attestation（OIDC の keyless 署名）を付け、`gh attestation verify` で検証して、ワークフローの成果物として30日保存 |
| `work` 宛ての PR | 作成と再現性の確認だけ（Attestation は作らない） |

秘密鍵・証明書は使わない（keyless のため不要）。**GitHub Release への添付・公開はしない。** リリースは Kadoka の確認を得てから、検証済みの成果物を手作業で添付する。

手動実行は、ワークフローが既定ブランチ（`main`）に入ってから使える。タグ push はタグのコミットにこのワークフローがあれば動く。`work` から `main` への統合は #86。

## 利用者向けの検証手順

1. Release から zip と `SHA256SUMS` をダウンロードする。
2. チェックサムを確認する（PowerShell）:

   ```powershell
   Get-FileHash .\obake-no-sumika-v0.3.0-game.zip -Algorithm SHA256
   ```

   表示された値が `SHA256SUMS` の同じファイル名の行と一致すること。
3. 作成元を確認する（[GitHub CLI](https://cli.github.com/) が必要）:

   ```powershell
   gh attestation verify .\obake-no-sumika-v0.3.0-game.zip --repo tomiya7688/obake-no-sumika
   ```

   `Verification succeeded` と、このリポジトリの `release-artifacts.yml` が表示されること。`SHA256SUMS` も同じ方法で確認できる。

## 既存の公開成果物（2026-10-31 時点）

| リリース | 成果物 | 状況 |
| --- | --- | --- |
| v0.2.0 | `obake-no-sumika-v0.2.0-windows.zip` | 手作業でアップロード。Attestation なし。GitHub が記録した SHA-256 は `e89dc2887a816d1b8a6c6041309cd67486a1f445b8a9f9edfff1f77cee8bcd74` |
| v0.1.0-beta.1 | `obake-no-sumika-v0.1.0-beta.1.zip` | 同上。`b378189597efbec3ac5f3d25beb16c9f00e57878496aab230eb19a63047d29ae` |

既存の zip は作成手順が残っておらず、同じ内容を再現して Attestation を後付けすることはできない。差し替え・再リリース・注記の要否は Kadoka が判断する。
