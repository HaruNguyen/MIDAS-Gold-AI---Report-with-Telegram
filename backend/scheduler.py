"""
Cac job chay dinh ky:
1. Daily digest  — tong hop suc khoe / volume / license, gui 1 lan/ngay vao gio cau hinh.
2. License check — quet hang ngay, canh bao truoc han thue bot theo cac moc 30/14/7/1 ngay.
"""
import asyncio
import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .database import SessionLocal
from .models import Account
from .risk import license_alert_tier
from .telegram_bot import notifier

logger = logging.getLogger("midas_report.scheduler")


async def job_daily_digest():
    db = SessionLocal()
    try:
        await notifier.daily_digest(db)
    except Exception:
        logger.exception("Loi khi gui daily digest")
    finally:
        db.close()


async def job_license_check():
    db = SessionLocal()
    try:
        accounts = db.query(Account).filter(Account.license_expiry.isnot(None)).all()
        for acc in accounts:
            days_remaining = (acc.license_expiry - date.today()).days
            if license_alert_tier(days_remaining) is not None:
                await notifier.alert_license_expiry(acc, days_remaining)
    except Exception:
        logger.exception("Loi khi kiem tra license")
    finally:
        db.close()


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        job_daily_digest, "cron",
        hour=settings.DAILY_DIGEST_HOUR, minute=settings.DAILY_DIGEST_MINUTE,
        id="daily_digest",
    )
    scheduler.add_job(
        job_license_check, "cron",
        hour=settings.DAILY_DIGEST_HOUR, minute=settings.DAILY_DIGEST_MINUTE + 1,
        id="license_check",
    )
    scheduler.start()
    logger.info("Scheduler started: daily_digest @ %02d:%02d", settings.DAILY_DIGEST_HOUR, settings.DAILY_DIGEST_MINUTE)
    return scheduler
