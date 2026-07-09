"""models(CRUD)層の基本動作。"""
from __future__ import annotations

from keylog import models


def test_create_and_get_user(conn):
    uid = models.create_user(conn, "田中", "IDM-1")
    row = models.get_user(conn, uid)
    assert row["name"] == "田中"
    assert row["idm"] == "IDM-1"
    assert row["active"] == 1
    assert row["created_at"]


def test_get_user_by_idm(conn):
    uid = models.create_user(conn, "田中", "IDM-1")
    assert models.get_user_by_idm(conn, "IDM-1")["user_id"] == uid
    assert models.get_user_by_idm(conn, "NOPE") is None


def test_list_users_excludes_inactive_by_default(conn):
    a = models.create_user(conn, "有効", "IDM-A")
    b = models.create_user(conn, "無効", "IDM-B")
    models.set_user_active(conn, b, False)
    ids_active = {r["user_id"] for r in models.list_users(conn)}
    assert a in ids_active and b not in ids_active
    ids_all = {r["user_id"] for r in models.list_users(conn, include_inactive=True)}
    assert {a, b} <= ids_all


def test_create_and_get_key(conn):
    kid = models.create_key(conn, "K-9", "倉庫", note="メモ")
    row = models.get_key(conn, kid)
    assert row["code"] == "K-9"
    assert row["name"] == "倉庫"
    assert row["note"] == "メモ"
    assert row["active"] == 1


def test_get_key_by_code(conn):
    kid = models.create_key(conn, "K-9", "倉庫")
    assert models.get_key_by_code(conn, "K-9")["key_id"] == kid
    assert models.get_key_by_code(conn, "ZZ") is None


def test_list_available_keys_reflects_checkout(conn):
    uid = models.create_user(conn, "u", "IDM-U")
    kid = models.create_key(conn, "K-1", "k")
    codes = [r["code"] for r in models.list_available_keys(conn)]
    assert "K-1" in codes
    cid = models.create_checkout(conn, kid, uid)
    codes = [r["code"] for r in models.list_available_keys(conn)]
    assert "K-1" not in codes  # 貸出中は在庫から消える
    models.close_checkout(conn, cid)
    codes = [r["code"] for r in models.list_available_keys(conn)]
    assert "K-1" in codes  # 返却で在庫に戻る


def test_list_available_keys_excludes_inactive(conn):
    kid = models.create_key(conn, "K-1", "k")
    models.set_key_active(conn, kid, False)
    codes = [r["code"] for r in models.list_available_keys(conn)]
    assert "K-1" not in codes


def test_setting_roundtrip_and_upsert(conn):
    assert models.get_setting(conn, "x") is None
    models.set_setting(conn, "x", "1")
    assert models.get_setting(conn, "x") == "1"
    models.set_setting(conn, "x", "2")  # ON CONFLICT で更新
    assert models.get_setting(conn, "x") == "2"
