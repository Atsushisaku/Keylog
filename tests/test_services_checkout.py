"""貸出/返却の業務ルール(SPEC 由来)。"""
from __future__ import annotations

import pytest

from keylog import models, services


# --- ルール1: 二重貸出防止 --------------------------------------------------


def test_double_checkout_is_rejected(conn, user, key):
    services.checkout_key(conn, user, key)
    with pytest.raises(services.KeyAlreadyCheckedOutError):
        services.checkout_key(conn, user, key)


def test_checkout_possible_again_after_return(conn, user, key):
    cid = services.checkout_key(conn, user, key)
    services.return_checkout(conn, cid)
    # 返却後は再び貸出できる
    cid2 = services.checkout_key(conn, user, key)
    assert cid2 != cid


# --- ルール2: 貸出/返却の往復 --------------------------------------------


def test_checkout_return_roundtrip(conn, user, key):
    key_row = models.get_key(conn, key)
    code = key_row["code"]

    # 最初は在庫にある
    assert code in [r["code"] for r in models.list_available_keys(conn)]

    cid = services.checkout_key(conn, user, key)
    # 未返却レコードが存在する
    open_row = models.get_open_checkout_for_key(conn, key)
    assert open_row is not None
    assert open_row["checkout_id"] == cid
    # 在庫からは消える
    assert code not in [r["code"] for r in models.list_available_keys(conn)]

    services.return_checkout(conn, cid)
    # 未返却レコードは消える
    assert models.get_open_checkout_for_key(conn, key) is None
    # 在庫に再出現
    assert code in [r["code"] for r in models.list_available_keys(conn)]


# --- ルール3: 1利用者が複数の鍵を同時貸出 ---------------------------------


def test_one_user_can_hold_multiple_keys(conn, user):
    k1 = models.create_key(conn, "K-1", "鍵1")
    k2 = models.create_key(conn, "K-2", "鍵2")
    services.checkout_key(conn, user, k1)
    services.checkout_key(conn, user, k2)
    held = models.list_open_checkouts_for_user(conn, user)
    assert {r["key_code"] for r in held} == {"K-1", "K-2"}


# --- ルール4: 無効ユーザー / 廃棄鍵 --------------------------------------


def test_checkout_by_inactive_user_raises(conn, user, key):
    models.set_user_active(conn, user, False)
    with pytest.raises(services.UserInactiveError):
        services.checkout_key(conn, user, key)


def test_checkout_of_inactive_key_raises(conn, user, key):
    models.set_key_active(conn, key, False)
    with pytest.raises(services.KeyInactiveError):
        services.checkout_key(conn, user, key)


def test_checkout_unknown_user_or_key_raises(conn, user, key):
    with pytest.raises(services.NotFoundError):
        services.checkout_key(conn, 99999, key)
    with pytest.raises(services.NotFoundError):
        services.checkout_key(conn, user, 99999)


# --- return_checkout エラー系 --------------------------------------------


def test_return_unknown_checkout_raises(conn):
    with pytest.raises(services.NotFoundError):
        services.return_checkout(conn, 99999)


def test_return_already_returned_raises(conn, user, key):
    cid = services.checkout_key(conn, user, key)
    services.return_checkout(conn, cid)
    with pytest.raises(services.KeylogError):
        services.return_checkout(conn, cid)


# --- return_key_for_user 正常系 / 相手違い -------------------------------


def test_return_key_for_user_success(conn, user, key):
    services.checkout_key(conn, user, key)
    services.return_key_for_user(conn, user, key)
    assert models.get_open_checkout_for_key(conn, key) is None


def test_return_key_for_wrong_user_raises(conn, user, key):
    other = models.create_user(conn, "別人", "IDM-OTHER")
    services.checkout_key(conn, user, key)
    with pytest.raises(services.NotFoundError):
        services.return_key_for_user(conn, other, key)
    # 元の貸出は返却されていない
    assert models.get_open_checkout_for_key(conn, key) is not None


def test_return_key_for_user_when_not_checked_out_raises(conn, user, key):
    with pytest.raises(services.NotFoundError):
        services.return_key_for_user(conn, user, key)
