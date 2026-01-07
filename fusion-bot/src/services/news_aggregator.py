"""
News Aggregator Service for FusionBot
======================================

Aggregates and filters crypto news from RSS feeds.
Handles deduplication and symbol detection.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional

from src.core.models import NewsItem
from src.core.exceptions import NewsParsingError
from src.infrastructure.clients.rss_client import RSSClient
from src.infrastructure.database import get_session
from src.infrastructure.database.repositories import NewsRepository
from src.config import get_settings
from src.config.constants import SUPPORTED_SYMBOLS
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NewsAggregator:
    """
    Aggregates crypto news from multiple RSS sources.
    
    Responsibilities:
        - Fetch news from configured RSS feeds
        - Filter for relevant symbols (from watchlist)
        - Deduplicate against previously processed news
        - Filter by age (ignore stale news)
    
    Usage:
        aggregator = NewsAggregator()
        new_headlines = aggregator.get_actionable_news()
    """
    
    def __init__(
        self,
        rss_client: Optional[RSSClient] = None,
        max_age_hours: int = 4,
    ):
        """
        Initialize news aggregator.
        
        Args:
            rss_client: RSS client instance (creates one if not provided)
            max_age_hours: Maximum age of news to consider
        """
        self.settings = get_settings()
        self.rss_client = rss_client or RSSClient(
            cache_seconds=self.settings.rss_cache_seconds
        )
        self.max_age_hours = max_age_hours
        self.watchlist = self.settings.watchlist_symbols
        
        logger.info(
            "News aggregator initialized",
            watchlist=self.watchlist,
            max_age_hours=max_age_hours,
        )
    
    def fetch_all_news(self) -> List[NewsItem]:
        """
        Fetch all news from RSS feeds.
        
        Returns:
            List of NewsItem from all feeds
        """
        try:
            return self.rss_client.fetch_crypto_news()
        except Exception as e:
            logger.error("Failed to fetch news", error=str(e))
            return []
    
    def filter_by_age(self, news: List[NewsItem]) -> List[NewsItem]:
        """
        Filter news by age.
        
        Args:
            news: List of news items
        
        Returns:
            News items younger than max_age_hours
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.max_age_hours)
        
        filtered = []
        for item in news:
            if item.published_at is None:
                # No date available - include but log
                logger.debug(
                    "News item without publish date",
                    news_id=item.id[:8],
                    title=item.title[:50],
                )
                filtered.append(item)
            elif item.published_at >= cutoff:
                filtered.append(item)
        
        logger.debug(
            "Age filter applied",
            before=len(news),
            after=len(filtered),
        )
        return filtered
    
    def filter_by_watchlist(self, news: List[NewsItem]) -> List[NewsItem]:
        """
        Filter news for symbols in the watchlist.
        
        Args:
            news: List of news items
        
        Returns:
            News items mentioning watchlist symbols
        """
        filtered = [
            item for item in news
            if item.detected_symbol and item.detected_symbol in self.watchlist
        ]
        
        logger.debug(
            "Watchlist filter applied",
            before=len(news),
            after=len(filtered),
            watchlist=self.watchlist,
        )
        return filtered
    
    def filter_duplicates(self, news: List[NewsItem]) -> List[NewsItem]:
        """
        Filter out already-processed news.
        
        Args:
            news: List of news items
        
        Returns:
            News items not previously processed
        """
        new_items = []
        
        with get_session() as session:
            repo = NewsRepository(session)
            
            for item in news:
                if not repo.is_seen(item.id):
                    new_items.append(item)
                else:
                    logger.debug(
                        "Skipping duplicate news",
                        news_id=item.id[:8],
                        title=item.title[:50],
                    )
        
        logger.debug(
            "Deduplication applied",
            before=len(news),
            after=len(new_items),
        )
        return new_items
    
    def get_actionable_news(self) -> List[NewsItem]:
        """
        Get new, relevant, actionable news items.
        
        This is the main method - it:
        1. Fetches all news
        2. Filters by age
        3. Filters by watchlist symbols
        4. Removes duplicates
        
        Returns:
            List of actionable NewsItem
        """
        # Fetch all news
        all_news = self.fetch_all_news()
        
        if not all_news:
            logger.info("No news fetched from RSS feeds")
            return []
        
        logger.info(f"Fetched {len(all_news)} news items from RSS")
        
        # Apply filters
        news = self.filter_by_age(all_news)
        news = self.filter_by_watchlist(news)
        news = self.filter_duplicates(news)
        
        if news:
            logger.info(
                "Actionable news found",
                count=len(news),
                titles=[n.title[:50] for n in news[:3]],
            )
        else:
            logger.debug("No actionable news after filtering")
        
        return news
    
    def mark_processed(
        self,
        news_item: NewsItem,
        action: str,
        rejection_reason: Optional[str] = None,
    ) -> None:
        """
        Mark a news item as processed.
        
        Args:
            news_item: The news item to mark
            action: Action taken (BUY, WAIT, REJECTED)
            rejection_reason: Why it was rejected (if applicable)
        """
        with get_session() as session:
            repo = NewsRepository(session)
            repo.mark_seen(news_item, action, rejection_reason)
        
        logger.debug(
            "News marked as processed",
            news_id=news_item.id[:8],
            action=action,
        )
    
    def get_stats(self) -> dict:
        """Get news processing statistics."""
        with get_session() as session:
            repo = NewsRepository(session)
            return {
                "processed_today": repo.count_today(),
                "recent_news": [
                    {
                        "title": n.title[:50],
                        "source": n.source,
                        "action": n.action_taken,
                    }
                    for n in repo.get_recent(hours=24, limit=10)
                ],
            }

