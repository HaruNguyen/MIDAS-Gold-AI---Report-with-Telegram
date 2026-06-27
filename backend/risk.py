"""
Logic phan loai "suc khoe bo lenh" va quyet dinh khi nao can canh bao.

Nguong duoc lay truc tiep tu cong thuc van hanh cua bot (file GOLD Bot EA.docx):
  - < 15 lenh                -> SAFE        (an toan)
  - 15 - 25 lenh             -> WATCH        (AI bat dau can thiep nang lot tu lenh 15)
  - >= 26 lenh hoac Hedge ON -> CRITICAL/HEDGE_LOCKED (gan/dang trong vung Hedge cung, max 26-30)
"""
from .config import settings

HEALTH_RANK = {"SAFE": 0, "WATCH": 1, "CRITICAL": 2, "HEDGE_LOCKED": 3}

HEALTH_EMOJI = {
    "SAFE": "🟢",
    "WATCH": "🟡",
    "CRITICAL": "🔴",
    "HEDGE_LOCKED": "⛔",
}

HEALTH_VN = {
    "SAFE": "AN TOÀN",
    "WATCH": "THEO DÕI",
    "CRITICAL": "NGUY HIỂM",
    "HEDGE_LOCKED": "HEDGE LOCK",
}

HEALTH_DESC = {
    "SAFE": "Bộ lệnh khỏe, chạy đúng kịch bản toán học. Để cho máy làm việc.",
    "WATCH": "AI đang can thiệp nâng lot từ lệnh thứ 15. Theo dõi sát, chưa cần hành động.",
    "CRITICAL": "Bộ lệnh sát ngưỡng Hedge (≥26 lệnh hoặc DD cao). Cần chú ý, chuẩn bị kịch bản xử lý.",
    "HEDGE_LOCKED": "Đã kích hoạt Hedge — chế độ phòng thủ cuối. Theo dõi liên tục tới khi thoát Hedge.",
}


def classify_health(total_orders: int, hedge_active: bool, drawdown_pct: float) -> str:
    if hedge_active:
        return "HEDGE_LOCKED"
    if total_orders >= settings.ORDERS_CRITICAL_THRESHOLD or drawdown_pct >= settings.DRAWDOWN_CRITICAL_PCT:
        return "CRITICAL"
    if total_orders >= settings.ORDERS_WATCH_THRESHOLD or drawdown_pct >= settings.DRAWDOWN_WARNING_PCT:
        return "WATCH"
    return "SAFE"


def should_alert(previous_status: str, current_status: str) -> bool:
    """Chi canh bao khi tinh trang XAU DI (escalation) de tranh spam Telegram.
    Van canh bao khi tu CRITICAL/HEDGE_LOCKED tro ve SAFE (tin tot: da duoc giai cuu)."""
    prev_rank = HEALTH_RANK.get(previous_status, 0)
    cur_rank = HEALTH_RANK.get(current_status, 0)
    if cur_rank > prev_rank:
        return True  # xau di -> bao ngay
    if prev_rank >= HEALTH_RANK["CRITICAL"] and cur_rank == HEALTH_RANK["SAFE"]:
        return True  # vua duoc giai cuu thanh cong -> bao tin tot
    return False


def estimate_ib_revenue(total_lots: float, rate: float = None) -> float:
    rate = rate if rate is not None else settings.IB_RATE_USD_PER_LOT
    return round(total_lots * rate, 2)


def license_alert_tier(days_remaining: int):
    """Tra ve moc canh bao license gan nhat ma days_remaining cham toi (hoac None)."""
    for tier in sorted(settings.LICENSE_WARNING_DAYS, reverse=True):
        if days_remaining == tier:
            return tier
    return None
