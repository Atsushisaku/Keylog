"""貸出/返却のメイン画面(PIN 不要)。カードをかざして操作する。"""
from __future__ import annotations

import customtkinter as ctk

from .. import models, services
from . import dialogs


class MainView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self.conn = app.conn
        self.mode = "lend"  # "lend" or "return"
        self.current_user = None  # sqlite3.Row | None

        self._build()
        self.refresh()

    # ------------------------------------------------------------ UI
    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 6))

        # fg_color を背後のフレーム色に合わせ、トラック枠(下端の線)を溶かす
        self.mode_switch = ctk.CTkSegmentedButton(
            header, values=["貸出", "返却"], command=self._on_mode_change,
            fg_color=self.cget("fg_color"),
        )
        self.mode_switch.set("貸出")
        self.mode_switch.pack(side="left")

        ctk.CTkButton(
            header, text="管理メニュー", width=120, fg_color="gray40",
            command=self.app.open_admin,
        ).pack(side="right")

        self.status = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.status.pack(padx=20, pady=(6, 2))

        self.hint = ctk.CTkLabel(self, text="", text_color="gray60")
        self.hint.pack(padx=20, pady=(0, 8))

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(4, 8))

        self.toast = ctk.CTkLabel(self, text="", text_color="#2e7d32")
        self.toast.pack(padx=20, pady=(0, 12))

    # ------------------------------------------------------------ 状態遷移
    def _on_mode_change(self, value: str) -> None:
        self.mode = "lend" if value == "貸出" else "return"
        self.current_user = None
        self.refresh()

    def reset(self) -> None:
        self.current_user = None
        self.refresh()

    def refresh(self) -> None:
        for w in self.list_frame.winfo_children():
            w.destroy()

        if self.current_user is None:
            action = "貸出" if self.mode == "lend" else "返却"
            self.status.configure(text=f"{action}モード — カードをかざしてください")
            self.hint.configure(text="社員証などの IC カードをリーダーに載せてください")
            return

        name = self.current_user["name"]
        if self.mode == "lend":
            self.status.configure(text=f"{name} さん — 貸す鍵を選んでください")
            self._show_lend_list()
        else:
            self.status.configure(text=f"{name} さん — 返す鍵を選んでください")
            self._show_return_list()

    def _show_lend_list(self) -> None:
        keys = models.list_available_keys(self.conn)
        self.hint.configure(text=f"在庫中の鍵: {len(keys)} 本")
        if not keys:
            ctk.CTkLabel(self.list_frame, text="貸出可能な鍵がありません").pack(pady=20)
            return
        for k in keys:
            self._key_row(k["code"], k["name"], lambda kid=k["key_id"]: self._do_lend(kid))

    def _show_return_list(self) -> None:
        rows = models.list_open_checkouts_for_user(self.conn, self.current_user["user_id"])
        self.hint.configure(text=f"借用中の鍵: {len(rows)} 本")
        if not rows:
            ctk.CTkLabel(self.list_frame, text="借用中の鍵はありません").pack(pady=20)
            return
        for r in rows:
            self._key_row(
                r["key_code"], r["key_name"],
                lambda cid=r["checkout_id"]: self._do_return(cid),
                subtitle=f"貸出: {r['checked_out_at']}",
            )

    def _key_row(self, code: str, name: str, command, subtitle: str = "") -> None:
        text = f"{code}　{name}"
        if subtitle:
            text += f"\n{subtitle}"
        # 青塗りをやめ、枠線のみ・ホバーで淡く反応する中立的な行にする
        ctk.CTkButton(
            self.list_frame, text=text, anchor="w", height=44, command=command,
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray85", "gray25"),
            border_width=1, border_color=("gray70", "gray35"),
        ).pack(fill="x", padx=4, pady=3)

    # ------------------------------------------------------------ カード受信
    def on_card(self, idm: str) -> None:
        """app から呼ばれる(UI スレッド)。かざされた IDm を処理する。"""
        res = services.resolve_card(self.conn, idm)
        if res.status is services.CardStatus.OK:
            self.current_user = res.user
            self._clear_toast()
            self.refresh()
        elif res.status is services.CardStatus.INACTIVE:
            dialogs.error(self, "無効な利用者のカードです。")
        else:  # UNKNOWN
            self._handle_unknown_card(idm)

    def _handle_unknown_card(self, idm: str) -> None:
        if self.mode == "return":
            dialogs.info(self, "未登録カードです。返却する鍵がありません。")
            return
        # 貸出モードのみ: PIN → 名前 → 登録(登録は常に PIN 必須)
        if not self.app.require_pin():
            return
        name = dialogs.ask_text(self, "利用者登録", "未登録カードです。利用者名を入力してください")
        if not name:
            return
        try:
            uid = services.register_user_with_card(self.conn, name, idm)
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            return
        self.current_user = models.get_user(self.conn, uid)
        self._toast(f"{name} さんを登録しました")
        self.refresh()

    # ------------------------------------------------------------ 貸出/返却実行
    def _do_lend(self, key_id: int) -> None:
        key = models.get_key(self.conn, key_id)
        if not dialogs.confirm(self, f"{key['code']} {key['name']} を貸し出します。よろしいですか？"):
            return
        try:
            services.checkout_key(self.conn, self.current_user["user_id"], key_id)
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            self.refresh()
            return
        msg = f"{self.current_user['name']} さんが {key['name']} を貸出しました"
        self.reset()
        self._toast(msg)

    def _do_return(self, checkout_id: int) -> None:
        try:
            services.return_checkout(self.conn, checkout_id)
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            self.refresh()
            return
        name = self.current_user["name"]
        self.reset()
        self._toast(f"{name} さんが鍵を返却しました")

    # ------------------------------------------------------------ トースト
    def _toast(self, message: str) -> None:
        self.toast.configure(text=message)
        self.after(4000, self._clear_toast)

    def _clear_toast(self) -> None:
        self.toast.configure(text="")
