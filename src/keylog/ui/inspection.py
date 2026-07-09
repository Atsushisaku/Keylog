"""点検の実施ダイアログ。

要件:
 1. すべて返却されているかを明示(未返却があれば一覧・結果に反映)
 2. 現物があるかを点検者がチェックリストで確認
 3. 点検者名と日時を記録
"""
from __future__ import annotations

import customtkinter as ctk

from .. import services
from . import dialogs


class InspectionDialog(ctk.CTkToplevel):
    def __init__(self, parent, conn, on_done) -> None:
        super().__init__(parent)
        self.parent = parent
        self.conn = conn
        self.on_done = on_done

        self.items = services.build_inspection_checklist(conn)
        self.out_items = [i for i in self.items if not i["in_stock"]]
        self.stock_items = [i for i in self.items if i["in_stock"]]
        self.checks: dict[int, ctk.CTkCheckBox] = {}

        self.title("点検の実施")
        self.geometry("580x680")
        self.minsize(480, 560)
        self.transient(parent)
        self.bind("<Escape>", lambda _e: self.destroy())

        self._build()
        self.after(20, self._focus)

    # ------------------------------------------------------------ 構築
    def _build(self) -> None:
        ctk.CTkLabel(
            self, text="点検の実施", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(padx=20, pady=(16, 8))

        # 1) 点検者名
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(row, text="点検者名").pack(side="left")
        self.inspector = ctk.CTkEntry(row, width=240, placeholder_text="例: 山田太郎")
        self.inspector.pack(side="left", padx=10)

        # 2) 返却状況サマリ
        if self.out_items:
            box = ctk.CTkFrame(self, fg_color=("#f6e3c5", "#4a3a1e"))
            box.pack(fill="x", padx=20, pady=(4, 8))
            ctk.CTkLabel(
                box, text=f"⚠ 未返却が {len(self.out_items)} 件あります(現物確認できません)",
                text_color=("#8a5a00", "#f0c674"), anchor="w",
            ).pack(fill="x", padx=10, pady=(6, 2))
            for it in self.out_items:
                ctk.CTkLabel(
                    box, text=f"　・{it['code']} {it['name']}（{it['holder']}）",
                    anchor="w", text_color=("#8a5a00", "#f0c674"),
                ).pack(fill="x", padx=10)
            ctk.CTkLabel(box, text="").pack(pady=1)
        else:
            ctk.CTkLabel(
                self, text="✓ すべての鍵が返却済みです", text_color=("#2e7d32", "#7CD88B"),
            ).pack(padx=20, pady=(4, 8))

        # 3) 現物チェックリスト
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20)
        ctk.CTkLabel(head, text="現物確認(在庫中の鍵)", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(head, text="すべて確認済み", width=110, height=26,
                      fg_color="gray40", command=self._check_all).pack(side="right")

        self.list_frame = ctk.CTkScrollableFrame(self, height=280)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(4, 8))
        if not self.stock_items:
            ctk.CTkLabel(self.list_frame, text="在庫中の鍵がありません").pack(pady=16)
        for it in self.stock_items:
            cb = ctk.CTkCheckBox(self.list_frame, text=f"{it['code']}　{it['name']}")
            cb.pack(fill="x", padx=6, pady=4, anchor="w")
            self.checks[it["key_id"]] = cb

        # 所見
        ctk.CTkLabel(self, text="所見(任意)", anchor="w").pack(fill="x", padx=20)
        self.note = ctk.CTkEntry(self, placeholder_text="特記事項があれば入力")
        self.note.pack(fill="x", padx=20, pady=(2, 8))

        # ボタン
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=(0, 14))
        ctk.CTkButton(btns, text="点検を記録", width=130, command=self._submit).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="キャンセル", width=110, fg_color="gray40",
                      command=self.destroy).pack(side="left", padx=6)

    def _focus(self) -> None:
        self.update_idletasks()
        try:
            px, py = self.parent.winfo_rootx(), self.parent.winfo_rooty()
            self.geometry(f"+{px + 60}+{py + 40}")
        except Exception:
            pass
        self.grab_set()
        self.lift()
        self.focus_force()
        self.inspector.focus_set()

    # ------------------------------------------------------------ 動作
    def _check_all(self) -> None:
        for cb in self.checks.values():
            cb.select()

    def _submit(self) -> None:
        confirmed = [kid for kid, cb in self.checks.items() if cb.get()]
        try:
            services.record_inspection(
                self.conn, self.inspector.get(), confirmed, self.note.get() or None
            )
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            return

        unchecked = len(self.stock_items) - len(confirmed)
        msg = "点検を記録しました。"
        if self.out_items or unchecked:
            parts = []
            if self.out_items:
                parts.append(f"未返却 {len(self.out_items)} 件")
            if unchecked:
                parts.append(f"未確認 {unchecked} 件")
            msg += "（問題あり: " + " / ".join(parts) + "）"
        self.grab_release()
        self.destroy()
        if callable(self.on_done):
            self.on_done()
        dialogs.info(self.parent, msg, title="点検完了")
