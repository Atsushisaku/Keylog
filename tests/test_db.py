"""DB 接続・スキーマ・DB レベルの二重貸出防止インデックス。"""
from __future__ import annotations

import sqlite3

import pytest

from keylog import db, models


def test_initialize_returns_usable_connection():
    conn = db.initialize(":memory:")
    try:
        # スキーマの全テーブルが存在する
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"users", "keys", "checkouts", "inspections", "settings"} <= names
    finally:
        conn.close()


def test_foreign_keys_enabled():
    conn = db.connect(":memory:")
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_init_schema_is_idempotent(conn):
    # 二度呼んでも例外にならない
    db.init_schema(conn)
    db.init_schema(conn)


def test_partial_unique_index_blocks_double_open_checkout(conn):
    """DB レベル: 同じ鍵に未返却レコードは同時 1 件まで。"""
    uid = models.create_user(conn, "u", "IDM-A")
    kid = models.create_key(conn, "K-1", "k")
    models.create_checkout(conn, kid, uid)
    with pytest.raises(sqlite3.IntegrityError):
        models.create_checkout(conn, kid, uid)


def test_index_allows_reuse_after_return(conn):
    """返却済みになれば同じ鍵を再び貸出できる(部分インデックスの条件)。"""
    uid = models.create_user(conn, "u", "IDM-A")
    kid = models.create_key(conn, "K-1", "k")
    cid = models.create_checkout(conn, kid, uid)
    models.close_checkout(conn, cid)
    # 例外が出ないこと
    models.create_checkout(conn, kid, uid)
