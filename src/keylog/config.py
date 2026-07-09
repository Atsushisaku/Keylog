"""パス・定数の一元管理。"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# ベースディレクトリ:
# - PyInstaller で凍結(exe)時は exe と同じフォルダ(データが永続化される場所)
# - 通常実行時は src/keylog/../../（プロジェクトルート）
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
DB_PATH = DATA_DIR / "keylog.db"

# エクスポート(PDF/CSV)の既定保存先はユーザーのダウンロードフォルダ
DOWNLOADS_DIR = Path.home() / "Downloads"

# UI フォント候補。先頭から順に「インストール済みの最初のもの」を使う。
# Noto Sans JP が無い配布先でも Windows 標準の日本語フォントで正しく表示するため。
UI_FONT_CANDIDATES = ["Noto Sans JP", "Yu Gothic UI", "Meiryo", "MS Gothic"]

# 初回起動時に投入する管理者 PIN の初期値。
# DB にはソルト付きハッシュで保存されるため、平文が残るのはこの初回投入時のみ。
INITIAL_ADMIN_PIN = "pass"

# PBKDF2 反復回数
PIN_PBKDF2_ITERATIONS = 200_000

# リーダーのポーリング間隔(秒)と、UI 側でキューを drain する間隔(ミリ秒)
READER_POLL_INTERVAL = 0.3
UI_QUEUE_DRAIN_MS = 150

# 単一起動ガードに使うロックファイル
LOCK_PATH = DATA_DIR / "keylog.lock"


def icon_path() -> Path | None:
    """ウィンドウアイコン(.ico)のパスを返す(無ければ None)。

    凍結(exe)時は PyInstaller の展開先(_MEIPASS)に同梱される。
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", BASE_DIR))
        p = base / "Keylog.ico"
    else:
        p = BASE_DIR / "assets" / "Keylog.ico"
    return p if p.exists() else None


def ensure_dirs() -> None:
    """データ・出力ディレクトリを用意する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    """ローカル時刻の naive ISO8601 文字列(秒精度)。全日時をこの形式で統一する。"""
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")
