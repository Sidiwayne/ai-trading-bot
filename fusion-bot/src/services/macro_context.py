"""
Macro Context Service for FusionBot
====================================

Gathers macro-economic headlines as CONTEXT for AI decision making.
Does NOT block trades - provides information for AI to weigh.

Philosophy:
- Macro news = context, not automatic blocks
- AI sees the full picture (macro + crypto + technicals)
- Only TRUE CATASTROPHES trigger code-level blocks
- "Fed rate cut" is bullish, not a reason to stop trading

Replaces the old binary MacroGuard approach.
"""

import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple
from dataclasses import dataclass

from src.infrastructure.clients.rss_client import RSSClient
from src.infrastructure.database import get_session
from src.infrastructure.database.repositories import MacroEventRepository
from src.config import get_settings
from src.config.constants import MACRO_RSS_FEEDS
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════════
# CATASTROPHE KEYWORDS - Only these trigger CODE-LEVEL blocks
# These are rare, obvious disasters where trading is truly dangerous
# ════════════════════════════════════════════════════════════════════════════════

CATASTROPHE_KEYWORDS = [
    "market crash",
    "flash crash",
    "circuit breaker",
    "trading halted",
    "exchange hack",
    "exchange hacked",
    "black swan",
    "systemic collapse",
    "bank run",
    "lehman",
    "insolvency",
]


# ════════════════════════════════════════════════════════════════════════════════
# MACRO CONTEXT KEYWORDS - These are gathered as context for AI
# NOT automatic blocks - AI will weigh them appropriately
# ════════════════════════════════════════════════════════════════════════════════

MACRO_CONTEXT_KEYWORDS = [
    # Fed / Central Banks (can be bullish OR bearish)
    "fed", "federal reserve", "fomc", "powell", "interest rate",
    "rate hike", "rate cut", "hawkish", "dovish",
    "quantitative tightening", "quantitative easing",
    
    # Economic Indicators (context-dependent)
    "cpi", "inflation", "ppi", "unemployment", "nonfarm payroll",
    "gdp", "recession", "stagflation", "jobs report",
    
    # Geopolitical (severity varies)
    "war", "conflict", "sanction", "tariff", "trade war",
    
    # Market Events (severity varies)
    "correction", "bear market", "sell-off", "volatility",
    "liquidation", "capitulation",
]


@dataclass
class MacroHeadline:
    """A macro-economic headline with metadata."""
    title: str
    source: str
    published_at: Optional[datetime]
    matched_keywords: List[str]
    
    def __str__(self) -> str:
        age = "unknown"
        if self.published_at:
            minutes = (datetime.now(timezone.utc) - self.published_at).total_seconds() / 60
            if minutes < 60:
                age = f"{int(minutes)}m ago"
            else:
                age = f"{int(minutes / 60)}h ago"
        return f'"{self.title}" ({self.source}, {age})'


@dataclass  
class MacroClimate:
    """
    The current macro-economic climate.
    
    Provides context for AI decision making, not automatic blocks.
    """
    headlines: List[MacroHeadline]
    is_catastrophe: bool  # Only true for REAL disasters
    catastrophe_reason: Optional[str]
    
    def to_prompt_section(self) -> str:
        """Format macro climate for inclusion in AI prompt."""
        if not self.headlines:
            return "No macro headlines matched financial keywords. Assume neutral macro environment."
        
        lines = [f"Found {len(self.headlines)} headline(s) matching financial keywords:"]
        for h in self.headlines[:10]:  # Limit to 10
            keywords = ", ".join(h.matched_keywords[:3])
            lines.append(f"  • {h} [matched: {keywords}]")
        
        return "\n".join(lines)


class MacroContext:
    """
    Gathers macro-economic context for AI decision making.
    
    Philosophy:
        - Macro news is CONTEXT, not automatic BLOCKS
        - AI sees macro headlines and weighs them against crypto opportunities
        - "Fed rate cut" is bullish - don't block on it!
        - Only TRUE CATASTROPHES (exchange hack, market crash) block in code
    
    Usage:
        context = MacroContext()
        climate = context.get_current_climate()
        
        if climate.is_catastrophe:
            # Code-level block (rare)
        else:
            # Include climate.to_prompt_section() in AI prompt
    """
    
    def __init__(self, rss_client: Optional[RSSClient] = None):
        """Initialize macro context gatherer."""
        self.settings = get_settings()
        self.rss_client = rss_client or RSSClient(cache_seconds=300)
        
        logger.info(
            "Macro context initialized",
            catastrophe_keywords=len(CATASTROPHE_KEYWORDS),
            context_keywords=len(MACRO_CONTEXT_KEYWORDS),
        )
    
    def _check_for_catastrophe(self, headline: str) -> Optional[str]:
        """
        Check if headline indicates a TRUE CATASTROPHE.
        
        These are rare, obvious disasters where trading should stop.
        Uses word boundary matching to avoid false positives.
        
        Returns:
            Matched catastrophe keyword if found, None otherwise
        """
        headline_lower = headline.lower()
        
        for keyword in CATASTROPHE_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, headline_lower):
                return keyword
        
        return None
    
    def _extract_context_keywords(self, headline: str) -> List[str]:
        """
        Extract macro context keywords from headline.
        
        These are NOT automatic blocks - just context for AI.
        """
        headline_lower = headline.lower()
        found = []
        
        for keyword in MACRO_CONTEXT_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, headline_lower):
                found.append(keyword)
        
        return found
    
    def get_current_climate(self) -> MacroClimate:
        """
        Get the current macro-economic climate.
        
        Returns:
            MacroClimate with headlines and catastrophe status
        """
        headlines = []
        is_catastrophe = False
        catastrophe_reason = None
        
        try:
            # Fetch macro news
            macro_news = self.rss_client.fetch_crypto_news(sources=MACRO_RSS_FEEDS)
            
            for item in macro_news:
                # First check for catastrophe (code-level block)
                catastrophe_match = self._check_for_catastrophe(item.title)
                if catastrophe_match:
                    # TODO: Add recency filter - only trigger if headline < 2 hours old
                    # This would prevent false positives from old news discussing past events
                    # e.g., "Analyst recalls 2008 Lehman collapse" shouldn't trigger
                    is_catastrophe = True
                    catastrophe_reason = f"{catastrophe_match}: {item.title[:80]}"
                    logger.error(
                        "🚨 CATASTROPHE DETECTED",
                        keyword=catastrophe_match,
                        headline=item.title[:80],
                    )
                
                # Extract context keywords (for AI)
                context_keywords = self._extract_context_keywords(item.title)
                
                if context_keywords:
                    headlines.append(MacroHeadline(
                        title=item.title,
                        source=item.source,
                        published_at=item.published_at,
                        matched_keywords=context_keywords,
                    ))
            
            # Sort by recency
            headlines.sort(
                key=lambda h: h.published_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True
            )
            
            logger.info(
                "Macro climate gathered",
                headline_count=len(headlines),
                is_catastrophe=is_catastrophe,
                headlines=[h.title for h in headlines],
            )
            
        except Exception as e:
            logger.error(f"Failed to gather macro context: {e}")
        
        return MacroClimate(
            headlines=headlines,
            is_catastrophe=is_catastrophe,
            catastrophe_reason=catastrophe_reason,
        )
    
    def record_catastrophe(self, keyword: str, headline: str, source: str) -> None:
        """Record a catastrophe event in the database."""
        with get_session() as session:
            repo = MacroEventRepository(session)
            repo.record_event(
                keyword=keyword,
                headline=headline,
                source=source,
                defensive_until=datetime.now(timezone.utc) + timedelta(hours=4),
                severity="CATASTROPHE",
            )
        
        logger.error(
            "🚨 CATASTROPHE RECORDED",
            keyword=keyword,
            headline=headline[:80],
        )
    
    def get_status(self) -> dict:
        """Get current macro context status."""
        climate = self.get_current_climate()
        return {
            "headline_count": len(climate.headlines),
            "is_catastrophe": climate.is_catastrophe,
            "catastrophe_reason": climate.catastrophe_reason,
            "recent_headlines": [str(h) for h in climate.headlines[:5]],
        }

