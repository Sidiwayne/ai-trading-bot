"""
RSS Feed Client for FusionBot
==============================

Fetches and parses news from crypto RSS feeds.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.models import NewsItem
from src.core.exceptions import NewsParsingError
from src.utils.logging import get_logger
from src.utils.helpers import generate_news_id, parse_rss_date, extract_symbol_from_text
from src.config.constants import RSS_FEEDS, MACRO_RSS_FEEDS, SUPPORTED_SYMBOLS

logger = get_logger(__name__)


@dataclass
class RSSFeedResult:
    """Result from fetching an RSS feed."""
    source: str
    items: List[NewsItem]
    fetched_at: datetime
    error: Optional[str] = None


class RSSClient:
    """
    Client for fetching and parsing RSS feeds.
    
    Features:
        - Parallel fetching of multiple feeds
        - Automatic retry on failure
        - Response caching to respect rate limits
        - Symbol detection in headlines
    
    Usage:
        client = RSSClient()
        news = client.fetch_crypto_news()
        for item in news:
            print(item.title)
    """
    
    def __init__(
        self,
        timeout: int = 10,
        cache_seconds: int = 60,
        max_workers: int = 4,
    ):
        """
        Initialize RSS client.
        
        Args:
            timeout: Request timeout in seconds
            cache_seconds: Minimum time between refetches of same feed
            max_workers: Max parallel feed fetches
        """
        self.timeout = timeout
        self.cache_seconds = cache_seconds
        self.max_workers = max_workers
        
        # Cache: {source: (timestamp, items)}
        self._cache: Dict[str, tuple[float, List[NewsItem]]] = {}
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set user agent to avoid blocks
        self.session.headers.update({
            "User-Agent": "FusionBot/1.0 (Crypto News Aggregator)"
        })
        
        logger.info("RSS client initialized", cache_seconds=cache_seconds)
    
    def _is_cached(self, source: str) -> bool:
        """Check if feed is cached and still valid."""
        if source not in self._cache:
            return False
        timestamp, _ = self._cache[source]
        return (time.time() - timestamp) < self.cache_seconds
    
    def _get_cached(self, source: str) -> Optional[List[NewsItem]]:
        """Get cached items if valid."""
        if self._is_cached(source):
            _, items = self._cache[source]
            logger.debug("Using cached RSS data", source=source)
            return items
        return None
    
    def _update_cache(self, source: str, items: List[NewsItem]) -> None:
        """Update cache for a feed."""
        self._cache[source] = (time.time(), items)
    
    def _fetch_feed(self, source: str, url: str) -> RSSFeedResult:
        """
        Fetch and parse a single RSS feed.
        
        Args:
            source: Feed source name
            url: Feed URL
        
        Returns:
            RSSFeedResult with parsed items
        """
        # Check cache first
        cached = self._get_cached(source)
        if cached is not None:
            return RSSFeedResult(
                source=source,
                items=cached,
                fetched_at=datetime.now(timezone.utc),
            )
        
        try:
            logger.debug("Fetching RSS feed", source=source, url=url)
            
            # Fetch the feed
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse with feedparser
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                raise NewsParsingError(source, f"Feed parsing error: {feed.bozo_exception}")
            
            # Convert entries to NewsItem
            items: List[NewsItem] = []
            for entry in feed.entries[:50]:  # Limit to 50 most recent
                try:
                    news_item = self._parse_entry(entry, source)
                    items.append(news_item)
                except Exception as e:
                    logger.warning(
                        "Failed to parse RSS entry",
                        source=source,
                        error=str(e),
                    )
                    continue
            
            # Update cache
            self._update_cache(source, items)
            
            logger.info(
                "RSS feed fetched successfully",
                source=source,
                item_count=len(items),
            )
            
            return RSSFeedResult(
                source=source,
                items=items,
                fetched_at=datetime.now(timezone.utc),
            )
        
        except requests.RequestException as e:
            logger.error(
                "Failed to fetch RSS feed",
                source=source,
                url=url,
                error=str(e),
            )
            return RSSFeedResult(
                source=source,
                items=[],
                fetched_at=datetime.now(timezone.utc),
                error=str(e),
            )
        except Exception as e:
            logger.error(
                "Unexpected error fetching RSS",
                source=source,
                error=str(e),
            )
            return RSSFeedResult(
                source=source,
                items=[],
                fetched_at=datetime.now(timezone.utc),
                error=str(e),
            )
    
    def _parse_entry(self, entry: Any, source: str) -> NewsItem:
        """
        Parse a feedparser entry to NewsItem.
        
        Args:
            entry: Feedparser entry object
            source: Source name
        
        Returns:
            NewsItem instance
        """
        title = entry.get("title", "").strip()
        url = entry.get("link", "")
        
        # Parse publication date
        published_at = None
        for date_field in ["published", "updated", "created"]:
            if date_field in entry:
                published_at = parse_rss_date(entry[date_field])
                if published_at:
                    break
        
        # Generate unique ID
        news_id = generate_news_id(title, source)
        
        # Extract summary if available
        summary = None
        if "summary" in entry:
            summary = entry.summary[:500] if entry.summary else None
        
        # Detect symbol in title
        detected_symbol = extract_symbol_from_text(title, SUPPORTED_SYMBOLS)
        
        return NewsItem(
            id=news_id,
            title=title,
            source=source,
            url=url,
            published_at=published_at,
            detected_symbol=detected_symbol,
            summary=summary,
        )
    
    def fetch_crypto_news(self, sources: Dict[str, str] = None) -> List[NewsItem]:
        """
        Fetch news from all crypto RSS feeds.
        
        Args:
            sources: Optional dict of {name: url}, defaults to RSS_FEEDS
        
        Returns:
            List of NewsItem from all feeds, sorted by date
        """
        if sources is None:
            sources = RSS_FEEDS
        
        all_items: List[NewsItem] = []
        
        # Fetch feeds in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_feed, source, url): source
                for source, url in sources.items()
            }
            
            for future in as_completed(futures):
                source = futures[future]
                try:
                    result = future.result()
                    all_items.extend(result.items)
                except Exception as e:
                    logger.error(
                        "Feed fetch failed",
                        source=source,
                        error=str(e),
                    )
        
        # Sort by published date (newest first)
        all_items.sort(
            key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        
        logger.info(
            "Crypto news fetch complete",
            total_items=len(all_items),
            sources=len(sources),
        )
        
        return all_items
    
    def fetch_macro_news(self) -> List[NewsItem]:
        """
        Fetch news from macro/financial RSS feeds.
        
        Used for detecting systemic risk events.
        
        Returns:
            List of NewsItem from financial feeds
        """
        return self.fetch_crypto_news(sources=MACRO_RSS_FEEDS)
    
    def get_relevant_news(
        self,
        symbols: List[str] = None,
        max_age_hours: int = 4,
    ) -> List[NewsItem]:
        """
        Get news relevant to specific symbols.
        
        Args:
            symbols: List of trading pairs to filter for
            max_age_hours: Maximum age of news to include
        
        Returns:
            Filtered list of NewsItem
        """
        all_news = self.fetch_crypto_news()
        
        # Filter by age
        if max_age_hours:
            cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
            all_news = [
                n for n in all_news
                if n.published_at and n.published_at.timestamp() > cutoff
            ]
        
        # Filter by symbol if specified
        if symbols:
            all_news = [
                n for n in all_news
                if n.detected_symbol in symbols
            ]
        
        return all_news
    
    def clear_cache(self) -> None:
        """Clear the RSS cache."""
        self._cache.clear()
        logger.info("RSS cache cleared")

