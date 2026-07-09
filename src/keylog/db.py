"""DB 接続とスキーマ作成。

- 接続ごとに `foreign_keys=ON` / `journal_mode=WAL` を設定する(SQLite 既定は OFF)。
- 二重貸出は部分ユニークインデックスで DB レベルに拒否する(最後の砦)。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    idm        TEXT    UNIQUE,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS keys (
    key_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT    NOT NULL UNIQUE,
    name       TEXT    NOT NULL,
    note       TEXT,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS checkouts (
    checkout_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id         INTEGER NOT NULL REFERENCES keys(key_id),
    user_id        INTEGER NOT NULL REFERENCES users(user_id),
    checked_out_at TEXT    NOT NULL,
    returned_at    TEXT
);

-- 1つの鍵に「未返却」の記録は同時に1件まで(=二重貸出の物理的禁止)
CREATE UNIQUE INDEX IF NOT EXISTS ux_open_checkout
    ON checkouts(key_id) WHERE returned_at IS NULL;

CREATE TABLE IF NOT EXISTS inspections (
    inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    inspected_at  TEXT    NOT NULL,
    inspector     TEXT    NOT NULL,
    result        TEXT    NOT NULL,
    note          TEXT,
    open_snapshot TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    """PRAGMA を適用済みの接続を返す。`:memory:` も可(テスト用)。"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # インメモリ DB では WAL を張れない/意味が無いのでファイル時のみ
    if str(db_path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """テーブル・インデックスを作成する(冪等)。"""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def initialize(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    """ディレクトリ準備 → 接続 → スキーマ作成 まで行い接続を返す。"""
    if str(db_path) != ":memory:":
        config.ensure_dirs()
    conn = connect(db_path)
    init_schema(conn)
    return conn
