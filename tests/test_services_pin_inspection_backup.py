"""管理者 PIN・点検記録・バックアップの業務ルール。"""
from __future__ import annotations

import json

import pytest

from keylog import config, db, models, services


# --- ルール8: PIN --------------------------------------------------------


def test_ensure_admin_pin_sets_initial(conn):
    services.ensure_admin_pin(conn)
    assert services.verify_admin_pin(conn, config.INITIAL_ADMIN_PIN) is True
    assert services.verify_admin_pin(conn, "wrong") is False


def test_ensure_admin_pin_is_idempotent(conn):
    services.ensure_admin_pin(conn)
    first_hash = models.get_setting(conn, "admin_pin_hash")
    services.ensure_admin_pin(conn)  # 2回目は上書きしない
    assert models.get_setting(conn, "admin_pin_hash") == first_hash


def test_set_admin_pin_changes_verification(conn):
    services.ensure_admin_pin(conn)
    services.set_admin_pin(conn, "new-pin-123")
    assert services.verify_admin_pin(conn, "new-pin-123") is True
    assert services.verify_admin_pin(conn, config.INITIAL_ADMIN_PIN) is False


def test_pin_is_not_stored_in_plaintext(conn):
    services.set_admin_pin(conn, "secret-pin")
    stored = models.get_setting(conn, "admin_pin_hash")
    assert stored is not None
    assert stored != "secret-pin"  # 生 PIN と一致しない(ハッシュ化されている)
    # ソルトも保存されている
    assert models.get_setting(conn, "admin_pin_salt") is not None


def test_verify_without_pin_set_returns_false(conn):
    assert services.verify_admin_pin(conn, "anything") is False


def test_set_empty_pin_raises(conn):
    with pytest.raises(services.KeylogError):
        services.set_admin_pin(conn, "")


# --- ルール9: 点検記録(チェックリスト式) --------------------------------


def test_checklist_reflects_stock_and_out(conn):
    uid = models.create_user(conn, "借主", "IDM-I")
    k1 = models.create_key(conn, "K-1", "在庫鍵")
    k2 = models.create_key(conn, "K-2", "貸出鍵")
    services.checkout_key(conn, uid, k2)

    items = services.build_inspection_checklist(conn)
    by_id = {i["key_id"]: i for i in items}
    assert by_id[k1]["in_stock"] is True and by_id[k1]["holder"] is None
    assert by_id[k2]["in_stock"] is False and by_id[k2]["holder"] == "借主"


def test_inspection_ok_when_all_returned_and_confirmed(conn):
    k1 = models.create_key(conn, "K-1", "鍵1")
    k2 = models.create_key(conn, "K-2", "鍵2")

    insp_id = services.record_inspection(conn, "点検者A", [k1, k2], note="定例")
    row = models.list_inspections(conn)[0]
    assert row["inspection_id"] == insp_id
    assert row["inspector"] == "点検者A"
    assert row["result"] == "ok"
    assert row["all_returned"] == 1
    cl = json.loads(row["checklist"])
    assert all(i["confirmed"] for i in cl)


def test_inspection_issue_when_stock_key_unconfirmed(conn):
    k1 = models.create_key(conn, "K-1", "鍵1")
    models.create_key(conn, "K-2", "鍵2")  # 未確認のまま

    services.record_inspection(conn, "点検者", [k1])
    row = models.list_inspections(conn)[0]
    assert row["result"] == "issue"
    assert row["all_returned"] == 1


def test_inspection_issue_when_key_out(conn):
    uid = models.create_user(conn, "借主", "IDM-I")
    k1 = models.create_key(conn, "K-1", "在庫鍵")
    k2 = models.create_key(conn, "K-2", "貸出鍵")
    services.checkout_key(conn, uid, k2)

    # 在庫鍵は確認、貸出鍵は現物なしなので確認不可
    services.record_inspection(conn, "点検者", [k1])
    row = models.list_inspections(conn)[0]
    assert row["result"] == "issue"
    assert row["all_returned"] == 0
    cl = {i["key_id"]: i for i in json.loads(row["checklist"])}
    assert cl[k1]["confirmed"] is True
    assert cl[k2]["confirmed"] is False and cl[k2]["in_stock"] is False


def test_inspection_out_key_cannot_be_confirmed(conn):
    """貸出中の鍵IDを confirmed に渡しても確認済みにはならない。"""
    uid = models.create_user(conn, "借主", "IDM-I")
    k2 = models.create_key(conn, "K-2", "貸出鍵")
    services.checkout_key(conn, uid, k2)

    services.record_inspection(conn, "点検者", [k2])  # 不正に渡す
    row = models.list_inspections(conn)[0]
    cl = {i["key_id"]: i for i in json.loads(row["checklist"])}
    assert cl[k2]["confirmed"] is False


def test_record_inspection_blank_inspector_raises(conn):
    with pytest.raises(services.KeylogError):
        services.record_inspection(conn, "  ", [])


# --- ルール10: バックアップ backup_db ------------------------------------


def test_backup_db_produces_readable_copy(conn, tmp_path):
    uid = models.create_user(conn, "バックアップ対象", "IDM-BK")
    kid = models.create_key(conn, "K-BK", "鍵BK")
    services.checkout_key(conn, uid, kid)

    dest = tmp_path / "sub" / "backup.db"
    result = services.backup_db(conn, dest)
    assert result == dest
    assert dest.exists()

    # バックアップを開いてデータが読めること
    restored = db.connect(dest)
    try:
        u = models.get_user_by_idm(restored, "IDM-BK")
        assert u is not None and u["name"] == "バックアップ対象"
        assert models.get_key_by_code(restored, "K-BK") is not None
        assert models.get_open_checkout_for_key(restored, kid) is not None
    finally:
        restored.close()
