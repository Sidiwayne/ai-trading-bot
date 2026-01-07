"""Configuration module for FusionBot."""

from src.config.settings import Settings, get_settings
from src.config.constants import (
    RSS_FEEDS,
    MACRO_RSS_FEEDS,
    DANGER_KEYWORDS,
    SUPPORTED_SYMBOLS,
)

__all__ = [
    "Settings",
    "get_settings",
    "RSS_FEEDS",
    "MACRO_RSS_FEEDS",
    "DANGER_KEYWORDS",
    "SUPPORTED_SYMBOLS",
]

