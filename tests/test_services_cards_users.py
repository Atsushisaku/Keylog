"""カード判定・利用者登録・無効化ガードの業務ルール。"""
from __future__ import annotations

import pytest

from keylog import models, services


# --- ルール5: カード判定 resolve_card ------------------------------------


def test_resolve_card_unknown(conn):
    res = services.resolve_card(conn, "IDM-NOPE")
    assert res.status is services.CardStatus.UNKNOWN
    assert res.user is None


def test_resolve_card_inactive(conn):
    uid = models.create_user(conn, "退職者", "IDM-X")
    models.set_user_active(conn, uid, False)
    res = services.resolve_card(conn, "IDM-X")
    assert res.status is services.CardStatus.INACTIVE
    assert res.user["user_id"] == uid


def test_resolve_card_ok(conn):
    uid = models.create_user(conn, "現役", "IDM-Y")
    res = services.resolve_card(conn, "IDM-Y")
    assert res.status is services.CardStatus.OK
    assert res.user["user_id"] == uid


# --- ルール6: 登録の重複防止 ---------------------------------------------


def test_register_user_with_card_success(conn):
    uid = services.register_user_with_card(conn, "新人", "IDM-NEW")
    assert models.get_user(conn, uid)["idm"] == "IDM-NEW"


def test_register_user_with_duplicate_idm_raises(conn):
    services.register_user_with_card(conn, "先客", "IDM-DUP")
    with pytest.raises(services.DuplicateIdmError):
        services.register_user_with_card(conn, "後客", "IDM-DUP")


def test_register_user_with_blank_name_raises(conn):
    with pytest.raises(services.KeylogError):
        services.register_user_with_card(conn, "   ", "IDM-Z")


def test_assign_card_to_other_users_idm_raises(conn):
    a = models.create_user(conn, "A", "IDM-A")
    b = models.create_user(conn, "B", "IDM-B")
    with pytest.raises(services.DuplicateIdmError):
        services.assign_card_to_user(conn, b, "IDM-A")
    # b の idm は変わっていない
    assert models.get_user(conn, b)["idm"] == "IDM-B"


def test_assign_card_same_user_is_ok(conn):
    a = models.create_user(conn, "A", "IDM-A")
    # 自分の idm を再設定するのは許容
    services.assign_card_to_user(conn, a, "IDM-A")
    assert models.get_user(conn, a)["idm"] == "IDM-A"


def test_assign_new_card_to_user(conn):
    a = models.create_user(conn, "A", None)
    services.assign_card_to_user(conn, a, "IDM-FRESH")
    assert models.get_user(conn, a)["idm"] == "IDM-FRESH"


# --- ルール7: 無効化ガード -----------------------------------------------


def test_deactivate_user_with_open_checkout_raises(conn):
    uid = models.create_user(conn, "借主", "IDM-H")
    kid = models.create_key(conn, "K-H", "鍵")
    services.checkout_key(conn, uid, kid)
    with pytest.raises(services.HasOpenCheckoutError):
        services.deactivate_user(conn, uid)
    # 失敗時は有効なまま・idm も残る
    row = models.get_user(conn, uid)
    assert row["active"] == 1
    assert row["idm"] == "IDM-H"


def test_deactivate_user_releases_idm(conn):
    uid = models.create_user(conn, "退職予定", "IDM-REL")
    services.deactivate_user(conn, uid)
    row = models.get_user(conn, uid)
    assert row["active"] == 0
    assert row["idm"] is None  # idm が解放されている


def test_deactivate_user_frees_idm_for_reuse(conn):
    uid = models.create_user(conn, "退職者", "IDM-SHARED")
    services.deactivate_user(conn, uid)
    # 解放後は同じ idm を別利用者に登録できる
    new_uid = services.register_user_with_card(conn, "新人", "IDM-SHARED")
    assert new_uid != uid


def test_discard_key_with_open_checkout_raises(conn):
    uid = models.create_user(conn, "u", "IDM-D")
    kid = models.create_key(conn, "K-D", "鍵")
    services.checkout_key(conn, uid, kid)
    with pytest.raises(services.HasOpenCheckoutError):
        services.discard_key(conn, kid)
    assert models.get_key(conn, kid)["active"] == 1


def test_discard_available_key_succeeds(conn):
    kid = models.create_key(conn, "K-D", "鍵")
    services.discard_key(conn, kid)
    assert models.get_key(conn, kid)["active"] == 0
