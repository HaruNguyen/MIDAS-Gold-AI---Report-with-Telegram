from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from .database import Base


class Account(Base):
    """Mot tai khoan MT5 dang chay bot MIDAS Gold AI EA."""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, index=True, nullable=False)   # Trading ID (MT5 login)
    server = Column(String, nullable=False)                          # Broker server
    symbol = Column(String, default="XAUUSD")
    preset = Column(String, default="Master Alpha")                  # Master Alpha | Master Elite | custom
    is_cent = Column(Boolean, default=False)
    owner_label = Column(String, default="")                         # ten/khach hang gan voi tai khoan (tuy chon)
    license_expiry = Column(Date, nullable=True)                      # ngay het han thue bot (~$600/nam)
    last_health_status = Column(String, default="SAFE")               # trang thai gan nhat, dung de chong spam alert
    created_at = Column(DateTime, default=datetime.utcnow)

    snapshots = relationship("Snapshot", back_populates="account", cascade="all, delete-orphan")


class Snapshot(Base):
    """Mot lan EA bao cao trang thai tai khoan ve server."""
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)

    balance = Column(Float)
    equity = Column(Float)
    margin_level = Column(Float)
    floating_pl = Column(Float)
    drawdown_pct = Column(Float)

    total_orders = Column(Integer)
    buy_orders = Column(Integer)
    sell_orders = Column(Integer)
    total_lots = Column(Float)
    closed_lots_today = Column(Float)

    loop_active = Column(Boolean)
    hedge_active = Column(Boolean)
    ai_confidence = Column(Float)
    zone_points = Column(Float)
    tp_points = Column(Float)
    multiplier = Column(Float)
    max_orders = Column(Integer)

    health_status = Column(String)  # SAFE | WATCH | CRITICAL | HEDGE_LOCKED
    reported_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="snapshots")
