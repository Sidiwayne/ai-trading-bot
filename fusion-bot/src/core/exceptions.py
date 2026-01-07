"""
Custom Exceptions for FusionBot
===============================

Hierarchical exception structure for precise error handling.
"""


class FusionBotError(Exception):
    """Base exception for all FusionBot errors."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ============================================
# Configuration Errors
# ============================================

class ConfigurationError(FusionBotError):
    """Raised when configuration is invalid or missing."""
    pass


# ============================================
# Exchange Errors
# ============================================

class ExchangeError(FusionBotError):
    """Base exception for exchange-related errors."""
    pass


class InsufficientBalanceError(ExchangeError):
    """Raised when account balance is too low for trade."""
    
    def __init__(self, required: float, available: float, currency: str):
        super().__init__(
            f"Insufficient {currency} balance",
            {"required": required, "available": available, "currency": currency}
        )
        self.required = required
        self.available = available
        self.currency = currency


class OrderExecutionError(ExchangeError):
    """Raised when order fails to execute."""
    
    def __init__(self, message: str, order_id: str = None, symbol: str = None):
        super().__init__(message, {"order_id": order_id, "symbol": symbol})
        self.order_id = order_id
        self.symbol = symbol


class RateLimitError(ExchangeError):
    """Raised when API rate limit is hit."""
    
    def __init__(self, retry_after: int = None):
        super().__init__(
            "API rate limit exceeded",
            {"retry_after_seconds": retry_after}
        )
        self.retry_after = retry_after


class ExchangeConnectionError(ExchangeError):
    """Raised when connection to exchange fails."""
    pass


# ============================================
# News Errors
# ============================================

class NewsParsingError(FusionBotError):
    """Raised when RSS feed parsing fails."""
    
    def __init__(self, source: str, reason: str):
        super().__init__(
            f"Failed to parse news from {source}",
            {"source": source, "reason": reason}
        )
        self.source = source
        self.reason = reason


# ============================================
# AI Errors
# ============================================

class AIAnalysisError(FusionBotError):
    """Raised when AI analysis fails."""
    
    def __init__(self, message: str, prompt: str = None):
        super().__init__(message, {"prompt_length": len(prompt) if prompt else 0})
        self.prompt = prompt


class AIRateLimitError(AIAnalysisError):
    """Raised when AI API rate limit is hit."""
    pass


class AIResponseParsingError(AIAnalysisError):
    """Raised when AI response cannot be parsed."""
    pass


# ============================================
# Database Errors
# ============================================

class DatabaseError(FusionBotError):
    """Raised when database operation fails."""
    pass


class RecordNotFoundError(DatabaseError):
    """Raised when expected record is not found."""
    
    def __init__(self, table: str, identifier: str):
        super().__init__(
            f"Record not found in {table}",
            {"table": table, "identifier": identifier}
        )
        self.table = table
        self.identifier = identifier


class DuplicateRecordError(DatabaseError):
    """Raised when attempting to insert duplicate record."""
    pass


# ============================================
# Trading Logic Errors
# ============================================

class TradingError(FusionBotError):
    """Base exception for trading logic errors."""
    pass


class PositionLimitError(TradingError):
    """Raised when max open positions limit reached."""
    
    def __init__(self, current: int, maximum: int, message: str = "Maximum open positions reached"):
        super().__init__(
            message,
            {"current": current, "maximum": maximum}
        )
        self.current = current
        self.maximum = maximum


class DefensiveModeError(TradingError):
    """Raised when trade rejected due to defensive mode."""
    
    def __init__(self, reason: str, until: str = None):
        super().__init__(
            f"Defensive mode active: {reason}",
            {"reason": reason, "until": until}
        )
        self.reason = reason
        self.until = until


class ChasePreventionError(TradingError):
    """Raised when trade rejected due to price already moved."""
    
    def __init__(self, price_move_pct: float, max_allowed_pct: float):
        super().__init__(
            f"Price moved too much since news",
            {"price_move_pct": price_move_pct, "max_allowed_pct": max_allowed_pct}
        )
        self.price_move_pct = price_move_pct
        self.max_allowed_pct = max_allowed_pct

