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
