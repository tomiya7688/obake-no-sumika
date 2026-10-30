# Python取得基盤の緊急bootstrap（Issue #99 / #105 / #111）

リポジトリ直下から、対象venvのPythonを明示する。既定は読取専用の版・CAファイル確認で、旧版/欠落は終了1、判定/更新失敗は終了2。`--apply` だけが更新を許可する。Python 3.10以上と既存pipが必要。

```powershell
.\.venv\Scripts\python.exe -I -B tools/security/script/bootstrap.py
.\.venv\Scripts\python.exe -I -B tools/security/script/bootstrap.py --apply
```

最低版はpip 26.2.2 / certifi 2026.10.19。旧版/欠落だけを公式SHA256付きwheelで更新し、pipを先に処理する。満たしている新しい版は降格しない。未知の版表記（pre/dev/local版を含む）は自動更新せず非0で止め、手動で確認する。

pip自体が欠落した場合は自動導入せず終了2にする。対象Pythonの `ensurepip` でpipを準備してから再実行する。Work CIは依存導入前に更新し、導入後にも読取専用checkで下限を再確認する。

base Pythonは暗黙に変更しない。CIの管理済みruntimeだけは明示した `--managed-runtime` で更新を許可する。別のvenv・OS証明書・global Pythonを走査/更新する機能はない。TLS検証の無効化やtrusted-hostは使わない。

出力の `bundles` は実際の `certifi.where()` とpip内蔵certifiのファイルパス/内容SHA256、PEM証明書数、既知の問題rootのDER指紋照合結果。**既知rootの内容点検であり、全証明書チェーンの拒否やOS信頼ストアの更新確認ではない**（`chains_verified: false`）。Python本体、uv/sigstore、配布物、main側CIなどの全環境対応は親Issue #99に残る。

## 実CA bundleの内容点検（Issue #115）

`ca_count` は重複や非CA証明書を除くため、PEMブロック数の `certificate_count` と異なり得る。既知rootの照合は解析済みCAに対して行い、両数の一致や全TLS検証を主張しない。

選択Pythonが返す2つの実ファイルを各8MiB以下の同じ読取snapshotで検査する。標準ライブラリの独立したSSLContextでPEM/X.509を解析し、証明書のDER SHA256を照合する。OSのdefault CAやネットワークは使わず、ファイルも変更しない。PEMコメントや改行を変えてもDERの一致判定は変わらない。

`certificate_count` はPEM証明書の数（重複も数える）、`ca_count` は独立contextに読み込まれたCA数、`known_roots_checked` は照合リストの件数、`distrusted_roots` は一致した名前/DER SHA256。OpenSSLが解析したCAのDERを照合するため、PEM内のDER末尾にデータを付けても同じrootを見逃さない。標準のCERTIFICATE以外のPEMブロックは、混在時も未対応として拒否する。現在の対象は `emSign ECC Root CA - G3` の1件。出典はcertifiの[修正前69494a7と復元662df63の差分](https://github.com/certifi/python-certifi/compare/69494a764d0a08f90838d53d4b0fefd3e84045d6...662df63d7906df66f1f07c0751a3dfe9da14d914)。影響のないemSign rootは名前だけで拒否しない。

既知対象が残っていれば版を満たしていても終了1、空/不完全/解析不能/大きすぎるbundleは終了2。`--apply` でも安全な版の不正bundleを黙って上書きしない。診断後、全準備プロセスを止めて信頼できるwheelからの再導入を手動で検討する。既存の取得前/起動前ゲートも非0なら未起動になる。

この1件が無いことを、失効した中間証明書のSPKI・別rootを経由するcross-sign・環境変数のCA上書き・OS信頼・すべてのTLS経路の安全証明として扱わない。公開fixtureの出典は [tests/fixtures/security](../../tests/fixtures/security/README.md)、回帰は `python -m unittest tests.test_python_security -v`。

## CA環境上書きの取得前点検

非空の `PIP_CERT` / `REQUESTS_CA_BUNDLE` / `CURL_CA_BUNDLE` / `SSL_CERT_FILE` は、更新より先に同じ8MiB上限・隔離DER指紋検査を全件実施する。正常なら従来の更新へ進み、既知rootがあれば `--apply` でも更新せず終了1。不正・欠落・非ファイルや解析不能は終了2。非空の `SSL_CERT_DIR` はディレクトリ実監査が未対応のため終了2。空/未設定は従来の動作を維持する。

追加JSON `environment_bundles` は変数名から内容SHA/PEM数/CA数/既知対象結果への対応。追加項目と上書きエラーは値やパスを含めず、環境やファイルを変更しない（従来の `python` / `bundles` には既定のPython/CAパスが残る）。相対パスは実行時cwdから解決する。複数指定は、クライアントごとの優先順位を推測せず全件検査する保守的な条件であり、有効なTLS経路を特定したという意味ではない。点検時点のsnapshotであり、後続利用までファイルを固定するものではない。

根拠: [pip HTTPS Certificates](https://pip.pypa.io/en/stable/topics/https-certificates/)、[Requests SSL Cert Verification](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification)、[Python SSL default paths](https://docs.python.org/3/library/ssl.html#ssl.get_default_verify_paths)。ディレクトリ指定を使う環境は、値を消して迂回せず実際の信頼元を手動点検する。pip設定ファイル/CLI指定、OS既定ストア、全TLSチェーン/中間SPKI/cross-signの点検は引き続き親#99に残る。`chains_verified:false` を維持する。

## Windowsの4起動バッチ

`run_game.bat` / `run_engine.bat` / `run_object_editor.bat` / `run_editor.bat` は、プロジェクトの `.venv` を準備した後、次の順で起動する。

1. 上記bootstrapの `--apply`。古いpip/certifiだけを更新し、失敗したら依存取得もアプリ起動もしない。既存venvはglobal PythonがPATHになくても検査・起動できる（venvが参照するbase Pythonの実体は必要）。
2. ゲーム/統合GUI/オブジェクトエディタは必要なimportが不足した時だけ `requirements.txt` を導入。会話エディタは標準ライブラリのTkinterを確認し、不要なpygame/Pillowは導入しない。いずれも失敗したら停止。
3. bootstrapの読取専用checkで最低版/CAファイルを再確認し、成功時だけアプリを起動。

会話エディタも同じvenvを使う。従来のglobal `pyw` / `py` へのフォールバックは行わず、global Pythonのパッケージは更新しない。エラー時はコンソールに原因を表示し、キー入力後に非0で終了する。pip欠落時は `.\.venv\Scripts\python.exe -m ensurepip` を実行し、**ほかの依存を取得する前に**冒頭のbootstrapを実行する。ゲーム/GUIの実行中監視やOS/全チェーンの検証を追加したものではない。

回帰テスト: `python -m unittest tests.test_windows_security_launchers -v`。静的な契約/責務選択は全OSで実行し、実Windows CMDの34ケースはWindowsだけで実行する。空白・日本語パスと別cwd、既存依存/不足依存、初回検査/取得/再検査の失敗（終了1と2、依存導入成功後の再検査失敗も含む）、GUI用pythonw欠落、会話エディタでpygame/Pillow不要をfixtureで検証する（外部取得・実GUI操作の証拠ではない）。

安全な版を満たす環境はbootstrapで再取得しない。旧版/不足の修復が必要な時は、オフラインなら失敗して起動しない。pip欠落や部分的に作られたvenvは上記ensurepipで手動復旧する。既存venvを自動削除することはない。

### 共有venvの準備ロック（Issue #113）

4バッチとREADMEの手動起動は `launch.py` を使う。venv作成/apply/必要な依存導入の間だけproject内 `.venv-setup.lock/` を排他的に作成し、既定300秒まで待機する。通常は準備終了時に自分のtokenだけ解放し、その後の読取専用checkに成功した場合だけ起動する。アプリの終了待ちにはロックを持ち込まない。

強制終了/Ctrl+Cのロックは残し、PID不在や経過時間だけで自動削除しない。子pipが残っている可能性があるため、利用者が該当projectの全準備プロセス終了を確認した後だけ、`python -I -B tools/security/script/launch.py --recover-lock <owner-token> --confirm-no-setup-processes` で明示回収する。稼働中/状態不明のPID、不一致token、壊れたmetadataは回収拒否。詳しくは[設計と復旧手順](../../docs/venv起動機能説明書.md)。

手動pip/ensurepip・IDE・CIなど共通入口を通らない更新は調停しない。同時に実行しないこと。実行中アプリと依存の差替え、OS/全TLSの安全性、実GUI準備完了はこのロックの保証外。

`-I` はPythonの隔離実行であり、pipの `PIP_*` 設定やCA上書きを一律に無効化するものではない。上記4つのCAファイル環境指定は内容点検するが、取得先・その他の設定・OS信頼ストアを含む実際のTLS経路の検証は親Issue #99の残件とする。

根拠と固定wheelの出典:

- [Python公式のセキュリティ告知とpipのURL/SHA256](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)
- [certifi公式アドバイザリ](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)
- [certifi 2026.10.19のPyPI公式wheelメタデータ](https://pypi.org/pypi/certifi/2026.10.19/json)

Ruffの整形/checkは今回変更したPythonファイルを引数で明示し、[品質手順](../quality/README.md)に従う。関連テストは `python -m unittest tests.test_python_security tests.test_context_selection tests.test_ruff_baseline -v`。
