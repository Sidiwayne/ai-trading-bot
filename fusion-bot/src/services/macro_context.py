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
from src.utils.classification_cache import ClassificationCache
from src.services.notifier import get_notifier
from src.services.catastrophe_classifier import CatastropheClassifier

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
        
        # Initialize catastrophe classifier (eager loading - critical component)
        try:
            self.catastrophe_classifier = CatastropheClassifier()
        except Exception as e:
            logger.warning(
                "Failed to initialize catastrophe classifier, will use keyword matching",
                error=str(e),
            )
            self.catastrophe_classifier = None
        
        # Initialize classification cache (centralized cache manager)
        self.cache = ClassificationCache(ttl_hours=2.0)  # Match recency filter
        
        logger.info(
            "Macro context initialized",
            catastrophe_keywords=len(CATASTROPHE_KEYWORDS),
            context_keywords=len(MACRO_CONTEXT_KEYWORDS),
            classifier_available=self.catastrophe_classifier is not None,
        )
    
    def _check_for_catastrophe(
        self, headline: str, published_at: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Check if headline indicates a TRUE CATASTROPHE.
        
        Uses sentence transformer for semantic classification, with keyword matching as fallback.
        Results are cached to avoid redundant model inference.
        
        Args:
            headline: News headline to check
            published_at: Publication timestamp (for recency filter)
        
        Returns:
            Matched catastrophe keyword if found, None otherwise
        """
        # Step 1: Recency filter - only check recent headlines (< 2 hours old)
        if published_at:
            age_hours = (datetime.now(timezone.utc) - published_at).total_seconds() / 3600
            if age_hours > 2.0:
                # Headline too old - skip check (don't cache)
                return None
        
        # Step 2: Check cache
        is_cached, cached_result = self.cache.get_classification(headline)
        if is_cached:
            # Cache hit - return cached result (can be None if cached as "not catastrophe")
            return cached_result
        
        # Step 3: Compute classification (not cached or expired)
        result = None
        
        # Use sentence transformer classifier if available
        if self.catastrophe_classifier:
            is_catastrophe = self.catastrophe_classifier.is_catastrophe(headline)
            if is_catastrophe:
                # Classifier says it's a catastrophe - extract keyword for logging
                headline_lower = headline.lower()
                for keyword in CATASTROPHE_KEYWORDS:
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, headline_lower):
                        result = keyword
                        break
                # If classifier says catastrophe but no keyword match, return generic
                if result is None:
                    result = "catastrophe_detected"
            # else: result stays None (not a catastrophe)
        else:
            # Fallback to keyword matching ONLY if classifier unavailable
            headline_lower = headline.lower()
            for keyword in CATASTROPHE_KEYWORDS:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, headline_lower):
                    result = keyword
                    break
        
        # Step 4: Cache the result
        self.cache.set_classification(headline, result)
        
        return result
    
    def _extract_context_keywords(self, headline: str) -> List[str]:
        """
        Extract macro context keywords from headline.
        
        These are NOT automatic blocks - just context for AI.
        Results are cached to avoid redundant regex matching.
        
        Args:
            headline: News headline to extract keywords from
        
        Returns:
            List of matched context keywords
        """
        # Check cache
        is_cached, cached_keywords = self.cache.get_context_keywords(headline)
        if is_cached:
            # Cache hit - return cached keywords (can be empty list)
            return cached_keywords
        
        # Compute keywords (not cached or expired)
        headline_lower = headline.lower()
        found = []
        
        for keyword in MACRO_CONTEXT_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, headline_lower):
                found.append(keyword)
        
        # Cache the result
        self.cache.set_context_keywords(headline, found)
        
        return found
    
    def get_current_climate(self) -> MacroClimate:
        """
        Get the current macro-economic climate.
        
        Returns:
            MacroClimate with headlines and catastrophe status
        """
        # Periodic cleanup of expired cache entries
        self.cache.cleanup_expired()
        
        headlines = []
        is_catastrophe = False
        catastrophe_reason = None
        
        try:
            # Fetch macro news
            macro_news = self.rss_client.fetch_crypto_news(sources=MACRO_RSS_FEEDS)
            
            for item in macro_news:
                # First check for catastrophe (code-level block)
                catastrophe_match = self._check_for_catastrophe(item.title, item.published_at)
                if catastrophe_match:
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
        
        # Send Telegram notification
        notifier = get_notifier()
        if notifier:
            notifier.send(
                f"<b>🚨 Macro Catastrophe Detected</b>\n"
                f"Keyword: <code>{keyword}</code>\n"
                f"Headline: {headline[:200]}\n"
                f"Source: {source}\n"
                f"\n⚠️ Trading blocked for 4 hours.",
                priority="CRITICAL"
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

