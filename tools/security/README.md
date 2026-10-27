# Python取得基盤の緊急bootstrap（Issue #99 / #105 / #111）

リポジトリ直下から、対象venvのPythonを明示する。既定は読取専用の版・CAファイル確認で、旧版/欠落は終了1、判定/更新失敗は終了2。`--apply` だけが更新を許可する。Python 3.10以上と既存pipが必要。

```powershell
.\.venv\Scripts\python.exe -I -B tools/security/script/bootstrap.py
.\.venv\Scripts\python.exe -I -B tools/security/script/bootstrap.py --apply
```

最低版はpip 26.2.2 / certifi 2026.10.19。旧版/欠落だけを公式SHA256付きwheelで更新し、pipを先に処理する。満たしている新しい版は降格しない。未知の版表記（pre/dev/local版を含む）は自動更新せず非0で止め、手動で確認する。

pip自体が欠落した場合は自動導入せず終了2にする。対象Pythonの `ensurepip` でpipを準備してから再実行する。Work CIは依存導入前に更新し、導入後にも読取専用checkで下限を再確認する。

base Pythonは暗黙に変更しない。CIの管理済みruntimeだけは明示した `--managed-runtime` で更新を許可する。別のvenv・OS証明書・global Pythonを走査/更新する機能はない。TLS検証の無効化やtrusted-hostは使わない。

出力の `bundles` は実際の `certifi.where()` とpip内蔵certifiのファイルパス/内容SHA256。**版とCAファイルの点検であり、全証明書チェーンの拒否やOS信頼ストアの更新確認ではない**（`chains_verified: false`）。Python本体、uv/sigstore、配布物、main側CIなどの全環境対応は親Issue #99に残る。

## Windowsの4起動バッチ

`run_game.bat` / `run_engine.bat` / `run_object_editor.bat` / `run_editor.bat` は、プロジェクトの `.venv` を準備した後、次の順で起動する。

1. 上記bootstrapの `--apply`。古いpip/certifiだけを更新し、失敗したら依存取得もアプリ起動もしない。既存venvはglobal PythonがPATHになくても検査・起動できる（venvが参照するbase Pythonの実体は必要）。
2. 必要なimportが不足した時だけ `requirements.txt` を導入。失敗したら停止。
3. bootstrapの読取専用checkで最低版/CAファイルを再確認し、成功時だけアプリを起動。

会話エディタも同じvenvを使う。従来のglobal `pyw` / `py` へのフォールバックは行わず、global Pythonのパッケージは更新しない。エラー時はコンソールに原因を表示し、キー入力後に非0で終了する。pip欠落時は `.\.venv\Scripts\python.exe -m ensurepip` を実行し、**ほかの依存を取得する前に**冒頭のbootstrapを実行する。ゲーム/GUIの実行中監視やOS/全チェーンの検証を追加したものではない。

回帰テスト: `python -m unittest tests.test_windows_security_launchers -v`。静的な契約/責務選択は全OSで実行し、実Windows CMDの32ケースはWindowsだけで実行する。空白・日本語パスと別cwd、既存依存/不足依存、初回検査/取得/再検査の失敗（終了1と2、依存導入成功後の再検査失敗も含む）をfixtureで検証する（外部取得・実GUI操作の証拠ではない）。

`-I` はPythonの隔離実行であり、pipの `PIP_*` 設定や `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` 等のCA上書きを一律に無効化するものではない。取得先・CA上書き・OS信頼ストアを含む実際のTLS経路の検証は親Issue #99の残件とする。

根拠と固定wheelの出典:

- [Python公式のセキュリティ告知とpipのURL/SHA256](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)
- [certifi公式アドバイザリ](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)
- [certifi 2026.10.19のPyPI公式wheelメタデータ](https://pypi.org/pypi/certifi/2026.10.19/json)

Ruffの整形/checkは今回変更したPythonファイルを引数で明示し、[品質手順](../quality/README.md)に従う。関連テストは `python -m unittest tests.test_python_security tests.test_context_selection tests.test_ruff_baseline -v`。
