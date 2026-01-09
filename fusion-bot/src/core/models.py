"""
Domain Models for FusionBot
============================

Pure Python dataclasses representing core domain concepts.
These are NOT ORM models - they are domain objects.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from src.core.enums import (
    TradeAction,
    TradeStatus,
    TradeSide,
    ExitReason,
    TrendDirection,
    RSIZone,
    MACDSignal,
)


@dataclass
class NewsItem:
    """
    Represents a news article from RSS feed.
    
    Attributes:
        id: Unique identifier (hash of title + source)
        title: Article headline
        source: RSS feed source name
        url: Link to full article
        published_at: When the article was published
        detected_symbol: Trading symbol detected in headline (e.g., "BTC/USDC")
        summary: Brief summary if available
    """
    
    id: str
    title: str
    source: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    detected_symbol: Optional[str] = None
    summary: Optional[str] = None
    
    def __post_init__(self):
        """Normalize title."""
        self.title = self.title.strip() if self.title else ""
    
    @property
    def age_seconds(self) -> Optional[float]:
        """Get age of news item in seconds."""
        if self.published_at:
            return (datetime.utcnow() - self.published_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "detected_symbol": self.detected_symbol,
        }


@dataclass
class TechnicalSignals:
    """
    Technical analysis signals computed from OHLCV data.
    
    Attributes:
        symbol: Trading pair
        timeframe: Candle timeframe (e.g., "4h")
        current_price: Latest close price
        rsi: Relative Strength Index (0-100)
        rsi_zone: Classification (OVERSOLD, NEUTRAL, OVERBOUGHT)
        ema_short: Short-term EMA value
        ema_long: Long-term EMA value
        trend: Trend direction based on EMAs
        macd: MACD line value
        macd_signal: Signal line value
        macd_histogram: Histogram value
        macd_indication: MACD signal classification
        atr: Average True Range (volatility)
        atr_percent: ATR as percentage of price
        computed_at: When signals were computed
    """
    
    symbol: str
    timeframe: str
    current_price: float
    
    # RSI
    rsi: float
    rsi_zone: RSIZone
    
    # EMAs
    ema_short: float
    ema_long: float
    trend: TrendDirection
    
    # MACD
    macd: float
    macd_signal: float
    macd_histogram: float
    macd_indication: MACDSignal
    
    # Volatility
    atr: float
    atr_percent: float
    
    computed_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_overbought(self) -> bool:
        """Check if RSI indicates overbought condition."""
        return self.rsi_zone == RSIZone.OVERBOUGHT
    
    @property
    def is_oversold(self) -> bool:
        """Check if RSI indicates oversold condition."""
        return self.rsi_zone == RSIZone.OVERSOLD
    
    @property
    def is_bullish(self) -> bool:
        """Check if overall technicals are bullish."""
        return (
            self.trend == TrendDirection.BULLISH
            and self.macd_indication in (MACDSignal.BULLISH, MACDSignal.BULLISH_CROSS)
            and not self.is_overbought
        )
    
    @property
    def is_bearish(self) -> bool:
        """Check if overall technicals are bearish."""
        return (
            self.trend == TrendDirection.BEARISH
            or self.macd_indication in (MACDSignal.BEARISH, MACDSignal.BEARISH_CROSS)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for AI prompt."""
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "rsi": round(self.rsi, 2),
            "rsi_zone": str(self.rsi_zone),
            "trend": str(self.trend),
            "ema_short": round(self.ema_short, 2),
            "ema_long": round(self.ema_long, 2),
            "macd": round(self.macd, 4),
            "macd_signal": round(self.macd_signal, 4),
            "macd_histogram": round(self.macd_histogram, 4),
            "macd_indication": str(self.macd_indication),
            "atr_percent": round(self.atr_percent, 4),
        }


@dataclass
class FusionDecision:
    """
    Decision output from the Fusion Brain (AI analysis).
    
    Attributes:
        action: BUY, WAIT, or SELL
        confidence: Confidence score (0-100)
        reasoning: AI's explanation for the decision
        news_item: The news that triggered analysis
        technicals: Technical signals at decision time
        rejection_reason: If WAIT, why was it rejected
        decided_at: When the decision was made
    """
    
    action: TradeAction
    confidence: int
    reasoning: str
    news_item: NewsItem
    technicals: TechnicalSignals
    rejection_reason: Optional[str] = None
    decided_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def should_execute(self) -> bool:
        """Check if decision should be executed (BUY with high confidence)."""
        return self.action == TradeAction.BUY and self.confidence >= 70
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "action": str(self.action),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "rejection_reason": self.rejection_reason,
            "news": self.news_item.to_dict(),
            "technicals": self.technicals.to_dict(),
            "decided_at": self.decided_at.isoformat(),
        }


@dataclass
class TradeEntry:
    """
    Parameters for entering a new trade.
    
    Attributes:
        symbol: Trading pair to trade
        side: BUY or SELL
        quantity: Amount to trade
        entry_price: Expected entry price
        virtual_sl: Virtual stop loss price
        virtual_tp: Virtual take profit price
        catastrophe_sl: Exchange-enforced stop loss price
        news_id: ID of news that triggered trade
        decision: The AI decision that led to this trade
    """
    
    symbol: str
    side: TradeSide
    quantity: float
    entry_price: float
    virtual_sl: float
    virtual_tp: float
    catastrophe_sl: float
    news_id: str
    decision: FusionDecision
    
    @property
    def virtual_sl_pct(self) -> float:
        """Get virtual SL as percentage from entry."""
        return (self.virtual_sl - self.entry_price) / self.entry_price
    
    @property
    def virtual_tp_pct(self) -> float:
        """Get virtual TP as percentage from entry."""
        return (self.virtual_tp - self.entry_price) / self.entry_price
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio."""
        risk = abs(self.entry_price - self.virtual_sl)
        reward = abs(self.virtual_tp - self.entry_price)
        return reward / risk if risk > 0 else 0


@dataclass
class Position:
    """
    An active trading position.
    
    Attributes:
        id: Database ID
        symbol: Trading pair
        side: BUY or SELL
        entry_price: Actual fill price
        quantity: Position size
        virtual_sl: Virtual stop loss price
        virtual_tp: Virtual take profit price
        catastrophe_sl: Exchange stop loss price
        exchange_stop_order_id: ID of stop order on exchange
        status: Current position status
        opened_at: When position was opened
        news_id: ID of triggering news
        reasoning: AI reasoning for the trade
    """
    
    id: int
    symbol: str
    side: TradeSide
    entry_price: float
    quantity: float
    virtual_sl: float
    virtual_tp: float
    catastrophe_sl: float
    exchange_stop_order_id: Optional[str]
    status: TradeStatus
    opened_at: datetime
    news_id: Optional[str] = None
    reasoning: Optional[str] = None
    
    # Exit fields (populated when closed)
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    closed_at: Optional[datetime] = None
    pnl_amount: Optional[float] = None
    pnl_percent: Optional[float] = None
    
    @property
    def is_open(self) -> bool:
        """Check if position is still open."""
        return self.status in (TradeStatus.PENDING, TradeStatus.OPEN)
    
    @property
    def age_hours(self) -> float:
        """Get position age in hours."""
        delta = datetime.utcnow() - self.opened_at
        return delta.total_seconds() / 3600
    
    def check_virtual_sl(self, current_price: float) -> bool:
        """Check if virtual stop loss is hit."""
        if self.side == TradeSide.BUY:
            return current_price <= self.virtual_sl
        else:
            return current_price >= self.virtual_sl
    
    def check_virtual_tp(self, current_price: float) -> bool:
        """Check if virtual take profit is hit."""
        if self.side == TradeSide.BUY:
            return current_price >= self.virtual_tp
        else:
            return current_price <= self.virtual_tp
    
    def calculate_pnl(self, exit_price: float) -> tuple[float, float]:
        """
        Calculate P&L for given exit price.
        
        Returns:
            Tuple of (pnl_amount, pnl_percent)
        """
        if self.side == TradeSide.BUY:
            pnl_amount = (exit_price - self.entry_price) * self.quantity
        else:
            pnl_amount = (self.entry_price - exit_price) * self.quantity
        
        pnl_percent = pnl_amount / (self.entry_price * self.quantity)
        return pnl_amount, pnl_percent
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": str(self.side),
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "virtual_sl": self.virtual_sl,
            "virtual_tp": self.virtual_tp,
            "status": str(self.status),
            "age_hours": round(self.age_hours, 2),
            "pnl_percent": self.pnl_percent,
        }

