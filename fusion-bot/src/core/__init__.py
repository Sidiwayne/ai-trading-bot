"""Core domain module for FusionBot."""

from src.core.enums import (
    TradeAction,
    TradeStatus,
    TradeSide,
    ExitReason,
    MarketRegime,
    TrendDirection,
    SystemMode,
)
from src.core.models import (
    NewsItem,
    TechnicalSignals,
    FusionDecision,
    TradeEntry,
    Position,
)
from src.core.exceptions import (
    FusionBotError,
    ConfigurationError,
    ExchangeError,
    InsufficientBalanceError,
    OrderExecutionError,
    RateLimitError,
    NewsParsingError,
    AIAnalysisError,
    DatabaseError,
)

__all__ = [
    # Enums
    "TradeAction",
    "TradeStatus",
    "TradeSide",
    "ExitReason",
    "MarketRegime",
    "TrendDirection",
    "SystemMode",
    # Models
    "NewsItem",
    "TechnicalSignals",
    "FusionDecision",
    "TradeEntry",
    "Position",
    # Exceptions
    "FusionBotError",
    "ConfigurationError",
    "ExchangeError",
    "InsufficientBalanceError",
    "OrderExecutionError",
    "RateLimitError",
    "NewsParsingError",
    "AIAnalysisError",
    "DatabaseError",
]

