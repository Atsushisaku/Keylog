"""共通 fixture。各テストは独立したインメモリ DB を使う。"""
from __future__ import annotations

import pytest

from keylog import db, models


@pytest.fixture
def conn():
    c = db.initialize(":memory:")
    yield c
    c.close()


@pytest.fixture
def user(conn):
    """有効な利用者を1人作って user_id を返す。"""
    return models.create_user(conn, "山田太郎", idm="IDM-USER-1")


@pytest.fixture
def key(conn):
    """有効な鍵を1つ作って key_id を返す。"""
    return models.create_key(conn, code="K-001", name="正面玄関")
