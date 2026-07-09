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
