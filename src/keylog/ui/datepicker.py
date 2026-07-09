"""日付入力ウィジェット。

CTk スタイルの入力欄 ＋ 📅 ボタン。ボタンでカレンダーをポップアップ表示し、
日付を選ぶと欄に反映する。欄への直接入力(YYYY-MM-DD)も可能。
"""
from __future__ import annotations

from datetime import date, datetime

import customtkinter as ctk
from tkcalendar import Calendar

_FONT_SIZE = 13


class DatePicker(ctk.CTkFrame):
    def __init__(self, master, initial: date | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.entry = ctk.CTkEntry(self, width=120, font=ctk.CTkFont(size=_FONT_SIZE))
        self.entry.pack(side="left")
        self.button = ctk.CTkButton(
            self, text="📅", width=40, font=ctk.CTkFont(size=16),
            command=self._open_calendar,
        )
        self.button.pack(side="left", padx=(6, 0))
        self._popup: ctk.CTkToplevel | None = None
        if initial is not None:
            self.set_date(initial)

    # ------------------------------------------------------------ 値
    def set_date(self, d: date) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, d.strftime("%Y-%m-%d"))

    def get_date(self) -> date:
        """欄の文字列を date に変換(不正なら ValueError)。"""
        return datetime.strptime(self.entry.get().strip(), "%Y-%m-%d").date()

    # ------------------------------------------------------------ カレンダー
    def _open_calendar(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.lift()
            return
        try:
            cur = self.get_date()
        except ValueError:
            cur = date.today()

        top = ctk.CTkToplevel(self)
        self._popup = top
        top.title("日付を選択")
        top.resizable(False, False)
        top.transient(self.winfo_toplevel())

        dark = ctk.get_appearance_mode() == "Dark"
        if dark:
            colors = dict(
                background="#2b3540", foreground="white",
                headersbackground="#222a33", headersforeground="#dfe6ee",
                normalbackground="#2b3540", normalforeground="white",
                weekendbackground="#2b3540", weekendforeground="#9fb3c8",
                othermonthbackground="#232a31", othermonthforeground="#6b7783",
                othermonthwebackground="#232a31", othermonthweforeground="#6b7783",
                bordercolor="#222a33",
            )
        else:
            colors = dict(
                background="#f5f7fa", foreground="#1a1a1a",
                headersbackground="#e4e9f0", headersforeground="#1a1a1a",
                normalbackground="white", normalforeground="#1a1a1a",
                weekendbackground="white", weekendforeground="#3355aa",
                othermonthbackground="#eef1f5", othermonthforeground="#9aa5b1",
                othermonthwebackground="#eef1f5", othermonthweforeground="#9aa5b1",
                bordercolor="#d0d7e2",
            )

        cal = Calendar(
            top, selectmode="day", date_pattern="yyyy-mm-dd",
            year=cur.year, month=cur.month, day=cur.day,
            locale="ja_JP", firstweekday="sunday", showweeknumbers=False,
            showothermonthdays=True,
            selectbackground="#1f6aa5", selectforeground="white",
            font="TkDefaultFont 12", headersfont="TkDefaultFont 10 bold",
            **colors,
        )
        cal.pack(padx=12, pady=12)

        def choose() -> None:
            self.set_date(cal.selection_get())
            top.destroy()
            self._popup = None

        cal.bind("<<CalendarSelected>>", lambda _e: None)
        cal.bind("<Double-1>", lambda _e: choose())

        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(pady=(0, 12))
        ctk.CTkButton(row, text="選択", width=90, command=choose).pack(side="left", padx=6)
        ctk.CTkButton(row, text="キャンセル", width=90, fg_color="gray40",
                      command=lambda: (top.destroy(), setattr(self, "_popup", None))).pack(side="left", padx=6)

        # ボタン直下に配置してフォーカスを奪う
        top.update_idletasks()
        x = self.button.winfo_rootx()
        y = self.button.winfo_rooty() + self.button.winfo_height() + 4
        top.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        top.after(20, lambda: (top.grab_set(), top.lift(), top.focus_force()))
