"""RC-S300 / FeliCa 読み取りテスト.

実行するとカード待ち受け状態になります。
カードをリーダーに載せるたびに IDm(製造ID) と PMm(製造パラメータ) を表示します。
終了は Ctrl+C。

使い方:
    py read_test.py
"""
import io
import sys
import time

# Windows コンソールの文字化け防止 + 即時表示(行バッファリング)
sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer, encoding="utf-8", errors="replace",
    line_buffering=True, write_through=True,
)

from smartcard.System import readers


def to_hex(data):
    return "".join(f"{b:02X}" for b in data)


def read_once(reader):
    """カードが載っていれば読み取って True。無ければ False。"""
    try:
        conn = reader.createConnection()
        conn.connect()
    except Exception:
        return False

    try:
        atr = conn.getATR()
        print(f"  ATR : {to_hex(atr)}")

        idm, sw1, sw2 = conn.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
        if (sw1, sw2) == (0x90, 0x00):
            print(f"  IDm : {to_hex(idm)}  ← 製造ID(カード固有)")
        else:
            print(f"  IDm 取得失敗: SW={sw1:02X}{sw2:02X}")

        pmm, sw1, sw2 = conn.transmit([0xFF, 0xCA, 0x00, 0x01, 0x00])
        if (sw1, sw2) == (0x90, 0x00):
            print(f"  PMm : {to_hex(pmm)}")
        print("  → 読み取り成功\n")
    finally:
        try:
            conn.disconnect()
        except Exception:
            pass
    return True


def main():
    rs = readers()
    if not rs:
        print("リーダーが見つかりません。USB 接続を確認してください。")
        return 1

    reader = rs[0]
    print(f"リーダー: {reader}")
    print("カードを載せてください（終了は Ctrl+C）\n")

    card_present = False
    try:
        while True:
            if read_once(reader):
                if not card_present:
                    card_present = True
                # カードが離れるまで連続表示しない
                time.sleep(1.0)
            else:
                card_present = False
                time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n終了しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
