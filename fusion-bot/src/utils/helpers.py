"""
Helper Utilities for FusionBot
==============================

Common utility functions used across the application.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional, List
import re


def generate_news_id(title: str, source: str) -> str:
    """
    Generate a unique ID for a news item.
    
    Args:
        title: News headline
        source: RSS feed source
    
    Returns:
        SHA256 hash of normalized title + source
    """
    # Normalize: lowercase, remove extra whitespace
    normalized = f"{title.lower().strip()}|{source.lower().strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def extract_symbol_from_text(text: str, supported_symbols: dict) -> Optional[str]:
    """
    Extract trading symbol from news headline.
    
    Args:
        text: News headline or body
        supported_symbols: Dict mapping symbols to their keywords
    
    Returns:
        Trading symbol if found, None otherwise
    
    Example:
        >>> supported = {"BTC/USDC": ["bitcoin", "btc"]}
        >>> extract_symbol_from_text("Bitcoin hits new high", supported)
        "BTC/USDC"
    """
    text_lower = text.lower()
    
    for symbol, keywords in supported_symbols.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return symbol
    
    return None


def parse_rss_date(date_string: str) -> Optional[datetime]:
    """
    Parse various RSS date formats to datetime.
    
    Args:
        date_string: Date string from RSS feed
    
    Returns:
        datetime object or None if parsing fails
    """
    if not date_string:
        return None
    
    # Common RSS date formats
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",      # RFC 822
        "%a, %d %b %Y %H:%M:%S %Z",      # RFC 822 with timezone name
        "%Y-%m-%dT%H:%M:%S%z",           # ISO 8601
        "%Y-%m-%dT%H:%M:%SZ",            # ISO 8601 UTC
        "%Y-%m-%d %H:%M:%S",             # Simple datetime
        "%Y-%m-%d",                       # Date only
    ]
    
    # Clean up the date string
    date_string = date_string.strip()
    
    # Handle timezone abbreviations
    date_string = re.sub(r'\s+(GMT|UTC|EST|PST|EDT|PDT)\s*$', '', date_string)
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            # Ensure timezone aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    
    return None


def calculate_position_size(
    account_balance: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss_price: float,
    max_position_pct: float = 0.30,
    fee_rate: float = 0.001,
) -> float:
    """
    Calculate position size based on risk management with safety caps.
    
    Uses Kelly-style position sizing (risk-based) but caps at max % of balance
    and accounts for trading fees.
    
    Args:
        account_balance: Total account balance in quote currency
        risk_per_trade: Risk per trade as decimal (0.02 = 2%)
        entry_price: Expected entry price
        stop_loss_price: Stop loss price
        max_position_pct: Maximum position as % of balance (0.30 = 30%)
        fee_rate: Trading fee rate (0.001 = 0.1%)
    
    Returns:
        Position size in base currency
    
    Example:
        >>> calculate_position_size(10000, 0.02, 50000, 49000, 0.30, 0.001)
        0.06  # Capped at 30% of $10k = $3000 worth
    """
    risk_per_unit = abs(entry_price - stop_loss_price)
    
    if risk_per_unit <= 0 or entry_price <= 0:
        return 0
    
    # Kelly-style: position sized so loss at SL = risk_amount
    risk_amount = account_balance * risk_per_trade
    kelly_quantity = risk_amount / risk_per_unit
    
    # Cap: max position as % of balance (accounting for fees)
    max_spend = account_balance * max_position_pct / (1 + fee_rate)
    max_quantity = max_spend / entry_price
    
    # Take the smaller of Kelly and cap
    final_quantity = min(kelly_quantity, max_quantity)
    
    return final_quantity


def format_price(price: float, decimals: int = 2) -> str:
    """
    Format price with appropriate decimal places.
    
    Args:
        price: Price value
        decimals: Number of decimal places
    
    Returns:
        Formatted price string
    """
    if price >= 1000:
        return f"{price:,.{decimals}f}"
    elif price >= 1:
        return f"{price:.{decimals}f}"
    else:
        # For small prices, show more decimals
        return f"{price:.6f}"


def format_percent(value: float, include_sign: bool = True) -> str:
    """
    Format percentage value.
    
    Args:
        value: Decimal value (0.05 = 5%)
        include_sign: Include + sign for positive values
    
    Returns:
        Formatted percentage string
    """
    pct = value * 100
    if include_sign and pct > 0:
        return f"+{pct:.2f}%"
    return f"{pct:.2f}%"


def truncate_string(text: str, max_length: int = 100) -> str:
    """
    Truncate string with ellipsis.
    
    Args:
        text: Input string
        max_length: Maximum length including ellipsis
    
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def is_market_hours() -> bool:
    """
    Check if it's currently within crypto market hours.
    
    Note: Crypto markets are 24/7, but this can be used
    to avoid trading during low-liquidity periods.
    
    Returns:
        True (crypto is always open)
    """
    return True


def get_timeframe_minutes(timeframe: str) -> int:
    """
    Convert timeframe string to minutes.
    
    Args:
        timeframe: Timeframe string (1m, 5m, 1h, 4h, 1d)
    
    Returns:
        Number of minutes
    """
    multipliers = {
        'm': 1,
        'h': 60,
        'd': 1440,
        'w': 10080,
    }
    
    match = re.match(r'^(\d+)([mhdw])$', timeframe.lower())
    if not match:
        raise ValueError(f"Invalid timeframe: {timeframe}")
    
    value = int(match.group(1))
    unit = match.group(2)
    
    return value * multipliers[unit]

