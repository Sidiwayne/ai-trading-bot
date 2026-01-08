"""
Logging Configuration for FusionBot
====================================

Structured logging with both console and file output.
Uses structlog for rich, structured log entries.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import structlog
from rich.console import Console
from rich.logging import RichHandler


def setup_logging(
    log_level: str = "INFO",
    log_path: Optional[str] = None,
    json_logs: bool = False,
) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_path: Path to log file (optional)
        json_logs: If True, output JSON formatted logs
    """
    # Convert string level to logging constant
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create handlers
    handlers = []
    
    if json_logs:
        # JSON console handler for Docker/Loki (structured logs)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter('%(message)s'))
    else:
        # Rich console handler for beautiful terminal output (local dev)
        console_handler = RichHandler(
            console=Console(stderr=True),
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
        )
    console_handler.setLevel(level)
    handlers.append(console_handler)
    
    # File handler if path specified
    if log_path:
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_file,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        
        # Use JSON format for file logs
        if json_logs:
            file_handler.setFormatter(
                logging.Formatter('%(message)s')
            )
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            )
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )
    
    # Configure structlog
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    if json_logs:
        # JSON output for Loki/Docker
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Pretty output for local dev
        shared_processors.append(structlog.stdlib.ProcessorFormatter.wrap_for_formatter)
    
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Silence noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("ccxt").setLevel(logging.WARNING)
    logging.getLogger("feedparser").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured structlog logger
    
    Usage:
        logger = get_logger(__name__)
        logger.info("Trade executed", symbol="BTC/USDT", price=50000)
    """
    return structlog.get_logger(name)


class TradeLogger:
    """
    Specialized logger for trade events.
    
    Provides consistent formatting for trade-related log entries.
    """
    
    def __init__(self):
        self.logger = get_logger("fusionbot.trades")
    
    def log_signal(
        self,
        symbol: str,
        action: str,
        confidence: int,
        reasoning: str,
    ) -> None:
        """Log a trading signal."""
        self.logger.info(
            "Trading signal generated",
            symbol=symbol,
            action=action,
            confidence=confidence,
            reasoning=reasoning[:100] + "..." if len(reasoning) > 100 else reasoning,
        )
    
    def log_entry(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_id: str,
    ) -> None:
        """Log trade entry."""
        self.logger.info(
            "Trade entered",
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_id=order_id,
        )
    
    def log_exit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        pnl_percent: float,
        reason: str,
    ) -> None:
        """Log trade exit."""
        emoji = "✅" if pnl_percent > 0 else "❌"
        self.logger.info(
            f"{emoji} Trade closed",
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_percent=f"{pnl_percent:+.2%}",
            reason=reason,
        )
    
    def log_rejection(
        self,
        symbol: str,
        reason: str,
        details: dict = None,
    ) -> None:
        """Log trade rejection."""
        self.logger.warning(
            "Trade rejected",
            symbol=symbol,
            reason=reason,
            **(details or {}),
        )


# Create global trade logger instance
trade_logger = TradeLogger()

