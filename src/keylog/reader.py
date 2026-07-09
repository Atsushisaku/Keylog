"""RC-S300 (FeliCa) カード読み取り。

SPEC §7.1 に従い、ワーカースレッドは検知した IDm を Queue に put するだけ。
UI/DB には一切触れない。UI スレッドが root.after() で Queue を drain する。

pyscard(PC/SC) 経由。IDm は APDU `FF CA 00 00 00` で取得する。
"""
from __future__ import annotations

import queue
import threading
import time

from .config import READER_POLL_INTERVAL

try:
    from smartcard.System import readers as _list_readers
    _SMARTCARD_AVAILABLE = True
except Exception:  # pragma: no cover - pyscard 未導入環境
    _SMARTCARD_AVAILABLE = False


def _to_hex(data: list[int]) -> str:
    return "".join(f"{b:02X}" for b in data)


def list_reader_names() -> list[str]:
    if not _SMARTCARD_AVAILABLE:
        return []
    try:
        return [str(r) for r in _list_readers()]
    except Exception:
        return []


class CardReader:
    """別スレッドでリーダーをポーリングし、IDm を Queue に流す。

    使い方(UI 側):
        reader = CardReader()
        reader.start()
        # 定期的に reader.poll_events() を root.after で呼ぶ
        for evt in reader.poll_events():
            ...
        reader.stop()
    """

    def __init__(self, poll_interval: float = READER_POLL_INTERVAL) -> None:
        self._poll_interval = poll_interval
        self._events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # 同一カードの多重検知を抑止(離すまで再発火しない)
        self._last_idm: str | None = None

    # ---- ライフサイクル ----

    def start(self) -> None:
        if not _SMARTCARD_AVAILABLE:
            self._events.put(("error", "pyscard が利用できません。"))
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    # ---- UI 側から呼ぶ ----

    def poll_events(self) -> list[tuple[str, str]]:
        """溜まったイベントを取り出す。UI スレッドから呼ぶこと。

        戻り値は (種別, 値) のリスト。種別: 'card'=IDm検知 / 'error'=メッセージ。
        """
        out: list[tuple[str, str]] = []
        while True:
            try:
                out.append(self._events.get_nowait())
            except queue.Empty:
                break
        return out

    # ---- ワーカースレッド本体 ----

    # 何回連続で「不在」を観測したら同じカードの再発火を許すか。
    # 1回の読み取り失敗(排他接続の一時 None)で再発火して二重投入するのを防ぐ。
    _ABSENCE_TO_REARM = 3

    def _run(self) -> None:
        absent = 0
        while not self._stop.is_set():
            try:
                rs = _list_readers()
                idm = self._read_idm(rs[0]) if rs else None
                if idm is None:
                    # 一時的な失敗と本当の離席を区別するため連続不在をカウント
                    absent += 1
                    if absent >= self._ABSENCE_TO_REARM:
                        self._last_idm = None
                else:
                    absent = 0
                    if idm != self._last_idm:
                        self._last_idm = idm
                        self._events.put(("card", idm))
            except Exception:
                absent += 1
                if absent >= self._ABSENCE_TO_REARM:
                    self._last_idm = None
            time.sleep(self._poll_interval)

    @staticmethod
    def _read_idm(reader) -> str | None:
        """カードが載っていれば IDm(hex) を返す。無ければ None。"""
        try:
            conn = reader.createConnection()
            conn.connect()
        except Exception:
            return None
        try:
            data, sw1, sw2 = conn.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
            if (sw1, sw2) == (0x90, 0x00) and data:
                return _to_hex(data)
            return None
        except Exception:
            return None
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass
