"""DB アクセス層(CRUD)。業務ルールは持たず、素直な読み書きだけを担う。

全関数は sqlite3.Connection を第1引数に取り、行は sqlite3.Row を返す。
commit は呼び出し側(services)が行う方針だが、単純な更新系はここで commit する。
"""
from __future__ import annotations

import sqlite3

from .config import now_iso

Row = sqlite3.Row

# ---------------------------------------------------------------- users


def create_user(conn: sqlite3.Connection, name: str, idm: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO users (name, idm, active, created_at) VALUES (?, ?, 1, ?)",
        (name, idm, now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_user(conn: sqlite3.Connection, user_id: int) -> Row | None:
    return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def get_user_by_idm(conn: sqlite3.Connection, idm: str) -> Row | None:
    return conn.execute("SELECT * FROM users WHERE idm = ?", (idm,)).fetchone()


def list_users(conn: sqlite3.Connection, include_inactive: bool = False) -> list[Row]:
    sql = "SELECT * FROM users"
    if not include_inactive:
        sql += " WHERE active = 1"
    sql += " ORDER BY name"
    return conn.execute(sql).fetchall()


def update_user_name(conn: sqlite3.Connection, user_id: int, name: str) -> None:
    conn.execute("UPDATE users SET name = ? WHERE user_id = ?", (name, user_id))
    conn.commit()


def set_user_idm(conn: sqlite3.Connection, user_id: int, idm: str | None) -> None:
    conn.execute("UPDATE users SET idm = ? WHERE user_id = ?", (idm, user_id))
    conn.commit()


def set_user_active(conn: sqlite3.Connection, user_id: int, active: bool) -> None:
    conn.execute(
        "UPDATE users SET active = ? WHERE user_id = ?", (1 if active else 0, user_id)
    )
    conn.commit()


# ---------------------------------------------------------------- keys


def create_key(
    conn: sqlite3.Connection, code: str, name: str, note: str | None = None
) -> int:
    cur = conn.execute(
        "INSERT INTO keys (code, name, note, active, created_at) VALUES (?, ?, ?, 1, ?)",
        (code, name, note, now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_key(conn: sqlite3.Connection, key_id: int) -> Row | None:
    return conn.execute("SELECT * FROM keys WHERE key_id = ?", (key_id,)).fetchone()


def get_key_by_code(conn: sqlite3.Connection, code: str) -> Row | None:
    return conn.execute("SELECT * FROM keys WHERE code = ?", (code,)).fetchone()


def list_keys(conn: sqlite3.Connection, include_inactive: bool = False) -> list[Row]:
    sql = "SELECT * FROM keys"
    if not include_inactive:
        sql += " WHERE active = 1"
    sql += " ORDER BY code"
    return conn.execute(sql).fetchall()


def list_available_keys(conn: sqlite3.Connection) -> list[Row]:
    """在庫中(貸出中でない) かつ有効な鍵。"""
    return conn.execute(
        """
        SELECT k.* FROM keys k
        WHERE k.active = 1
          AND NOT EXISTS (
              SELECT 1 FROM checkouts c
              WHERE c.key_id = k.key_id AND c.returned_at IS NULL
          )
        ORDER BY k.code
        """
    ).fetchall()


def update_key(
    conn: sqlite3.Connection, key_id: int, code: str, name: str, note: str | None
) -> None:
    conn.execute(
        "UPDATE keys SET code = ?, name = ?, note = ? WHERE key_id = ?",
        (code, name, note, key_id),
    )
    conn.commit()


def set_key_active(conn: sqlite3.Connection, key_id: int, active: bool) -> None:
    conn.execute(
        "UPDATE keys SET active = ? WHERE key_id = ?", (1 if active else 0, key_id)
    )
    conn.commit()


# ---------------------------------------------------------------- checkouts


def create_checkout(
    conn: sqlite3.Connection, key_id: int, user_id: int, when: str | None = None
) -> int:
    cur = conn.execute(
        "INSERT INTO checkouts (key_id, user_id, checked_out_at) VALUES (?, ?, ?)",
        (key_id, user_id, when or now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def close_checkout(
    conn: sqlite3.Connection, checkout_id: int, when: str | None = None
) -> None:
    conn.execute(
        "UPDATE checkouts SET returned_at = ? WHERE checkout_id = ?",
        (when or now_iso(), checkout_id),
    )
    conn.commit()


def get_open_checkout_for_key(conn: sqlite3.Connection, key_id: int) -> Row | None:
    return conn.execute(
        "SELECT * FROM checkouts WHERE key_id = ? AND returned_at IS NULL", (key_id,)
    ).fetchone()


def list_open_checkouts(conn: sqlite3.Connection) -> list[Row]:
    """現在貸出中の一覧(利用者名・鍵情報を結合)。active を無視して全件返す。"""
    return conn.execute(
        """
        SELECT c.checkout_id, c.checked_out_at,
               u.user_id, u.name AS user_name, u.active AS user_active,
               k.key_id, k.code AS key_code, k.name AS key_name, k.active AS key_active
        FROM checkouts c
        JOIN users u ON u.user_id = c.user_id
        JOIN keys  k ON k.key_id  = c.key_id
        WHERE c.returned_at IS NULL
        ORDER BY c.checked_out_at
        """
    ).fetchall()


def list_open_checkouts_for_user(conn: sqlite3.Connection, user_id: int) -> list[Row]:
    """指定利用者が借用中の鍵一覧。"""
    return conn.execute(
        """
        SELECT c.checkout_id, c.checked_out_at,
               k.key_id, k.code AS key_code, k.name AS key_name
        FROM checkouts c
        JOIN keys k ON k.key_id = c.key_id
        WHERE c.returned_at IS NULL AND c.user_id = ?
        ORDER BY c.checked_out_at
        """,
        (user_id,),
    ).fetchall()


def list_checkouts_for_key(
    conn: sqlite3.Connection, key_id: int, start: str | None = None, end: str | None = None
) -> list[Row]:
    """鍵別の使用履歴。期間(checked_out_at)で絞れる。PDF レポート用。"""
    sql = [
        """
        SELECT c.checkout_id, c.checked_out_at, c.returned_at,
               u.name AS user_name
        FROM checkouts c
        JOIN users u ON u.user_id = c.user_id
        WHERE c.key_id = ?
        """
    ]
    params: list[object] = [key_id]
    if start:
        sql.append("AND c.checked_out_at >= ?")
        params.append(start)
    if end:
        sql.append("AND c.checked_out_at <= ?")
        params.append(end)
    sql.append("ORDER BY c.checked_out_at")
    return conn.execute(" ".join(sql), params).fetchall()


def get_checkout(conn: sqlite3.Connection, checkout_id: int) -> Row | None:
    return conn.execute(
        "SELECT * FROM checkouts WHERE checkout_id = ?", (checkout_id,)
    ).fetchone()


def delete_checkout(conn: sqlite3.Connection, checkout_id: int) -> None:
    conn.execute("DELETE FROM checkouts WHERE checkout_id = ?", (checkout_id,))
    conn.commit()


# ---------------------------------------------------------------- inspections


def create_inspection(
    conn: sqlite3.Connection,
    inspector: str,
    result: str,
    note: str | None,
    checklist: str | None,
    all_returned: bool,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO inspections
            (inspected_at, inspector, result, note, checklist, all_returned)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (now_iso(), inspector, result, note, checklist, 1 if all_returned else 0),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_inspections(conn: sqlite3.Connection) -> list[Row]:
    return conn.execute(
        "SELECT * FROM inspections ORDER BY inspected_at DESC"
    ).fetchall()


# ---------------------------------------------------------------- settings


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
