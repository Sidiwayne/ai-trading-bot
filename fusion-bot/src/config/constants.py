"""
Constants for FusionBot
=======================

Static configuration values that don't change at runtime.
"""

from typing import Dict, List

# ============================================
# RSS FEEDS - Crypto News Sources
# ============================================

RSS_FEEDS: Dict[str, str] = {
    "cointelegraph": "https://cointelegraph.com/rss",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "bitcoin_magazine": "https://bitcoinmagazine.com/.rss/full/",
    "decrypt": "https://decrypt.co/feed",
}

# ============================================
# MACRO RSS FEEDS - Financial News for Risk Detection
# ============================================

MACRO_RSS_FEEDS: Dict[str, str] = {
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    # Reuters feed is broken (404), using MarketWatch instead
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "cnbc": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
}

# ============================================
# DANGER KEYWORDS - Trigger Defensive Mode
# ============================================

DANGER_KEYWORDS: List[str] = [
    # Federal Reserve
    "fed",
    "federal reserve",
    "fomc",
    "powell",
    "interest rate",
    "rate hike",
    "rate cut",
    "hawkish",
    "dovish",
    "quantitative tightening",
    "qt",
    "quantitative easing",
    "qe",
    
    # Economic Indicators
    "cpi",
    "inflation",
    "ppi",
    "unemployment",
    "nonfarm payroll",
    "gdp",
    "recession",
    "stagflation",
    
    # Geopolitical
    "war",
    "conflict",
    "sanction",
    "tariff",
    "trade war",
    
    # Market Events
    "crash",
    "correction",
    "bear market",
    "capitulation",
    "liquidation",
    "black swan",
    
    # Crypto Specific
    "sec lawsuit",
    "exchange hack",
    "rug pull",
    "ponzi",
    "insolvency",
    "bankruptcy",
]

# ============================================
# SUPPORTED SYMBOLS - Trading Pairs
# ============================================

SUPPORTED_SYMBOLS: Dict[str, List[str]] = {
    "BTC/USDT": ["bitcoin", "btc", "₿"],
    "ETH/USDT": ["ethereum", "eth", "ether"],
    "SOL/USDT": ["solana", "sol"],
    "SOL/USDT": ["solana", "sol"],
    "XRP/USDT": ["ripple", "xrp"],
    "ADA/USDT": ["cardano", "ada"],
    "AVAX/USDT": ["avalanche", "avax"],
    "DOT/USDT": ["polkadot", "dot"],
    "LINK/USDT": ["chainlink", "link"],
    "MATIC/USDT": ["polygon", "matic"],
    "ATOM/USDT": ["cosmos", "atom"],
}

# ============================================
# TECHNICAL ANALYSIS PARAMETERS
# ============================================

TA_PARAMS = {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "ema_short": 20,
    "ema_long": 50,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "atr_period": 14,
    "candle_timeframe": "4h",
    "candles_to_fetch": 100,
}

# ============================================
# API RATE LIMITS
# ============================================

RATE_LIMITS = {
    "binance_requests_per_minute": 1200,
    "binance_orders_per_second": 10,
    "gemini_requests_per_minute": 60,
    "rss_min_interval_seconds": 60,
}

# ============================================
# RETRY CONFIGURATION
# ============================================

RETRY_CONFIG = {
    "max_attempts": 3,
    "initial_delay_seconds": 1,
    "max_delay_seconds": 30,
    "exponential_base": 2,
}

# ============================================
# HEALTH CHECK THRESHOLDS
# ============================================

HEALTH_THRESHOLDS = {
    "max_api_latency_ms": 5000,
    "max_heartbeat_age_seconds": 30,
    "min_account_balance_usdt": 10,
}

