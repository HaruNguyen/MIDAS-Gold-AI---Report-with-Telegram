"""
MIDAS Gold AI — Report Server
------------------------------
FastAPI app nhan snapshot tu EA (qua ReportModule.mqh), luu DB, phan loai rui ro,
va day canh bao / digest sang Telegram.

Chay local:
    uvicorn backend.main:app --reload --port 8000

EA se POST JSON toi:  http://<server-ip>:8000/api/report
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session

from .config import settings
from .database import init_db, get_db
from .models import Account, Snapshot
from .schemas import ReportIn
from .risk import classify_health, should_alert
from .telegram_bot import notifier, build_application
from .scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("midas_report.main")

telegram_app = None
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    global telegram_app, scheduler

    if settings.TELEGRAM_BOT_TOKEN:
        telegram_app = build_application(settings.TELEGRAM_BOT_TOKEN)
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        logger.info("Telegram command bot da khoi dong (polling).")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN trong rong — bot lenh se khong chay, chi luu DB.")

    scheduler = start_scheduler()

    yield

    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
    if scheduler:
        scheduler.shutdown()


app = FastAPI(title="MIDAS Gold AI - Report Server", lifespan=lifespan)


@app.get("/")
def root():
    return {"status": "ok", "service": "MIDAS Gold AI Report Server"}


@app.post("/api/report")
async def receive_report(payload: ReportIn, db: Session = Depends(get_db)):
    if payload.api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    account = db.query(Account).filter(Account.login == payload.login).first()
    if not account:
        account = Account(
            login=payload.login,
            server=payload.server,
            symbol=payload.symbol,
            preset=payload.preset,
            is_cent=payload.is_cent,
            license_expiry=payload.license_expiry,
            last_health_status="SAFE",
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    else:
        # cap nhat cac field co the thay doi (cau hinh, license)
        account.preset = payload.preset
        account.is_cent = payload.is_cent
        if payload.license_expiry:
            account.license_expiry = payload.license_expiry

    health_status = classify_health(payload.total_orders, payload.hedge_active, payload.drawdown_pct)

    snap = Snapshot(
        account_id=account.id,
        balance=payload.balance,
        equity=payload.equity,
        margin_level=payload.margin_level,
        floating_pl=payload.floating_pl,
        drawdown_pct=payload.drawdown_pct,
        total_orders=payload.total_orders,
        buy_orders=payload.buy_orders,
        sell_orders=payload.sell_orders,
        total_lots=payload.total_lots,
        closed_lots_today=payload.closed_lots_today,
        loop_active=payload.loop_active,
        hedge_active=payload.hedge_active,
        ai_confidence=payload.ai_confidence,
        zone_points=payload.zone_points,
        tp_points=payload.tp_points,
        multiplier=payload.multiplier,
        max_orders=payload.max_orders,
        health_status=health_status,
        reported_at=payload.timestamp or datetime.utcnow(),
    )
    db.add(snap)

    if should_alert(account.last_health_status, health_status):
        await notifier.alert_health_change(account, snap)

    account.last_health_status = health_status
    db.commit()

    return {"status": "received", "health_status": health_status}
