"""パス・定数の一元管理。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

# プロジェクトルート = このファイルから見て src/keylog/../../
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
DB_PATH = DATA_DIR / "keylog.db"

# エクスポート(PDF/CSV)の既定保存先はユーザーのダウンロードフォルダ
DOWNLOADS_DIR = Path.home() / "Downloads"

# UI フォント(日本語グリフを正しく表示するため Noto Sans JP)
UI_FONT_FAMILY = "Noto Sans JP"

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


def ensure_dirs() -> None:
    """データ・出力ディレクトリを用意する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    """ローカル時刻の naive ISO8601 文字列(秒精度)。全日時をこの形式で統一する。"""
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")
