"""レポート出力: 鍵別使用レポート(PDF) と 履歴 CSV。

- PDF: reportlab。日本語は同梱 CID フォント HeiseiKakuGo-W5(外部フォント不要)。
- CSV: Excel で文字化けしないよう UTF-8 BOM 付き。
"""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import models

_JP_FONT = "HeiseiKakuGo-W5"
_font_registered = False


def _ensure_font() -> None:
    global _font_registered
    if not _font_registered:
        pdfmetrics.registerFont(UnicodeCIDFont(_JP_FONT))
        _font_registered = True


def _parse_dt(s: str) -> datetime:
    """now_iso() 形式(スペース区切り)も T 区切りも受ける。"""
    return datetime.fromisoformat(s.replace("T", " "))


def _duration_text(checked_out_at: str, returned_at: str | None) -> str:
    if not returned_at:
        return "（貸出中）"
    delta = _parse_dt(returned_at) - _parse_dt(checked_out_at)
    total_min = int(delta.total_seconds() // 60)
    h, m = divmod(total_min, 60)
    if h and m:
        return f"{h}時間{m}分"
    if h:
        return f"{h}時間"
    return f"{m}分"


def key_usage_pdf(
    conn: sqlite3.Connection,
    key_id: int,
    out_path: Path | str,
    start: str | None = None,
    end: str | None = None,
) -> Path:
    """鍵別の使用履歴を A4 縦 PDF に出力する。"""
    _ensure_font()
    key = models.get_key(conn, key_id)
    if key is None:
        raise ValueError("鍵が見つかりません。")
    rows = models.list_checkouts_for_key(conn, key_id, start, end)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    title_style.fontName = _JP_FONT
    normal = styles["Normal"]
    normal.fontName = _JP_FONT

    period = "全期間"
    if start or end:
        period = f"{start or '—'} 〜 {end or '—'}"

    story = [
        Paragraph("鍵 使用レポート", title_style),
        Spacer(1, 6 * mm),
        Paragraph(f"鍵: {key['code']}　{key['name']}", normal),
        Paragraph(f"対象期間: {period}", normal),
        Paragraph(f"出力日時: {datetime.now().replace(microsecond=0).isoformat(sep=' ')}", normal),
        Spacer(1, 6 * mm),
    ]

    header = ["利用者", "貸出日時", "返却日時", "利用時間"]
    data = [header]
    for r in rows:
        data.append(
            [
                r["user_name"],
                r["checked_out_at"],
                r["returned_at"] or "（貸出中）",
                _duration_text(r["checked_out_at"], r["returned_at"]),
            ]
        )
    if len(data) == 1:
        data.append(["（記録なし）", "", "", ""])

    table = Table(data, colWidths=[35 * mm, 45 * mm, 45 * mm, 30 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _JP_FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b3a55")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f8")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title=f"鍵使用レポート {key['code']}",
    )
    doc.build(story)
    return out_path


def checkouts_csv(
    conn: sqlite3.Connection, out_path: Path | str, key_id: int | None = None
) -> Path:
    """貸出履歴を CSV(UTF-8 BOM)に出力する。key_id 指定でその鍵だけ。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if key_id is not None:
        rows = models.list_checkouts_for_key(conn, key_id)
        records = [
            {
                "key_id": key_id,
                "user_name": r["user_name"],
                "checked_out_at": r["checked_out_at"],
                "returned_at": r["returned_at"] or "",
            }
            for r in rows
        ]
    else:
        raw = conn.execute(
            """
            SELECT k.code AS key_code, k.name AS key_name, u.name AS user_name,
                   c.checked_out_at, c.returned_at
            FROM checkouts c
            JOIN keys k ON k.key_id = c.key_id
            JOIN users u ON u.user_id = c.user_id
            ORDER BY c.checked_out_at
            """
        ).fetchall()
        records = [
            {
                "key_code": r["key_code"],
                "key_name": r["key_name"],
                "user_name": r["user_name"],
                "checked_out_at": r["checked_out_at"],
                "returned_at": r["returned_at"] or "",
            }
            for r in raw
        ]

    fieldnames = list(records[0].keys()) if records else [
        "key_code", "key_name", "user_name", "checked_out_at", "returned_at"
    ]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return out_path
