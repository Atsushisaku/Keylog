"""業務ロジック層。

DB アクセス(models)の上に、SPEC の業務ルールを実装する:
- 二重貸出防止(DB 制約違反を業務例外に翻訳)
- 有効/無効(退職者・廃棄鍵)の扱い
- 未登録/無効カードの判定
- 管理者 PIN(ソルト付き PBKDF2)
- 点検記録・バックアップ
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from . import config, models

# ---------------------------------------------------------------- 例外


class KeylogError(Exception):
    """業務エラーの基底。message はユーザー表示可能な日本語。"""


class UserInactiveError(KeylogError):
    pass


class KeyInactiveError(KeylogError):
    pass


class KeyAlreadyCheckedOutError(KeylogError):
    pass


class DuplicateIdmError(KeylogError):
    pass


class HasOpenCheckoutError(KeylogError):
    pass


class NotFoundError(KeylogError):
    pass


# ---------------------------------------------------------------- カード判定


class CardStatus(str, Enum):
    UNKNOWN = "unknown"    # 未登録カード
    INACTIVE = "inactive"  # 退職者等(active=0)のカード
    OK = "ok"              # 有効な利用者


@dataclass
class CardResolution:
    status: CardStatus
    user: sqlite3.Row | None = None


def resolve_card(conn: sqlite3.Connection, idm: str) -> CardResolution:
    """かざされた IDm を利用者に解決する。"""
    user = models.get_user_by_idm(conn, idm)
    if user is None:
        return CardResolution(CardStatus.UNKNOWN)
    if not user["active"]:
        return CardResolution(CardStatus.INACTIVE, user)
    return CardResolution(CardStatus.OK, user)


# ---------------------------------------------------------------- 貸出/返却


def checkout_key(conn: sqlite3.Connection, user_id: int, key_id: int) -> int:
    """鍵を貸し出す。二重貸出は DB 制約が最後の砦。返り値は checkout_id。"""
    user = models.get_user(conn, user_id)
    if user is None:
        raise NotFoundError("利用者が見つかりません。")
    if not user["active"]:
        raise UserInactiveError("無効な利用者です。")

    key = models.get_key(conn, key_id)
    if key is None:
        raise NotFoundError("鍵が見つかりません。")
    if not key["active"]:
        raise KeyInactiveError("廃棄済みの鍵です。")

    try:
        return models.create_checkout(conn, key_id, user_id)
    except sqlite3.IntegrityError as exc:
        # ux_open_checkout 違反 = 既に貸出中
        raise KeyAlreadyCheckedOutError("その鍵は既に貸出中です。") from exc


def return_checkout(conn: sqlite3.Connection, checkout_id: int) -> None:
    """貸出記録を返却済みにする。"""
    row = models.get_checkout(conn, checkout_id)
    if row is None:
        raise NotFoundError("貸出記録が見つかりません。")
    if row["returned_at"] is not None:
        raise KeylogError("その記録は既に返却済みです。")
    models.close_checkout(conn, checkout_id)


def return_key_for_user(conn: sqlite3.Connection, user_id: int, key_id: int) -> None:
    """利用者+鍵の組から未返却記録を特定して返却する(返却画面用)。"""
    row = models.get_open_checkout_for_key(conn, key_id)
    if row is None or row["user_id"] != user_id:
        raise NotFoundError("この利用者がその鍵を借用中の記録がありません。")
    models.close_checkout(conn, row["checkout_id"])


# ---------------------------------------------------------------- 利用者登録


def register_user_with_card(conn: sqlite3.Connection, name: str, idm: str) -> int:
    """新規利用者を作りカードを紐付ける(その場登録・管理画面共通)。"""
    name = (name or "").strip()
    if not name:
        raise KeylogError("名前を入力してください。")
    if models.get_user_by_idm(conn, idm) is not None:
        raise DuplicateIdmError("このカードは既に別の利用者に登録されています。")
    try:
        return models.create_user(conn, name, idm)
    except sqlite3.IntegrityError as exc:
        raise DuplicateIdmError("このカードは既に登録されています。") from exc


def assign_card_to_user(conn: sqlite3.Connection, user_id: int, idm: str) -> None:
    """既存利用者にカードを再登録する(idm 更新)。"""
    existing = models.get_user_by_idm(conn, idm)
    if existing is not None and existing["user_id"] != user_id:
        raise DuplicateIdmError("このカードは既に別の利用者に登録されています。")
    try:
        models.set_user_idm(conn, user_id, idm)
    except sqlite3.IntegrityError as exc:
        raise DuplicateIdmError("このカードは既に登録されています。") from exc


# ---------------------------------------------------------------- 無効化


def deactivate_user(conn: sqlite3.Connection, user_id: int) -> None:
    """利用者を無効化。貸出中があれば拒否。無効化時に idm を解放する。"""
    if models.list_open_checkouts_for_user(conn, user_id):
        raise HasOpenCheckoutError("借用中の鍵があるため無効化できません。先に返却してください。")
    models.set_user_idm(conn, user_id, None)
    models.set_user_active(conn, user_id, False)


def discard_key(conn: sqlite3.Connection, key_id: int) -> None:
    """鍵を廃棄(無効化)。貸出中なら拒否。"""
    if models.get_open_checkout_for_key(conn, key_id) is not None:
        raise HasOpenCheckoutError("貸出中の鍵は廃棄できません。先に返却してください。")
    models.set_key_active(conn, key_id, False)


# ---------------------------------------------------------------- 管理者 PIN


def _hash_pin(pin: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), salt, config.PIN_PBKDF2_ITERATIONS
    )
    return dk.hex()


def ensure_admin_pin(conn: sqlite3.Connection) -> None:
    """PIN 未設定なら初期 PIN を投入する(初回起動)。"""
    if models.get_setting(conn, "admin_pin_hash") is None:
        set_admin_pin(conn, config.INITIAL_ADMIN_PIN)


def set_admin_pin(conn: sqlite3.Connection, pin: str) -> None:
    if not pin:
        raise KeylogError("PIN を入力してください。")
    salt = os.urandom(16)
    models.set_setting(conn, "admin_pin_salt", salt.hex())
    models.set_setting(conn, "admin_pin_hash", _hash_pin(pin, salt))


def verify_admin_pin(conn: sqlite3.Connection, pin: str) -> bool:
    salt_hex = models.get_setting(conn, "admin_pin_salt")
    stored = models.get_setting(conn, "admin_pin_hash")
    if not salt_hex or not stored:
        return False
    calc = _hash_pin(pin, bytes.fromhex(salt_hex))
    # タイミング攻撃対策(ローカル用途では過剰だが安価)
    return hmac.compare_digest(calc, stored)


# ---------------------------------------------------------------- 点検


def record_inspection(
    conn: sqlite3.Connection, inspector: str, result: str, note: str | None = None
) -> int:
    """点検を記録する。点検時点の貸出中一覧をスナップショット保存する。"""
    inspector = (inspector or "").strip()
    if not inspector:
        raise KeylogError("点検者名を入力してください。")
    if result not in ("ok", "issue"):
        raise KeylogError("点検結果が不正です。")
    open_rows = models.list_open_checkouts(conn)
    snapshot = json.dumps(
        [
            {
                "key_code": r["key_code"],
                "key_name": r["key_name"],
                "user_name": r["user_name"],
                "checked_out_at": r["checked_out_at"],
            }
            for r in open_rows
        ],
        ensure_ascii=False,
    )
    return models.create_inspection(conn, inspector, result, note, snapshot)


# ---------------------------------------------------------------- バックアップ


def backup_db(conn: sqlite3.Connection, dest: Path | str) -> Path:
    """SQLite オンラインバックアップ API で整合性のあるコピーを作る。"""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(dest)) as bck:
        conn.backup(bck)
    return dest
