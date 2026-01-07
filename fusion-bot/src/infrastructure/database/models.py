"""
SQLAlchemy ORM Models for FusionBot
===================================

Database table definitions for PostgreSQL.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SeenNewsORM(Base):
    """
    Tracks processed news items for deduplication.
    
    Once a news item is processed, it's stored here
    to prevent re-processing the same headline.
    """
    
    __tablename__ = "seen_news"
    
    id = Column(String(32), primary_key=True)  # Hash of title + source
    title = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)
    url = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    detected_symbol = Column(String(20), nullable=True)
    action_taken = Column(String(20), nullable=True)  # BUY, WAIT, REJECTED
    rejection_reason = Column(Text, nullable=True)
    
    # Relationship to trades
    trades = relationship("TradeORM", back_populates="news")
    
    __table_args__ = (
        Index("idx_seen_news_processed_at", "processed_at"),
        Index("idx_seen_news_source", "source"),
    )
    
    def __repr__(self) -> str:
        return f"<SeenNews(id={self.id[:8]}, title={self.title[:50]}...)>"


class TradeORM(Base):
    """
    Stores all trades (active and historical).
    
    This is the trade ledger - complete record of all
    trading activity with entry, exit, and P&L.
    """
    
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Trade Identity
    symbol = Column(String(20), nullable=False)  # BTC/USDT
    side = Column(String(10), nullable=False)    # BUY, SELL
    
    # Entry Details
    entry_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    entry_order_id = Column(String(100), nullable=True)
    
    # Virtual Targets (managed by bot)
    virtual_sl_price = Column(Float, nullable=False)   # -2% from entry
    virtual_tp_price = Column(Float, nullable=False)   # +4% from entry
    
    # Catastrophe Stop (managed by exchange)
    exchange_stop_order_id = Column(String(100), nullable=True)
    catastrophe_sl_price = Column(Float, nullable=False)  # -10% from entry
    
    # Lifecycle
    status = Column(String(20), default="OPEN", nullable=False)
    exit_price = Column(Float, nullable=True)
    exit_order_id = Column(String(100), nullable=True)
    exit_reason = Column(String(50), nullable=True)
    
    # Performance
    pnl_amount = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    
    # Audit Trail
    news_id = Column(String(32), ForeignKey("seen_news.id"), nullable=True)
    gemini_reasoning = Column(Text, nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationship
    news = relationship("SeenNewsORM", back_populates="trades")
    
    __table_args__ = (
        Index("idx_trades_status", "status"),
        Index("idx_trades_opened_at", "opened_at"),
        Index("idx_trades_symbol", "symbol"),
    )
    
    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, symbol={self.symbol}, status={self.status})>"


class MacroEventORM(Base):
    """
    Logs macro events that trigger defensive mode.
    
    Tracks dangerous headlines from financial news
    that caused the bot to pause trading.
    """
    
    __tablename__ = "macro_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(100), nullable=False)
    headline = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)
    severity = Column(String(20), default="WARNING", nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    defensive_mode_until = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("idx_macro_events_detected_at", "detected_at"),
    )
    
    def __repr__(self) -> str:
        return f"<MacroEvent(id={self.id}, keyword={self.keyword})>"


class SystemStateORM(Base):
    """
    Key-value store for system state.
    
    Used for crash recovery and persistent state
    that needs to survive restarts.
    """
    
    __tablename__ = "system_state"
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<SystemState(key={self.key})>"


class DailyPerformanceORM(Base):
    """
    Aggregated daily performance metrics.
    
    Rolled up statistics for analysis and reporting.
    """
    
    __tablename__ = "daily_performance"
    
    date = Column(String(10), primary_key=True)  # YYYY-MM-DD
    trades_opened = Column(Integer, default=0)
    trades_closed = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    total_pnl_percent = Column(Float, default=0.0)
    max_drawdown_percent = Column(Float, default=0.0)
    news_processed = Column(Integer, default=0)
    defensive_mode_hours = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<DailyPerformance(date={self.date}, pnl={self.total_pnl_percent:.2%})>"

