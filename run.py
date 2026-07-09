"""Keylog 起動エントリポイント。

    uv run python run.py

- src/ を import パスに追加
- 二重起動ガード(Windows named mutex): RC-S300 は排他接続のため多重起動を防ぐ
- DB 初期化 → GUI 起動
"""
from __future__ import annotations

import sys
from pathlib import Path

# src レイアウトのため import パスを通す
SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))


def acquire_single_instance() -> bool:
    """既に起動していれば False。二重起動を Windows named mutex で検出する。"""
    if sys.platform != "win32":
        return True
    import ctypes
    from ctypes import wintypes

    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, wintypes.BOOL(True), "Global\\KeylogSingleInstance")
    if not handle:
        return True  # mutex 作成失敗時はガードを諦めて起動を許す
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    # handle はプロセス終了まで保持する必要があるため参照を残す
    acquire_single_instance._handle = handle  # type: ignore[attr-defined]
    return True


def main() -> int:
    if not acquire_single_instance():
        try:
            import tkinter.messagebox as mb
            mb.showwarning("Keylog", "Keylog は既に起動しています。")
        except Exception:
            print("Keylog は既に起動しています。")
        return 1

    from keylog import db
    from keylog.ui.app import run_app

    conn = db.initialize()
    try:
        run_app(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
