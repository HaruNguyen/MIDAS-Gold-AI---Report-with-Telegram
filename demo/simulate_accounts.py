"""
Script demo: mo phong nhieu tai khoan MT5 dang chay MIDAS Gold AI EA,
gui snapshot lien tiep len Report Server (giong nhu EA thuc se lam qua WebRequest),
de kiem tra toan bo pipeline: phan loai rui ro -> luu DB -> canh bao Telegram.

Cach dung:
    1. Chay backend o terminal khac:  uvicorn backend.main:app --reload --port 8000
    2. Chay script nay:               python demo/simulate_accounts.py

Khong can MT5 thuc — script tu sinh du lieu gia lap, bao gom 1 kich ban
"tai khoan xau di dan" de bot Telegram phai canh bao escalation.
"""
import os
import time
import random
from datetime import date, timedelta

import requests

API_URL = os.getenv("REPORT_API_URL", "http://localhost:8000/api/report")
API_KEY = os.getenv("REPORT_API_KEY", "CHANGE_ME_SECRET_KEY")


def base_payload(login, server, preset, is_cent, license_days):
    return {
        "api_key": API_KEY,
        "login": login,
        "server": server,
        "symbol": "XAUUSD",
        "preset": preset,
        "is_cent": is_cent,
        "loop_active": True,
        "hedge_active": False,
        "zone_points": 50,
        "tp_points": 100,
        "multiplier": 1.3 if preset == "Master Alpha" else 1.5,
        "max_orders": 30,
        "license_expiry": str(date.today() + timedelta(days=license_days)),
    }


def snapshot(payload, balance, equity, total_orders, buy, sell, total_lots,
             closed_lots_today, ai_confidence, hedge_active=False):
    payload = dict(payload)
    drawdown_pct = max(0.0, (balance - equity) / balance * 100) if balance else 0
    payload.update({
        "balance": balance,
        "equity": equity,
        "margin_level": random.uniform(150, 800),
        "floating_pl": equity - balance,
        "drawdown_pct": round(drawdown_pct, 2),
        "total_orders": total_orders,
        "buy_orders": buy,
        "sell_orders": sell,
        "total_lots": total_lots,
        "closed_lots_today": closed_lots_today,
        "hedge_active": hedge_active,
        "ai_confidence": ai_confidence,
    })
    return payload


def send(payload):
    r = requests.post(API_URL, json=payload, timeout=10)
    print(f"  -> {payload['login']:>8}  orders={payload['total_orders']:<3} "
          f"DD={payload['drawdown_pct']:<6}  status={r.status_code}  resp={r.json()}")


def main():
    print("=== Kich ban 1: Tai khoan Cent on dinh (Master Alpha) ===")
    acc1 = base_payload("100001", "Taurex-Demo", "Master Alpha", True, license_days=45)
    send(snapshot(acc1, balance=100000, equity=99200, total_orders=6, buy=3, sell=3,
                   total_lots=0.45, closed_lots_today=2.1, ai_confidence=0))
    time.sleep(1)

    print("\n=== Kich ban 2: Tai khoan xau di dan -> kich hoat escalation alert ===")
    acc2 = base_payload("100002", "Exness-Real3", "Master Elite", False, license_days=5)
    steps = [
        dict(balance=5000, equity=4900, total_orders=8, buy=4, sell=4, total_lots=1.2,
             closed_lots_today=3.4, ai_confidence=0),
        dict(balance=5000, equity=4500, total_orders=17, buy=9, sell=8, total_lots=4.8,
             closed_lots_today=6.1, ai_confidence=62),
        dict(balance=5000, equity=3600, total_orders=27, buy=14, sell=13, total_lots=18.5,
             closed_lots_today=9.0, ai_confidence=78),
        dict(balance=5000, equity=3550, total_orders=28, buy=14, sell=14, total_lots=20.0,
             closed_lots_today=0.0, ai_confidence=80, hedge_active=True),
    ]
    for s in steps:
        send(snapshot(acc2, **s))
        time.sleep(1)

    print("\n=== Kich ban 3: Tai khoan vua duoc giai cuu (Hedge -> Safe) ===")
    acc3 = base_payload("100003", "ICMarkets-Live", "Master Alpha", False, license_days=1)
    send(snapshot(acc3, balance=2000, equity=1400, total_orders=29, buy=15, sell=14,
                   total_lots=22.0, closed_lots_today=0, ai_confidence=85, hedge_active=True))
    time.sleep(1)
    send(snapshot(acc3, balance=2000, equity=1980, total_orders=2, buy=1, sell=1,
                   total_lots=0.1, closed_lots_today=12.4, ai_confidence=0, hedge_active=False))

    print("\nXong. Kiem tra Telegram chat de xem cac canh bao da nhan (neu da cau hinh TELEGRAM_BOT_TOKEN).")
    print("Hoac goi GET /docs, hay dung lenh /accounts, /risk, /digest tren bot Telegram.")


if __name__ == "__main__":
    main()
