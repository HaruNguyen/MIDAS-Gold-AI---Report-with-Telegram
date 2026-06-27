"""
Cau hinh trung tam cho Report Server.
Tat ca gia tri nhay cam doc tu bien moi truong (.env) — khong hardcode trong code.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Bao mat ---
    API_KEY: str = os.getenv("REPORT_API_KEY", "CHANGE_ME_SECRET_KEY")

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")  # chat/group nhan bao cao (chu bot)

    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./midas_report.db")

    # --- Nguong "suc khoe bo lenh" (theo tai lieu van hanh EA) ---
    ORDERS_WATCH_THRESHOLD: int = int(os.getenv("ORDERS_WATCH_THRESHOLD", 15))     # AI bat dau can thiep nang lot
    ORDERS_CRITICAL_THRESHOLD: int = int(os.getenv("ORDERS_CRITICAL_THRESHOLD", 26))  # gan nguong Hedge (26-30)
    DRAWDOWN_WARNING_PCT: float = float(os.getenv("DRAWDOWN_WARNING_PCT", 15.0))
    DRAWDOWN_CRITICAL_PCT: float = float(os.getenv("DRAWDOWN_CRITICAL_PCT", 30.0))
    MARGIN_LEVEL_WARNING: float = float(os.getenv("MARGIN_LEVEL_WARNING", 200.0))  # %

    # --- Hoa hong IB (de uoc tinh doanh thu) ---
    IB_RATE_USD_PER_LOT: float = float(os.getenv("IB_RATE_USD_PER_LOT", 5.0))

    # --- License / thue bot ---
    LICENSE_WARNING_DAYS = [30, 14, 7, 1]  # cac moc canh bao truoc khi het han

    # --- Digest dinh ky ---
    DAILY_DIGEST_HOUR: int = int(os.getenv("DAILY_DIGEST_HOUR", 8))   # 08:00 hang ngay (gio server)
    DAILY_DIGEST_MINUTE: int = int(os.getenv("DAILY_DIGEST_MINUTE", 0))


settings = Settings()
