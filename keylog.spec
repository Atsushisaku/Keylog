# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller ビルド定義。

    uv run pyinstaller keylog.spec

- onefile(単一 exe)。データ(data/keylog.db)は exe と同じフォルダに作られる。
- customtkinter / tkcalendar / babel / reportlab / pyscard の同梱物を明示収集。
"""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for _pkg in ("customtkinter", "tkcalendar", "babel", "reportlab", "smartcard"):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

a = Analysis(
    ["run.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Keylog",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # GUI アプリなのでコンソールを出さない
    disable_windowed_traceback=False,
)
