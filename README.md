# Keylog — 鍵管理簿アプリ

部屋・保管庫などの**物理鍵の貸出・返却**を、FeliCa 内蔵の **IC カード**（社員証等）で
利用者を特定しながら記録するデスクトップ台帳アプリ。

- 詳細仕様: [SPEC.md](SPEC.md)
- 用語: 鍵=物理キー / IC カード=人を特定する FeliCa / 利用者 / 貸出記録

## 動作環境
- Windows 11
- カードリーダー: SONY RC-S300（`SONY FeliCa Port/PaSoRi 4.0`）
- Python >=3.10（uv が管理）、SQLite

## セットアップ
```bash
uv sync                 # .venv 作成 + 依存インストール
```

## 起動
```bash
uv run python run.py                 # アプリ本体
uv run python tools/read_test.py     # カード読み取り確認（開発用）
```

## データとバックアップ
- 全データは `data/keylog.db`（SQLite 単一ファイル）に保存される。
- **バックアップはこのファイルをコピーするだけ**。定期的に別媒体へ退避すること。
- `data/` と `exports/`（PDF/CSV 出力先）はリポジトリ管理外（`.gitignore`）。

## スタンドアロン配布（exe 化）

Python 環境の無い PC で動かす場合は、PyInstaller で単一 exe にビルドする。

```bash
uv sync                        # 初回のみ(pyinstaller を含む dev 依存を導入)
uv run pyinstaller keylog.spec # dist/Keylog.exe を生成(単一ファイル)
```

**配布と実行**
- `dist/Keylog.exe` を対象 PC の**書き込み可能なフォルダ**にコピーして実行する
  （`data/` と `exports/` は exe と同じ場所に作られるため、Program Files 直下は避ける）。
- **Python のインストールは不要**。
- 対象 PC に **SONY RC-S300 のドライバ**が入っていること（PC/SC は Windows 標準）。
- フォントは Noto Sans JP があればそれを、無ければ Windows 標準の **Yu Gothic UI** に自動フォールバック
  するため、日本語は正しく表示される。
- 未署名 exe のため初回起動時に SmartScreen 警告が出ることがある
  （「詳細情報」→「実行」で起動可）。

## 管理者 PIN
- マスタ編集（利用者・鍵の登録/編集/削除）と点検記録は管理者 PIN が必要。
- 初期 PIN はセットアップ時に設定（詳細は SPEC.md §11）。

## ライセンス

Copyright (C) 2026 Atsushisaku

本プロジェクトは **GNU General Public License v3.0 以降 (GPL-3.0-or-later)** で公開しています。
全文は [LICENSE](LICENSE) を参照してください。

日付ピッカーに用いている **tkcalendar が GPLv3** のため、プロジェクト全体を GPLv3 互換で
公開しています（コピーレフト）。再配布する場合はソース公開等の GPLv3 の条件に従ってください。

### 使用しているサードパーティ・ライブラリ

| ライブラリ | ライセンス |
|---|---|
| tkcalendar | GPL-3.0 |
| pyscard | LGPL-2.1+ |
| customtkinter | CC0-1.0 |
| reportlab | BSD-3-Clause |
| pillow | HPND (MIT-CMU) |
| babel / darkdetect | BSD-3-Clause |
| packaging | Apache-2.0 / BSD-2-Clause |
| charset-normalizer | MIT |

※ 日本語表示に用いる Noto Sans JP は OS 導入済みのシステムフォントを参照しており、
本リポジトリには同梱していません。
