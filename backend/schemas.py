from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class ReportIn(BaseModel):
    """Payload ma EA (ReportModule.mqh) gui len qua WebRequest."""
    api_key: str
    login: str
    server: str
    symbol: str = "XAUUSD"
    preset: str = "Master Alpha"
    is_cent: bool = False

    balance: float
    equity: float
    margin_level: float = 0.0
    floating_pl: float = 0.0
    drawdown_pct: float = 0.0

    total_orders: int = 0
    buy_orders: int = 0
    sell_orders: int = 0
    total_lots: float = 0.0
    closed_lots_today: float = 0.0

    loop_active: bool = True
    hedge_active: bool = False
    ai_confidence: float = 0.0
    zone_points: float = 0.0
    tp_points: float = 0.0
    multiplier: float = 0.0
    max_orders: int = 0

    health_status: Optional[str] = None  # neu EA tu tinh; server se tinh lai de chac chan dong nhat
    license_expiry: Optional[date] = None
    timestamp: Optional[datetime] = None
