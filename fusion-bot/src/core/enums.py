"""
Enums for FusionBot
===================

Type-safe enumerations for all domain concepts.
"""

from enum import Enum, auto


class TradeAction(str, Enum):
    """Action decision from the Fusion Brain."""
    
    BUY = "BUY"
    WAIT = "WAIT"
    SELL = "SELL"  # For future short support
    
    def __str__(self) -> str:
        return self.value


class TradeStatus(str, Enum):
    """Lifecycle status of a trade."""
    
    PENDING = "PENDING"      # Order placed, awaiting fill
    OPEN = "OPEN"            # Position is active
    CLOSING = "CLOSING"      # Exit order placed, awaiting fill
    CLOSED = "CLOSED"        # Position fully closed
    CANCELLED = "CANCELLED"  # Order cancelled before fill
    FAILED = "FAILED"        # Order failed to execute
    
    def __str__(self) -> str:
        return self.value


class TradeSide(str, Enum):
    """Side of the trade."""
    
    BUY = "BUY"
    SELL = "SELL"
    
    def __str__(self) -> str:
        return self.value


class ExitReason(str, Enum):
    """Reason for closing a position."""
    
    VIRTUAL_SL = "VIRTUAL_SL"           # Virtual stop loss hit
    VIRTUAL_TP = "VIRTUAL_TP"           # Virtual take profit hit
    CATASTROPHE_SL = "CATASTROPHE_SL"   # Exchange stop loss hit (disaster)
    TIME_DECAY = "TIME_DECAY"           # Zombie trade force closed
    MANUAL = "MANUAL"                   # User manually closed
    SIGNAL = "SIGNAL"                   # Opposite signal received
    DEFENSIVE_MODE = "DEFENSIVE_MODE"   # Closed due to macro risk
    SYNC_MISSING = "SYNC_MISSING"       # Position not found on exchange
    
    def __str__(self) -> str:
        return self.value


class MarketRegime(str, Enum):
    """Current market regime classification."""
    
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNKNOWN = "UNKNOWN"
    
    def __str__(self) -> str:
        return self.value


class TrendDirection(str, Enum):
    """Trend direction from technical analysis."""
    
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    
    def __str__(self) -> str:
        return self.value


class SystemMode(str, Enum):
    """Operating mode of the trading system."""
    
    ACTIVE = "ACTIVE"              # Normal operation, seeking trades
    DEFENSIVE = "DEFENSIVE"         # Macro risk detected, managing existing only
    MAINTENANCE = "MAINTENANCE"     # System under maintenance
    SHUTDOWN = "SHUTDOWN"           # Graceful shutdown in progress
    
    def __str__(self) -> str:
        return self.value


class NewsStatus(str, Enum):
    """
    Accurate status tracking for news items.
    
    Reflects what ACTUALLY happened to each news item,
    not a generic "WAIT" that hides the real reason.
    """
    
    # === Trade Executed ===
    SELECTED = "SELECTED"               # AI chose this headline, trade executed
    
    # === AI Decision (Batch) ===
    COMPARED_OUT = "COMPARED_OUT"       # Evaluated by AI, but better option existed in batch
    AI_WAIT = "AI_WAIT"                 # AI evaluated entire batch, said WAIT for all
    
    # === Pre-AI Rejections (Code) ===
    HARD_LIMIT_RSI = "HARD_LIMIT_RSI"   # Failed RSI hard limit check
    HARD_LIMIT_AGE = "HARD_LIMIT_AGE"   # News too old
    HARD_LIMIT_OTHER = "HARD_LIMIT"     # Other hard limit failure
    
    # === Filtering Rejections ===
    NO_SYMBOL = "NO_SYMBOL"             # Couldn't detect tradeable symbol
    NOT_IN_WATCHLIST = "NOT_WATCHLIST"  # Symbol not in configured watchlist
    DUPLICATE = "DUPLICATE"             # Already processed this news
    POSITION_EXISTS = "POS_EXISTS"      # Already have position in this symbol
    
    # === Post-AI Rejections (Code Veto) ===
    VETO_CONFIDENCE = "VETO_CONFIDENCE" # AI confidence too low
    VETO_INCONSISTENT = "VETO_INCON"    # AI logic inconsistent (noise + BUY)
    
    # === System States ===
    DEFENSIVE_MODE = "DEFENSIVE"        # System in defensive mode, no new trades
    COOLDOWN = "COOLDOWN"               # Trade cooldown active
    POSITION_LIMIT = "POS_LIMIT"        # Max positions reached
    EXECUTION_FAILED = "EXEC_FAILED"    # Trade execution failed
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def is_rejection(cls, status: "NewsStatus") -> bool:
        """Check if this status represents a rejection."""
        rejections = {
            cls.HARD_LIMIT_RSI, cls.HARD_LIMIT_AGE, cls.HARD_LIMIT_OTHER,
            cls.NO_SYMBOL, cls.NOT_IN_WATCHLIST, cls.DUPLICATE, cls.POSITION_EXISTS,
            cls.VETO_CONFIDENCE, cls.VETO_INCONSISTENT, cls.EXECUTION_FAILED,
        }
        return status in rejections
    
    @classmethod
    def is_ai_decision(cls, status: "NewsStatus") -> bool:
        """Check if this status came from AI decision."""
        return status in {cls.SELECTED, cls.COMPARED_OUT, cls.AI_WAIT}


class RSIZone(str, Enum):
    """RSI classification zones."""
    
    OVERSOLD = "OVERSOLD"       # RSI < 30
    NEUTRAL = "NEUTRAL"         # 30 <= RSI <= 70
    OVERBOUGHT = "OVERBOUGHT"   # RSI > 70
    
    def __str__(self) -> str:
        return self.value


class MACDSignal(str, Enum):
    """MACD signal classification."""
    
    BULLISH_CROSS = "BULLISH_CROSS"   # MACD crossed above signal
    BEARISH_CROSS = "BEARISH_CROSS"   # MACD crossed below signal
    BULLISH = "BULLISH"               # MACD above signal
    BEARISH = "BEARISH"               # MACD below signal
    
    def __str__(self) -> str:
        return self.value

