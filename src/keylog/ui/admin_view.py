"""管理メニュー(PIN 通過後)。利用者・鍵・貸出状況・点検・レポート・設定。"""
from __future__ import annotations

import calendar
import os
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from .. import config, models, reports, services
from . import dialogs
from .datepicker import DatePicker


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _month_ago(d: date) -> date:
    """d の1ヶ月前(月末日を超える場合はその月の末日に丸める)。"""
    m = d.month - 1 or 12
    y = d.year - (1 if d.month == 1 else 0)
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


class AdminView(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app
        self.conn = app.conn
        self._build()

    def _build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkButton(
            top, text="← 貸出/返却に戻る", width=160, fg_color="gray40",
            command=self.app.open_main,
        ).pack(side="left")
        ctk.CTkLabel(top, text="管理メニュー", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", padx=16)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=10)
        for name in ["利用者", "鍵", "貸出状況", "点検", "レポート", "設定"]:
            self.tabs.add(name)

        self._build_users(self.tabs.tab("利用者"))
        self._build_keys(self.tabs.tab("鍵"))
        self._build_status(self.tabs.tab("貸出状況"))
        self._build_inspections(self.tabs.tab("点検"))
        self._build_reports(self.tabs.tab("レポート"))
        self._build_settings(self.tabs.tab("設定"))

    # ============================================================ 利用者
    def _build_users(self, tab) -> None:
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=6)
        ctk.CTkButton(bar, text="＋ 利用者を追加", command=self._add_user).pack(side="left")
        self.users_show_inactive = ctk.CTkCheckBox(
            bar, text="無効も表示", command=self._refresh_users
        )
        self.users_show_inactive.pack(side="left", padx=12)
        self.users_list = ctk.CTkScrollableFrame(tab)
        self.users_list.pack(fill="both", expand=True, pady=6)
        self._refresh_users()

    def _refresh_users(self) -> None:
        for w in self.users_list.winfo_children():
            w.destroy()
        show_inactive = bool(self.users_show_inactive.get())
        for u in models.list_users(self.conn, include_inactive=show_inactive):
            row = ctk.CTkFrame(self.users_list)
            row.pack(fill="x", padx=4, pady=3)
            card = "カード有" if u["idm"] else "カード無"
            state = "" if u["active"] else "（無効）"
            ctk.CTkLabel(
                row, text=f"{u['name']} {state}", anchor="w",
                font=ctk.CTkFont(size=14),
            ).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=card, text_color="gray60").pack(side="left", padx=8)
            if u["active"]:
                ctk.CTkButton(row, text="無効化", width=64, fg_color="#b03a3a",
                              command=lambda uid=u["user_id"]: self._deactivate_user(uid)).pack(side="right", padx=3)
                ctk.CTkButton(row, text="カード再登録", width=110,
                              command=lambda uid=u["user_id"]: self._reassign_card(uid)).pack(side="right", padx=3)
                ctk.CTkButton(row, text="名前変更", width=80, fg_color="gray40",
                              command=lambda uid=u["user_id"], nm=u["name"]: self._rename_user(uid, nm)).pack(side="right", padx=3)

    def _add_user(self) -> None:
        name = dialogs.ask_text(self, "利用者を追加", "利用者名を入力してください")
        if not name:
            return
        try:
            models.create_user(self.conn, name.strip())
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            return
        self._refresh_users()

    def _rename_user(self, uid: int, current: str) -> None:
        name = dialogs.ask_text(self, "名前変更", "新しい名前", initial=current)
        if not name:
            return
        models.update_user_name(self.conn, uid, name.strip())
        self._refresh_users()

    def _reassign_card(self, uid: int) -> None:
        dialogs.info(self, "カードをリーダーにかざしてください。")

        def got(idm: str) -> None:
            try:
                services.assign_card_to_user(self.conn, uid, idm)
                dialogs.info(self, "カードを登録しました。")
            except services.KeylogError as e:
                dialogs.error(self, str(e))
            self._refresh_users()

        self.app.capture_next_card(got)

    def _deactivate_user(self, uid: int) -> None:
        if not dialogs.confirm(self, "この利用者を無効化します。カードの紐付けも解除されます。よろしいですか？"):
            return
        try:
            services.deactivate_user(self.conn, uid)
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            return
        self._refresh_users()

    # ============================================================ 鍵
    def _build_keys(self, tab) -> None:
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=6)
        ctk.CTkButton(bar, text="＋ 鍵を追加", command=self._add_key).pack(side="left")
        self.keys_show_inactive = ctk.CTkCheckBox(
            bar, text="廃棄も表示", command=self._refresh_keys
        )
        self.keys_show_inactive.pack(side="left", padx=12)
        self.keys_list = ctk.CTkScrollableFrame(tab)
        self.keys_list.pack(fill="both", expand=True, pady=6)
        self._refresh_keys()

    def _refresh_keys(self) -> None:
        for w in self.keys_list.winfo_children():
            w.destroy()
        show_inactive = bool(self.keys_show_inactive.get())
        for k in models.list_keys(self.conn, include_inactive=show_inactive):
            row = ctk.CTkFrame(self.keys_list)
            row.pack(fill="x", padx=4, pady=3)
            state = "" if k["active"] else "（廃棄）"
            note = f"／{k['note']}" if k["note"] else ""
            ctk.CTkLabel(
                row, text=f"{k['code']}　{k['name']}{note} {state}", anchor="w",
                font=ctk.CTkFont(size=14),
            ).pack(side="left", padx=8)
            if k["active"]:
                ctk.CTkButton(row, text="廃棄", width=64, fg_color="#b03a3a",
                              command=lambda kid=k["key_id"]: self._discard_key(kid)).pack(side="right", padx=3)
                ctk.CTkButton(row, text="編集", width=64, fg_color="gray40",
                              command=lambda kk=k: self._edit_key(kk)).pack(side="right", padx=3)

    def _key_form(self, title, code="", name="", note=""):
        """管理番号・名称・備考を1画面でまとめて入力させる。"""
        return dialogs.ask_form(
            self, title,
            [
                {"name": "code", "label": "管理番号(例: A-01)", "initial": code, "required": True},
                {"name": "name", "label": "名称(例: 会議室A)", "initial": name, "required": True},
                {"name": "note", "label": "備考(任意・設置場所など)", "initial": note},
            ],
        )

    def _add_key(self) -> None:
        vals = self._key_form("鍵を追加")
        if not vals:
            return
        try:
            models.create_key(self.conn, vals["code"], vals["name"], vals["note"] or None)
        except Exception as e:  # UNIQUE 違反など
            dialogs.error(self, f"追加できません: {e}")
            return
        self._refresh_keys()

    def _edit_key(self, k) -> None:
        vals = self._key_form("鍵を編集", k["code"], k["name"], k["note"] or "")
        if not vals:
            return
        try:
            models.update_key(self.conn, k["key_id"], vals["code"], vals["name"], vals["note"] or None)
        except Exception as e:
            dialogs.error(self, f"更新できません: {e}")
            return
        self._refresh_keys()

    def _discard_key(self, kid: int) -> None:
        if not dialogs.confirm(self, "この鍵を廃棄(無効化)します。よろしいですか？"):
            return
        try:
            services.discard_key(self.conn, kid)
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            return
        self._refresh_keys()

    # ============================================================ 貸出状況
    def _build_status(self, tab) -> None:
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=6)
        ctk.CTkButton(bar, text="更新", width=80, command=self._refresh_status).pack(side="left")
        self.status_count = ctk.CTkLabel(bar, text="")
        self.status_count.pack(side="left", padx=12)
        self.status_list = ctk.CTkScrollableFrame(tab)
        self.status_list.pack(fill="both", expand=True, pady=6)
        self._refresh_status()

    def _refresh_status(self) -> None:
        for w in self.status_list.winfo_children():
            w.destroy()
        rows = models.list_open_checkouts(self.conn)
        self.status_count.configure(text=f"貸出中: {len(rows)} 本")
        if not rows:
            ctk.CTkLabel(self.status_list, text="現在貸出中の鍵はありません").pack(pady=20)
            return
        for r in rows:
            row = ctk.CTkFrame(self.status_list)
            row.pack(fill="x", padx=4, pady=3)
            uinv = "" if r["user_active"] else "（無効利用者）"
            ctk.CTkLabel(
                row,
                text=f"{r['key_code']} {r['key_name']}  ←  {r['user_name']}{uinv}\n貸出: {r['checked_out_at']}",
                anchor="w", justify="left",
            ).pack(side="left", padx=8)
            ctk.CTkButton(row, text="記録取消", width=80, fg_color="#8a6d1a",
                          command=lambda cid=r["checkout_id"]: self._void_checkout(cid)).pack(side="right", padx=3)
            ctk.CTkButton(row, text="代理返却", width=90,
                          command=lambda cid=r["checkout_id"]: self._proxy_return(cid)).pack(side="right", padx=3)

    def _proxy_return(self, cid: int) -> None:
        if not dialogs.confirm(self, "この鍵を返却済みにします(代理返却)。よろしいですか？"):
            return
        try:
            services.return_checkout(self.conn, cid)
        except services.KeylogError as e:
            dialogs.error(self, str(e))
        self._refresh_status()

    def _void_checkout(self, cid: int) -> None:
        if not dialogs.confirm(self, "この貸出記録を取り消します(誤登録の訂正)。記録は削除されます。よろしいですか？"):
            return
        models.delete_checkout(self.conn, cid)
        self._refresh_status()

    # ============================================================ 点検
    def _build_inspections(self, tab) -> None:
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", pady=6)
        ctk.CTkButton(bar, text="点検を実施", command=self._do_inspection).pack(side="left")
        self.insp_list = ctk.CTkScrollableFrame(tab, label_text="点検履歴")
        self.insp_list.pack(fill="both", expand=True, pady=6)
        self._refresh_inspections()

    def _refresh_inspections(self) -> None:
        for w in self.insp_list.winfo_children():
            w.destroy()
        for r in models.list_inspections(self.conn):
            res = "問題あり" if r["result"] == "issue" else "問題なし"
            note = f"／{r['note']}" if r["note"] else ""
            ctk.CTkLabel(
                self.insp_list,
                text=f"{r['inspected_at']}  {r['inspector']}  [{res}]{note}",
                anchor="w",
            ).pack(fill="x", padx=8, pady=2)

    def _do_inspection(self) -> None:
        open_rows = models.list_open_checkouts(self.conn)
        listing = "\n".join(f"・{r['key_code']} {r['key_name']}（{r['user_name']}）" for r in open_rows) or "（なし）"
        dialogs.info(self, f"現在貸出中（手元に無いはずの鍵）:\n{listing}", title="点検の参考")
        inspector = dialogs.ask_text(self, "点検の実施", "点検者名を入力してください")
        if not inspector:
            return
        issue = dialogs.confirm(self, "点検で問題は見つかりましたか？（はい=問題あり / いいえ=問題なし）", title="点検結果")
        note = dialogs.ask_text(self, "点検の実施", "所見・特記事項（任意）")
        try:
            services.record_inspection(
                self.conn, inspector, "issue" if issue else "ok", note or None
            )
        except services.KeylogError as e:
            dialogs.error(self, str(e))
            return
        self._refresh_inspections()

    # ============================================================ レポート
    def _build_reports(self, tab) -> None:
        frm = ctk.CTkFrame(tab, fg_color="transparent")
        frm.pack(fill="x", pady=10, padx=6)

        ctk.CTkLabel(frm, text="鍵別 使用レポート(PDF)", font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ctk.CTkLabel(frm, text="対象の鍵:").grid(row=1, column=0, sticky="w", pady=4)
        self._key_options = models.list_keys(self.conn, include_inactive=True)
        labels = [f"{k['code']} {k['name']}" for k in self._key_options] or ["（鍵なし）"]
        self.report_key = ctk.CTkOptionMenu(frm, values=labels)
        self.report_key.grid(row=1, column=1, sticky="w", pady=4)

        today = date.today()
        ctk.CTkLabel(frm, text="開始日:").grid(row=2, column=0, sticky="w", pady=4)
        self.report_start = DatePicker(frm, initial=_month_ago(today))
        self.report_start.grid(row=2, column=1, sticky="w", pady=4)

        ctk.CTkLabel(frm, text="終了日:").grid(row=3, column=0, sticky="w", pady=4)
        self.report_end = DatePicker(frm, initial=today)
        self.report_end.grid(row=3, column=1, sticky="w", pady=4)

        ctk.CTkLabel(
            frm, text="※ 📅 でカレンダー表示、直接入力も可。既定は直近1ヶ月。",
            text_color="gray60",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))

        ctk.CTkButton(frm, text="PDF を出力", command=self._export_pdf).grid(row=5, column=0, columnspan=2, sticky="w", pady=12)

        ctk.CTkLabel(frm, text="全履歴 CSV", font=ctk.CTkFont(size=15, weight="bold")).grid(row=6, column=0, columnspan=2, sticky="w", pady=(16, 8))
        ctk.CTkButton(frm, text="CSV を出力", command=self._export_csv).grid(row=7, column=0, sticky="w")

    def _selected_key_id(self):
        if not self._key_options:
            return None
        idx = self.report_key._values.index(self.report_key.get())
        return self._key_options[idx]["key_id"]

    def _export_pdf(self) -> None:
        kid = self._selected_key_id()
        if kid is None:
            dialogs.error(self, "鍵がありません。")
            return
        try:
            start_d = self.report_start.get_date()
            end_d = self.report_end.get_date()
        except Exception:
            dialogs.error(self, "日付の形式が正しくありません(YYYY-MM-DD)。")
            return
        if start_d > end_d:
            dialogs.error(self, "開始日が終了日より後になっています。")
            return
        start = start_d.strftime("%Y-%m-%d")
        end = end_d.strftime("%Y-%m-%d") + " 23:59:59"  # 終了日は当日いっぱいを含める

        key = models.get_key(self.conn, kid)
        default_name = f"key_report_{key['code']}_{_stamp()}.pdf"

        # 1) 一時ファイルに生成し、既定ビューアでプレビュー表示
        tmp = Path(tempfile.gettempdir()) / f"keylog_preview_{_stamp()}.pdf"
        try:
            reports.key_usage_pdf(self.conn, kid, tmp, start, end)
        except Exception as e:
            dialogs.error(self, f"PDF 生成に失敗: {e}")
            return
        try:
            os.startfile(str(tmp))  # noqa: S606 (Windows プレビュー)
        except Exception:
            pass

        # 2) プレビュー確認後に保存(既定はダウンロードフォルダ)
        if not dialogs.confirm(self, "プレビューを表示しました。この内容で保存しますか？", title="PDF の保存"):
            return
        dest = filedialog.asksaveasfilename(
            parent=self,
            title="PDF の保存先",
            defaultextension=".pdf",
            filetypes=[("PDF ファイル", "*.pdf")],
            initialdir=self._default_export_dir(),
            initialfile=default_name,
        )
        if not dest:  # キャンセル
            return
        try:
            shutil.copyfile(tmp, dest)
        except Exception as e:
            dialogs.error(self, f"保存に失敗: {e}")
            return
        dialogs.info(self, f"保存しました:\n{dest}")

    def _export_csv(self) -> None:
        out = filedialog.asksaveasfilename(
            parent=self,
            title="CSV の保存先を選択",
            defaultextension=".csv",
            filetypes=[("CSV ファイル", "*.csv")],
            initialdir=self._default_export_dir(),
            initialfile=f"checkouts_{_stamp()}.csv",
        )
        if not out:  # キャンセル
            return
        try:
            path = reports.checkouts_csv(self.conn, out)
        except Exception as e:
            dialogs.error(self, f"CSV 出力に失敗: {e}")
            return
        self._offer_open(path)

    def _default_export_dir(self) -> str:
        """エクスポートの既定保存先(ダウンロードフォルダ、無ければホーム)。"""
        d = config.DOWNLOADS_DIR
        return str(d if d.exists() else Path.home())

    def _offer_open(self, path) -> None:
        if dialogs.confirm(self, f"出力しました:\n{path}\n\n今すぐ開きますか？", title="出力完了"):
            try:
                os.startfile(str(path))  # noqa: S606 (Windows)
            except Exception as e:
                dialogs.error(self, f"開けませんでした: {e}")

    # ============================================================ 設定
    def _build_settings(self, tab) -> None:
        frm = ctk.CTkFrame(tab, fg_color="transparent")
        frm.pack(fill="x", pady=12, padx=6)
        ctk.CTkLabel(frm, text="管理者 PIN", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkButton(frm, text="PIN を変更", command=self._change_pin).pack(anchor="w", pady=(6, 18))
        ctk.CTkLabel(frm, text="バックアップ", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(frm, text="データベースの整合性のあるコピーを exports/ に保存します。",
                     text_color="gray60").pack(anchor="w", pady=(2, 6))
        ctk.CTkButton(frm, text="今すぐバックアップ", command=self._backup).pack(anchor="w")

    def _change_pin(self) -> None:
        new = dialogs.ask_pin(self, "新しい PIN")
        if not new:
            return
        confirm_pin = dialogs.ask_pin(self, "新しい PIN(確認)")
        if new != confirm_pin:
            dialogs.error(self, "PIN が一致しません。")
            return
        services.set_admin_pin(self.conn, new)
        dialogs.info(self, "PIN を変更しました。")

    def _backup(self) -> None:
        out = config.EXPORTS_DIR / f"keylog_backup_{_stamp()}.db"
        try:
            path = services.backup_db(self.conn, out)
        except Exception as e:
            dialogs.error(self, f"バックアップに失敗: {e}")
            return
        dialogs.info(self, f"バックアップしました:\n{path}")
