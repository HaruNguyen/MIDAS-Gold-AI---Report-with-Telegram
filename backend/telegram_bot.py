"""
Telegram bot cho MIDAS Gold AI Report App.

Hai vai tro:
1. NOTIFIER  — server tu day canh bao / digest sang chat cua chu bot (push, khong can lenh).
2. COMMAND BOT — chu bot go lenh /accounts /account /risk /volume /licenses de tra cuu nhanh.
"""
import logging
from datetime import date, datetime, timedelta

from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import Account, Snapshot
from .risk import HEALTH_EMOJI, estimate_ib_revenue

logger = logging.getLogger("midas_report.telegram")


# --------------------------------------------------------------------------
# NOTIFIER — goi tu main.py / scheduler.py de PUSH tin chu dong
# --------------------------------------------------------------------------
class Notifier:
    def __init__(self, token: str, default_chat_id: str):
        self.bot = Bot(token=token) if token else None
        self.default_chat_id = default_chat_id

    async def send(self, text: str, chat_id: str = None):
        if not self.bot:
            logger.warning("TELEGRAM_BOT_TOKEN chua duoc cau hinh — bo qua gui tin: %s", text[:80])
            return
        await self.bot.send_message(
            chat_id=chat_id or self.default_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )

    async def alert_health_change(self, account: Account, snap: Snapshot):
        emoji = HEALTH_EMOJI.get(snap.health_status, "⚪")
        text = (
            f"{emoji} <b>{snap.health_status}</b> — TK <code>{account.login}</code> ({account.preset})\n"
            f"Server: {account.server} | Symbol: {account.symbol}\n"
            f"Lệnh đang mở: <b>{snap.total_orders}</b> (Buy {snap.buy_orders} / Sell {snap.sell_orders})\n"
            f"Equity: {snap.equity:,.2f} | Drawdown: <b>{snap.drawdown_pct:.1f}%</b>\n"
            f"Loop: {'ON' if snap.loop_active else 'OFF'} | Hedge: {'ON ⚠️' if snap.hedge_active else 'OFF'}\n"
            f"AI Confidence: {snap.ai_confidence:.0f}%\n"
            f"⏱ {snap.reported_at:%Y-%m-%d %H:%M}"
        )
        await self.send(text)

    async def alert_license_expiry(self, account: Account, days_remaining: int):
        text = (
            f"📅 <b>Sắp hết hạn thuê bot</b> — TK <code>{account.login}</code>\n"
            f"Chủ tài khoản: {account.owner_label or 'N/A'}\n"
            f"Hết hạn: <b>{account.license_expiry}</b> (còn {days_remaining} ngày)\n"
            f"→ Nhắc gia hạn (~$600/năm giá gốc, biên giá do bạn định) để tránh mất volume IB."
        )
        await self.send(text)

    async def daily_digest(self, db: Session):
        text = build_daily_digest_text(db)
        await self.send(text)


def build_daily_digest_text(db: Session) -> str:
    accounts = db.query(Account).all()
    if not accounts:
        return "📊 <b>MIDAS Daily Digest</b>\nChưa có tài khoản nào được ghi nhận."

    lines = [f"📊 <b>MIDAS Daily Digest</b> — {date.today():%Y-%m-%d}", ""]

    total_volume_today = 0.0
    counts = {"SAFE": 0, "WATCH": 0, "CRITICAL": 0, "HEDGE_LOCKED": 0}
    risk_lines = []

    for acc in accounts:
        last_snap = (
            db.query(Snapshot)
            .filter(Snapshot.account_id == acc.id)
            .order_by(Snapshot.reported_at.desc())
            .first()
        )
        if not last_snap:
            continue
        counts[last_snap.health_status] = counts.get(last_snap.health_status, 0) + 1
        total_volume_today += last_snap.closed_lots_today or 0

        if last_snap.health_status in ("CRITICAL", "HEDGE_LOCKED"):
            emoji = HEALTH_EMOJI.get(last_snap.health_status, "⚪")
            risk_lines.append(
                f"  {emoji} <code>{acc.login}</code> — {last_snap.total_orders} lệnh, "
                f"DD {last_snap.drawdown_pct:.1f}%"
            )

    revenue_today = estimate_ib_revenue(total_volume_today)

    lines.append(f"Tổng tài khoản theo dõi: <b>{len(accounts)}</b>")
    lines.append(
        f"🟢 An toàn: {counts.get('SAFE', 0)}  |  🟡 Theo dõi: {counts.get('WATCH', 0)}  |  "
        f"🔴 Nguy hiểm: {counts.get('CRITICAL', 0)}  |  ⛔ Hedge: {counts.get('HEDGE_LOCKED', 0)}"
    )
    lines.append(f"💰 Volume khớp hôm nay: <b>{total_volume_today:.2f} lot</b> ≈ <b>${revenue_today:,.2f}</b> IB")

    if risk_lines:
        lines.append("")
        lines.append("⚠️ <b>Tài khoản cần chú ý:</b>")
        lines.extend(risk_lines)

    expiring = [
        a for a in accounts
        if a.license_expiry and 0 <= (a.license_expiry - date.today()).days <= 7
    ]
    if expiring:
        lines.append("")
        lines.append("📅 <b>Sắp hết hạn license (≤7 ngày):</b>")
        for a in expiring:
            d = (a.license_expiry - date.today()).days
            lines.append(f"  • <code>{a.login}</code> — còn {d} ngày ({a.license_expiry})")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# COMMAND BOT — chu bot tra cuu thu cong bang lenh trong Telegram
# --------------------------------------------------------------------------
def _db() -> Session:
    return SessionLocal()


async def cmd_help(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Lệnh khả dụng:\n"
        "/accounts — danh sách tài khoản & trạng thái hiện tại\n"
        "/account <login> — chi tiết 1 tài khoản\n"
        "/risk — danh sách tài khoản đang WATCH/CRITICAL/HEDGE\n"
        "/volume — tổng volume & doanh thu IB ước tính hôm nay\n"
        "/licenses — tài khoản sắp hết hạn thuê bot\n"
        "/digest — xem digest tổng hợp ngay lúc này"
    )


async def cmd_accounts(update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        accounts = db.query(Account).all()
        if not accounts:
            await update.message.reply_text("Chưa có tài khoản nào.")
            return
        lines = ["📋 <b>Danh sách tài khoản</b>"]
        for acc in accounts:
            last = (
                db.query(Snapshot)
                .filter(Snapshot.account_id == acc.id)
                .order_by(Snapshot.reported_at.desc())
                .first()
            )
            emoji = HEALTH_EMOJI.get(last.health_status, "⚪") if last else "⚪"
            orders = last.total_orders if last else "-"
            lines.append(f"{emoji} <code>{acc.login}</code> ({acc.preset}) — {orders} lệnh")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    finally:
        db.close()


async def cmd_account(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Dùng: /account <login>")
        return
    login = context.args[0]
    db = _db()
    try:
        acc = db.query(Account).filter(Account.login == login).first()
        if not acc:
            await update.message.reply_text(f"Không tìm thấy tài khoản {login}.")
            return
        last = (
            db.query(Snapshot)
            .filter(Snapshot.account_id == acc.id)
            .order_by(Snapshot.reported_at.desc())
            .first()
        )
        if not last:
            await update.message.reply_text("Tài khoản chưa có dữ liệu báo cáo.")
            return
        emoji = HEALTH_EMOJI.get(last.health_status, "⚪")
        text = (
            f"{emoji} <b>{acc.login}</b> — {acc.preset} ({'Cent' if acc.is_cent else 'USD'})\n"
            f"Server: {acc.server} | Symbol: {acc.symbol}\n"
            f"Balance: {last.balance:,.2f} | Equity: {last.equity:,.2f}\n"
            f"Floating P/L: {last.floating_pl:,.2f} | Drawdown: {last.drawdown_pct:.1f}%\n"
            f"Lệnh mở: {last.total_orders} (Buy {last.buy_orders}/Sell {last.sell_orders}) | Tổng lot: {last.total_lots:.2f}\n"
            f"Zone: {last.zone_points}pts | TP: {last.tp_points}pts | Multiplier: {last.multiplier} | Max orders: {last.max_orders}\n"
            f"Loop: {'ON' if last.loop_active else 'OFF'} | Hedge: {'ON' if last.hedge_active else 'OFF'}\n"
            f"AI Confidence: {last.ai_confidence:.0f}%\n"
            f"License hết hạn: {acc.license_expiry}\n"
            f"Cập nhật: {last.reported_at:%Y-%m-%d %H:%M}"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    finally:
        db.close()


async def cmd_risk(update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        accounts = db.query(Account).all()
        lines = ["⚠️ <b>Tài khoản cần chú ý</b>"]
        found = False
        for acc in accounts:
            last = (
                db.query(Snapshot)
                .filter(Snapshot.account_id == acc.id)
                .order_by(Snapshot.reported_at.desc())
                .first()
            )
            if last and last.health_status in ("WATCH", "CRITICAL", "HEDGE_LOCKED"):
                found = True
                emoji = HEALTH_EMOJI.get(last.health_status, "⚪")
                lines.append(
                    f"{emoji} <code>{acc.login}</code> — {last.total_orders} lệnh, DD {last.drawdown_pct:.1f}%"
                )
        if not found:
            lines.append("Không có tài khoản nào trong vùng rủi ro. 🎉")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    finally:
        db.close()


async def cmd_volume(update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        total_today = db.query(func.sum(Snapshot.closed_lots_today)).scalar() or 0
        # Luu y: day la xap xi tu snapshot gan nhat moi tai khoan trong demo;
        # ban dau xuat (production) nen aggregat theo deal history thuc thay vi lay tong snapshot.
        revenue = estimate_ib_revenue(total_today)
        await update.message.reply_text(
            f"💰 <b>Volume hôm nay</b>\nTổng lot khớp: <b>{total_today:.2f}</b>\n"
            f"Doanh thu IB ước tính: <b>${revenue:,.2f}</b> (rate ${settings.IB_RATE_USD_PER_LOT}/lot)",
            parse_mode=ParseMode.HTML,
        )
    finally:
        db.close()


async def cmd_licenses(update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        accounts = db.query(Account).filter(Account.license_expiry.isnot(None)).all()
        soon = [a for a in accounts if (a.license_expiry - date.today()).days <= 30]
        if not soon:
            await update.message.reply_text("Không có license nào sắp hết hạn trong 30 ngày tới.")
            return
        lines = ["📅 <b>License sắp hết hạn (≤30 ngày)</b>"]
        for a in sorted(soon, key=lambda x: x.license_expiry):
            d = (a.license_expiry - date.today()).days
            lines.append(f"• <code>{a.login}</code> — còn {d} ngày ({a.license_expiry})")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    finally:
        db.close()


async def cmd_digest(update, context: ContextTypes.DEFAULT_TYPE):
    db = _db()
    try:
        text = build_daily_digest_text(db)
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    finally:
        db.close()


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("accounts", cmd_accounts))
    app.add_handler(CommandHandler("account", cmd_account))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("volume", cmd_volume))
    app.add_handler(CommandHandler("licenses", cmd_licenses))
    app.add_handler(CommandHandler("digest", cmd_digest))
    return app


notifier = Notifier(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID)
