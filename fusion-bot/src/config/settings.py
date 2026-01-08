"""
Pydantic Settings for FusionBot
===============================

Type-safe configuration management with validation.
All settings are loaded from environment variables.
"""

from functools import lru_cache
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Usage:
        from src.config import get_settings
        settings = get_settings()
        print(settings.database_url)
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # === Database ===
    database_url: str = Field(
        default="postgresql+psycopg://fusionbot:fusionbot@localhost:5432/fusionbot",
        description="PostgreSQL connection URL (uses psycopg3)"
    )
    
    # === Exchange ===
    binance_api_key: str = Field(
        default="",
        description="Binance API key"
    )
    binance_api_secret: str = Field(
        default="",
        description="Binance API secret"
    )
    binance_testnet: bool = Field(
        default=True,
        description="Use Binance testnet"
    )
    
    # === AI ===
    google_api_key: str = Field(
        default="",
        description="Google Gemini API key"
    )
    
    # === Trading Mode ===
    trading_mode: str = Field(
        default="paper",
        description="Trading mode: 'paper' or 'live'"
    )
    
    # === Risk Parameters ===
    max_risk_per_trade: float = Field(
        default=0.02,
        ge=0.001,
        le=0.10,
        description="Maximum risk per trade (0.02 = 2%)"
    )
    max_position_pct: float = Field(
        default=0.30,
        ge=0.05,
        le=1.0,
        description="Maximum position size as % of balance (0.30 = 30%)"
    )
    trading_fee_rate: float = Field(
        default=0.001,
        ge=0,
        le=0.01,
        description="Trading fee rate for position sizing (0.001 = 0.1%)"
    )
    max_positions_per_symbol: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Maximum open positions per symbol (allows diversification)"
    )
    max_total_positions: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum total positions across all symbols (safety cap)"
    )
    virtual_stop_loss_pct: float = Field(
        default=-0.02,
        le=0,
        description="Virtual stop loss percentage (-0.02 = -2%)"
    )
    virtual_take_profit_pct: float = Field(
        default=0.04,
        ge=0,
        description="Virtual take profit percentage (0.04 = +4%)"
    )
    catastrophe_stop_loss_pct: float = Field(
        default=-0.10,
        le=0,
        description="Catastrophe stop loss percentage (-0.10 = -10%)"
    )
    max_trade_duration_hours: int = Field(
        default=4,
        ge=1,
        le=72,
        description="Maximum trade duration before forced close"
    )
    min_confidence_threshold: int = Field(
        default=70,
        ge=0,
        le=100,
        description="Minimum AI confidence to execute trade"
    )
    
    # === Chase Prevention ===
    max_price_move_since_news_pct: float = Field(
        default=0.015,
        ge=0,
        le=0.10,
        description="Max price move since news to avoid chasing (0.015 = 1.5%)"
    )
    
    # === Trade Cooldown ===
    trade_cooldown_minutes: int = Field(
        default=30,
        ge=0,
        le=1440,
        description="Minimum minutes between opening new trades"
    )
    
    # === Watchlist ===
    watchlist: str = Field(
        default="BTC/USDT,ETH/USDT,SOL/USDT",
        description="Comma-separated trading pairs"
    )
    
    # === Polling Intervals ===
    main_loop_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Main loop interval in seconds"
    )
    position_check_interval_seconds: int = Field(
        default=10,
        ge=5,
        le=60,
        description="Position check interval in seconds"
    )
    rss_cache_seconds: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="RSS cache duration in seconds"
    )
    
    # === Defensive Mode ===
    macro_danger_keywords: str = Field(
        default="Fed,CPI,FOMC,Powell,rate hike,rate cut,inflation,recession,war",
        description="Comma-separated danger keywords"
    )
    defensive_mode_duration_hours: int = Field(
        default=2,
        ge=1,
        le=24,
        description="Defensive mode duration in hours"
    )
    
    # === System ===
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_path: str = Field(
        default="logs/fusionbot.log",
        description="Log file path"
    )
    
    # === Development ===
    dry_run: bool = Field(
        default=False,
        description="Dry run mode (log but don't execute)"
    )
    
    # === Validators ===
    @field_validator("trading_mode")
    @classmethod
    def validate_trading_mode(cls, v: str) -> str:
        """Ensure trading mode is valid."""
        v = v.lower()
        if v not in ("paper", "live"):
            raise ValueError("trading_mode must be 'paper' or 'live'")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid."""
        v = v.upper()
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v
    
    # === Computed Properties ===
    @property
    def watchlist_symbols(self) -> List[str]:
        """Get watchlist as a list of symbols."""
        return [s.strip() for s in self.watchlist.split(",") if s.strip()]
    
    @property
    def danger_keywords_list(self) -> List[str]:
        """Get danger keywords as a list."""
        return [k.strip().lower() for k in self.macro_danger_keywords.split(",") if k.strip()]
    
    @property
    def is_paper_mode(self) -> bool:
        """Check if running in paper trading mode."""
        return self.trading_mode == "paper"
    
    @property
    def is_live_mode(self) -> bool:
        """Check if running in live trading mode."""
        return self.trading_mode == "live"
    
    # === Notifications ===
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token from @BotFather"
    )
    telegram_chat_id: str = Field(
        default="",
        description="Telegram chat ID to send notifications to"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    
    Returns:
        Settings: Application settings
    """
    return Settings()

