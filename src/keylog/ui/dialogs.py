"""共通の入力ダイアログ。CustomTkinter のモーダル Toplevel。

出現時に確実にキーボードフォーカスを入力欄へ移すため、
grab_set / lift / focus_force を親中央への配置後に行う。
"""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk


class _ModalDialog(ctk.CTkToplevel):
    """OK/キャンセルを持つモーダル。self.result に値を入れて閉じる。"""

    def __init__(self, parent, title: str) -> None:
        super().__init__(parent)
        self.parent = parent
        self.result = None
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self._first_widget: ctk.CTkBaseClass | None = None
        self.bind("<Escape>", lambda _e: self._finish(None))

    def activate(self) -> None:
        """全ウィジェット配置後に呼ぶ。中央寄せ＋フォーカス奪取。"""
        self.update_idletasks()
        self._center_over_parent()
        # 出現直後に確実にフォーカスを奪い、入力欄へ移す
        self.after(20, self._take_focus)

    def _center_over_parent(self) -> None:
        try:
            px, py = self.parent.winfo_rootx(), self.parent.winfo_rooty()
            pw, ph = self.parent.winfo_width(), self.parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

    def _take_focus(self) -> None:
        self.grab_set()
        self.lift()
        self.focus_force()
        if self._first_widget is not None:
            self._first_widget.focus_set()

    def _finish(self, value) -> None:
        self.result = value
        self.grab_release()
        self.destroy()


def _run_modal(dlg: _ModalDialog):
    dlg.activate()
    dlg.parent.wait_window(dlg)
    return dlg.result


def ask_pin(parent, title: str = "管理者 PIN") -> str | None:
    dlg = _ModalDialog(parent, title)
    ctk.CTkLabel(dlg, text="管理者 PIN を入力してください").pack(padx=24, pady=(20, 8))
    entry = ctk.CTkEntry(dlg, show="●", width=240)
    entry.pack(padx=24, pady=4)
    dlg._first_widget = entry
    entry.bind("<Return>", lambda _e: dlg._finish(entry.get()))

    row = ctk.CTkFrame(dlg, fg_color="transparent")
    row.pack(padx=24, pady=16)
    ctk.CTkButton(row, text="OK", width=90, command=lambda: dlg._finish(entry.get())).pack(side="left", padx=6)
    ctk.CTkButton(row, text="キャンセル", width=90, fg_color="gray40",
                  command=lambda: dlg._finish(None)).pack(side="left", padx=6)
    return _run_modal(dlg)


def ask_text(parent, title: str, prompt: str, initial: str = "") -> str | None:
    dlg = _ModalDialog(parent, title)
    ctk.CTkLabel(dlg, text=prompt).pack(padx=24, pady=(20, 8))
    entry = ctk.CTkEntry(dlg, width=300)
    entry.insert(0, initial)
    entry.pack(padx=24, pady=4)
    dlg._first_widget = entry
    entry.bind("<Return>", lambda _e: dlg._finish(entry.get()))

    row = ctk.CTkFrame(dlg, fg_color="transparent")
    row.pack(padx=24, pady=16)
    ctk.CTkButton(row, text="OK", width=90, command=lambda: dlg._finish(entry.get())).pack(side="left", padx=6)
    ctk.CTkButton(row, text="キャンセル", width=90, fg_color="gray40",
                  command=lambda: dlg._finish(None)).pack(side="left", padx=6)
    return _run_modal(dlg)


def ask_form(parent, title: str, fields: list[dict]) -> dict | None:
    """複数項目を1画面でまとめて入力させる。

    fields: [{"name","label","initial"?,"required"?}, ...]
    戻り値: {name: value, ...}(トリム済み)。キャンセルで None。
    必須項目が空なら赤メッセージを出して閉じない。
    """
    dlg = _ModalDialog(parent, title)
    ctk.CTkLabel(dlg, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack(
        padx=24, pady=(18, 6)
    )
    entries: dict[str, ctk.CTkEntry] = {}
    for i, f in enumerate(fields):
        label = f["label"] + ("　*" if f.get("required") else "")
        ctk.CTkLabel(dlg, text=label, anchor="w").pack(fill="x", padx=24, pady=(8, 2))
        e = ctk.CTkEntry(dlg, width=340)
        e.insert(0, f.get("initial") or "")
        e.pack(padx=24)
        entries[f["name"]] = e
        if i == 0:
            dlg._first_widget = e

    err = ctk.CTkLabel(dlg, text="", text_color="#d24b4b")
    err.pack(padx=24, pady=(6, 0))

    def submit(_e=None):
        values = {name: entries[name].get().strip() for name in entries}
        for f in fields:
            if f.get("required") and not values[f["name"]]:
                err.configure(text=f"「{f['label']}」は必須です。")
                entries[f["name"]].focus_set()
                return
        dlg._finish(values)

    for e in entries.values():
        e.bind("<Return>", submit)

    row = ctk.CTkFrame(dlg, fg_color="transparent")
    row.pack(padx=24, pady=16)
    ctk.CTkButton(row, text="保存", width=100, command=submit).pack(side="left", padx=6)
    ctk.CTkButton(row, text="キャンセル", width=100, fg_color="gray40",
                  command=lambda: dlg._finish(None)).pack(side="left", padx=6)
    return _run_modal(dlg)


def confirm(parent, message: str, title: str = "確認") -> bool:
    return messagebox.askyesno(title, message, parent=parent)


def info(parent, message: str, title: str = "お知らせ") -> None:
    messagebox.showinfo(title, message, parent=parent)


def error(parent, message: str, title: str = "エラー") -> None:
    messagebox.showerror(title, message, parent=parent)
