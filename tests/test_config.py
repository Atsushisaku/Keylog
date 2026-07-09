"""config モジュールの軽い健全性チェック。"""
from __future__ import annotations

import re

from keylog import config


def test_now_iso_format():
    s = config.now_iso()
    # "YYYY-MM-DD HH:MM:SS" 秒精度・マイクロ秒なし
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", s), s


def test_initial_admin_pin_value():
    assert config.INITIAL_ADMIN_PIN == "pass"
