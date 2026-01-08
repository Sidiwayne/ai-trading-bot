"""
Classification Cache Manager for FusionBot
==========================================

Centralized cache manager for classification results.
Handles caching of catastrophe classification and context keyword extraction.

Future: Can be swapped with Redis, DB, or other backends without changing
        the MacroContext service.
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ClassificationCache:
    """
    Centralized cache manager for classification results.
    
    Handles:
    - Catastrophe classification results
    - Context keyword extraction results
    - TTL-based expiration
    - Automatic cleanup
    
    Usage:
        cache = ClassificationCache(ttl_hours=2.0)
        
        # Check cache before expensive operation
        result = cache.get_classification(headline)
        if result is None:
            result = expensive_classification(headline)
            cache.set_classification(headline, result)
    
    Future: Can be swapped with Redis, DB, or other backends.
    """
    
    def __init__(self, ttl_hours: float = 2.0):
        """
        Initialize classification cache.
        
        Args:
            ttl_hours: Time-to-live for cache entries in hours
        """
        self._ttl_hours = ttl_hours
        
        # Cache storage: {normalized_headline: (result, cached_at)}
        self._classification_cache: Dict[str, Tuple[Optional[str], datetime]] = {}
        self._context_keywords_cache: Dict[str, Tuple[List[str], datetime]] = {}
        
        logger.info(
            "Classification cache initialized",
            ttl_hours=ttl_hours,
        )
    
    def normalize_key(self, headline: str) -> str:
        """
        Normalize headline for cache key.
        
        Args:
            headline: Raw headline text
        
        Returns:
            Normalized headline (lowercase, stripped, single spaces)
        """
        # Lowercase, strip, and collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', headline.strip().lower())
        return normalized
    
    def _is_expired(self, cached_at: datetime) -> bool:
        """
        Check if cache entry is expired based on TTL.
        
        Args:
            cached_at: When the entry was cached
        
        Returns:
            True if expired, False otherwise
        """
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        return age_hours > self._ttl_hours
    
    def get_classification(self, headline: str) -> Tuple[bool, Optional[str]]:
        """
        Get cached classification result.
        
        Args:
            headline: News headline to look up
        
        Returns:
            Tuple of (is_cached, result):
            - (False, None): Not cached or expired
            - (True, None): Cached as "not a catastrophe"
            - (True, keyword): Cached as "catastrophe" with keyword
        """
        cache_key = self.normalize_key(headline)
        
        if cache_key not in self._classification_cache:
            return (False, None)
        
        cached_result, cached_at = self._classification_cache[cache_key]
        
        if self._is_expired(cached_at):
            # Expired - remove and return not cached
            del self._classification_cache[cache_key]
            return (False, None)
        
        logger.debug("Cache hit for classification", headline=headline[:50])
        return (True, cached_result)
    
    def set_classification(self, headline: str, result: Optional[str]) -> None:
        """
        Cache classification result.
        
        Args:
            headline: News headline
            result: Classification result (keyword if catastrophe, None if not)
        """
        cache_key = self.normalize_key(headline)
        self._classification_cache[cache_key] = (result, datetime.now(timezone.utc))
        logger.debug("Cached classification result", headline=headline[:50])
    
    def get_context_keywords(self, headline: str) -> Tuple[bool, List[str]]:
        """
        Get cached context keywords.
        
        Args:
            headline: News headline to look up
        
        Returns:
            Tuple of (is_cached, keywords):
            - (False, []): Not cached or expired
            - (True, keywords): Cached keywords (can be empty list if no keywords found)
        """
        cache_key = self.normalize_key(headline)
        
        if cache_key not in self._context_keywords_cache:
            return (False, [])
        
        cached_keywords, cached_at = self._context_keywords_cache[cache_key]
        
        if self._is_expired(cached_at):
            # Expired - remove and return not cached
            del self._context_keywords_cache[cache_key]
            return (False, [])
        
        logger.debug("Cache hit for context keywords", headline=headline[:50])
        return (True, cached_keywords)
    
    def set_context_keywords(self, headline: str, keywords: List[str]) -> None:
        """
        Cache context keywords.
        
        Args:
            headline: News headline
            keywords: List of matched context keywords
        """
        cache_key = self.normalize_key(headline)
        self._context_keywords_cache[cache_key] = (keywords, datetime.now(timezone.utc))
        logger.debug("Cached context keywords", headline=headline[:50])
    
    def cleanup_expired(self) -> Tuple[int, int]:
        """
        Remove expired entries from both caches.
        
        Returns:
            Tuple of (classification_removed, context_removed) counts
        """
        # Clean classification cache
        classification_expired = [
            key for key, (_, cached_at) in self._classification_cache.items()
            if self._is_expired(cached_at)
        ]
        for key in classification_expired:
            del self._classification_cache[key]
        
        # Clean context keywords cache
        context_expired = [
            key for key, (_, cached_at) in self._context_keywords_cache.items()
            if self._is_expired(cached_at)
        ]
        for key in context_expired:
            del self._context_keywords_cache[key]
        
        if classification_expired or context_expired:
            logger.debug(
                "Cleaned up expired cache entries",
                classification_removed=len(classification_expired),
                context_removed=len(context_expired),
            )
        
        return len(classification_expired), len(context_expired)
    
    def clear(self) -> None:
        """
        Clear all cache entries (useful for testing).
        """
        self._classification_cache.clear()
        self._context_keywords_cache.clear()
        logger.debug("Cache cleared")
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache sizes
        """
        return {
            "classification_entries": len(self._classification_cache),
            "context_keywords_entries": len(self._context_keywords_cache),
        }

