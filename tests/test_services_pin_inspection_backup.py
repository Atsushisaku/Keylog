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


# --- ルール9: 点検記録 record_inspection ---------------------------------


def test_record_inspection_snapshots_open_checkouts(conn):
    uid = models.create_user(conn, "借主", "IDM-I")
    kid = models.create_key(conn, "K-INSP", "点検対象鍵")
    services.checkout_key(conn, uid, kid)

    insp_id = services.record_inspection(conn, "点検者A", "ok", note="定例")

    rows = models.list_inspections(conn)
    assert len(rows) == 1
    row = rows[0]
    assert row["inspection_id"] == insp_id
    assert row["inspector"] == "点検者A"
    assert row["result"] == "ok"

    snapshot = json.loads(row["open_snapshot"])
    assert len(snapshot) == 1
    assert snapshot[0]["key_code"] == "K-INSP"
    assert snapshot[0]["user_name"] == "借主"


def test_record_inspection_invalid_result_raises(conn):
    with pytest.raises(services.KeylogError):
        services.record_inspection(conn, "点検者", "bogus")


def test_record_inspection_blank_inspector_raises(conn):
    with pytest.raises(services.KeylogError):
        services.record_inspection(conn, "  ", "ok")


def test_record_inspection_empty_snapshot(conn):
    services.record_inspection(conn, "点検者", "issue", note="貸出なし")
    row = models.list_inspections(conn)[0]
    assert json.loads(row["open_snapshot"]) == []


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
