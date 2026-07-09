"""アプリのルート。カード読み取りループ・画面遷移・PIN ゲートを司る。

SPEC §7.1: リーダーはワーカースレッドで Queue に IDm を流すだけ。
ここ(UI スレッド)が root.after で Queue を drain し、DB 参照と画面更新を行う。
"""
from __future__ import annotations

import sqlite3
import tkinter.font as tkfont

import customtkinter as ctk

from .. import config, services
from ..config import UI_QUEUE_DRAIN_MS
from ..reader import CardReader
from . import dialogs
from .admin_view import AdminView
from .main_view import MainView


class KeylogApp(ctk.CTk):
    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self.conn = conn
        services.ensure_admin_pin(conn)

        self.title("Keylog — 鍵管理簿")
        self.geometry("760x620")
        self.minsize(640, 520)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        # テーマ読込(family を Roboto に戻す)後にフォントを上書きする
        self._apply_font_family()
        self._apply_icon()

        self._card_capture = None  # 一時的に次のカードを横取りするコールバック
        self._reader_error_shown = False

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.main_view = MainView(self.container, self)
        self.admin_view = None
        self._show(self.main_view)

        # リーダー開始 + drain ループ
        self.reader = CardReader()
        self.reader.start()
        self.after(UI_QUEUE_DRAIN_MS, self._drain_reader)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ アイコン
    def _apply_icon(self) -> None:
        """ウィンドウ(タイトルバー/タスクバー)のアイコンを設定する。

        CustomTkinter は生成から ~200ms 後に既定アイコンを再設定するため、
        直後に加えて少し遅延して再適用する。
        """
        p = config.icon_path()
        if p is None:
            return
        path = str(p)
        self._set_icon(path)
        self.after(300, lambda: self._set_icon(path))

    def _set_icon(self, path: str) -> None:
        try:
            self.iconbitmap(path)
        except Exception:
            pass

    # ------------------------------------------------------------ フォント
    def _apply_font_family(self) -> None:
        """日本語が正しく出るフォントに統一する。

        候補(config.UI_FONT_CANDIDATES)の先頭から、導入済みの最初のものを採用。
        配布先に Noto Sans JP が無くても Windows 標準の日本語フォントで表示できる。
        """
        available = set(tkfont.families())
        family = next((f for f in config.UI_FONT_CANDIDATES if f in available), None)
        if family is None:
            return
        # CTk ウィジェットの既定 family
        ctk.ThemeManager.theme["CTkFont"]["family"] = family
        # tk/ttk(messagebox・tkcalendar)用の名前付きフォント
        for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(fname).configure(family=family)
            except Exception:
                pass

    # ------------------------------------------------------------ 画面遷移
    def _show(self, view) -> None:
        for child in self.container.winfo_children():
            child.pack_forget()
        view.pack(fill="both", expand=True)
        self.active_view = view

    def open_admin(self) -> None:
        if not self.require_pin():
            return
        self.admin_view = AdminView(self.container, self)
        self._show(self.admin_view)

    def open_main(self) -> None:
        self.main_view.reset()
        self._show(self.main_view)
        if self.admin_view is not None:
            self.admin_view.destroy()
            self.admin_view = None

    # ------------------------------------------------------------ PIN
    def require_pin(self) -> bool:
        pin = dialogs.ask_pin(self)
        if pin is None:
            return False
        if services.verify_admin_pin(self.conn, pin):
            return True
        dialogs.error(self, "PIN が違います。")
        return False

    # ------------------------------------------------------------ カード横取り
    def capture_next_card(self, callback) -> None:
        """次に検知した1枚の IDm を、通常処理でなく callback に渡す。"""
        self._card_capture = callback

    # ------------------------------------------------------------ リーダー drain
    def _drain_reader(self) -> None:
        handled_card = False
        for kind, value in self.reader.poll_events():
            if kind == "error":
                if not self._reader_error_shown:
                    self._reader_error_shown = True
                    dialogs.error(self, f"カードリーダー: {value}")
                continue
            # kind == "card": 1回のドレインで扱うカードは1枚だけ。
            # 残りは重複タップとみなして捨てる(ポップの多重表示を防ぐ)。
            if handled_card:
                continue
            handled_card = True
            self._dispatch_card(value)
        if handled_card:
            # モーダル処理中に溜まった重複イベントを破棄
            self.reader.poll_events()
        self.after(UI_QUEUE_DRAIN_MS, self._drain_reader)

    def _dispatch_card(self, idm: str) -> None:
        if self._card_capture is not None:
            cb, self._card_capture = self._card_capture, None
            handler = cb
        elif self.active_view is self.main_view:
            handler = self.main_view.on_card
        else:
            return  # 管理画面表示中でキャプチャ待ちでないカードは無視
        try:
            handler(idm)
        except Exception as e:  # noqa: BLE001
            dialogs.error(self, f"処理エラー: {e}")

    # ------------------------------------------------------------ 終了
    def _on_close(self) -> None:
        try:
            self.reader.stop()
        finally:
            self.destroy()


def run_app(conn: sqlite3.Connection) -> None:
    app = KeylogApp(conn)
    app.mainloop()
