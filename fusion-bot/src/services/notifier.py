"""
Notification Service for FusionBot
===================================

Sends critical alerts via Telegram.
Only sends: Critical events, Financial events, System failures, Important trade events.
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NotifierInterface(ABC):
    """Abstract interface for notification services."""
    
    @abstractmethod
    def send(self, message: str, priority: str = "INFO") -> bool:
        """
        Send a notification.
        
        Args:
            message: Message to send
            priority: Priority level (CRITICAL, HIGH, MEDIUM, INFO)
        
        Returns:
            True if sent successfully
        """
        pass


class TelegramNotifier(NotifierInterface):
    """
    Telegram bot notifier.
    
    Sends messages to a Telegram chat via bot API.
    """
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Telegram chat ID to send messages to
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._enabled = bool(bot_token and chat_id)
        
        if not self._enabled:
            logger.warning("Telegram notifier disabled - missing bot_token or chat_id")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def send(self, message: str, priority: str = "INFO") -> bool:
        """
        Send message to Telegram.
        
        Args:
            message: Message to send
            priority: Priority level (for future filtering)
        
        Returns:
            True if sent successfully
        """
        if not self._enabled:
            return False
        
        try:
            # Format message with emoji based on priority
            emoji = self._get_emoji(priority)
            formatted_message = f"{emoji} {message}"
            
            response = requests.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": formatted_message,
                    "parse_mode": "HTML",  # Enable HTML formatting
                },
                timeout=10,
            )
            response.raise_for_status()
            
            logger.debug("Telegram notification sent", priority=priority)
            return True
            
        except Exception as e:
            logger.error("Failed to send Telegram notification", error=str(e), priority=priority)
            return False
    
    def _get_emoji(self, priority: str) -> str:
        """Get emoji for priority level."""
        emoji_map = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "ℹ️",
            "INFO": "ℹ️",
        }
        return emoji_map.get(priority, "ℹ️")
    
    def send_trade_opened(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        trade_id: int,
    ) -> bool:
        """Send notification for new position opened."""
        message = (
            f"<b>📈 Position Opened</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Quantity: {quantity:.8f}\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Trade ID: {trade_id}"
        )
        return self.send(message, priority="HIGH")
    
    def send_trade_closed(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        exit_price: Optional[float],
        pnl_percent: Optional[float],
        reason: str,
        trade_id: int,
    ) -> bool:
        """Send notification for position closed."""
        pnl_emoji = "✅" if (pnl_percent and pnl_percent > 0) else "❌"
        pnl_text = f"{pnl_percent:+.2%}" if pnl_percent is not None else "Unknown"
        
        exit_text = f"${exit_price:,.2f}" if exit_price else "Unknown"
        message = (
            f"<b>{pnl_emoji} Position Closed</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Quantity: {quantity:.8f}\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Exit: {exit_text}\n"
            f"PnL: {pnl_text}\n"
            f"Reason: {reason}\n"
            f"Trade ID: {trade_id}"
        )
        return self.send(message, priority="HIGH")
    
    def send_catastrophe_stop(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        pnl_percent: float,
        trade_id: int,
    ) -> bool:
        """Send notification for catastrophe stop hit."""
        message = (
            f"<b>🚨 Catastrophe Stop Hit</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Exit: ${exit_price:,.2f}\n"
            f"Loss: {pnl_percent:.2%}\n"
            f"Trade ID: {trade_id}"
        )
        return self.send(message, priority="CRITICAL")
    
    def send_external_close(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        trade_id: int,
    ) -> bool:
        """Send notification for external close (security alert)."""
        message = (
            f"<b>🔍 SECURITY ALERT: External Close Detected</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Quantity: {quantity:.8f}\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Trade ID: {trade_id}\n"
            f"\n⚠️ Position sold externally (manual/compromise).\n"
            f"Requires investigation."
        )
        return self.send(message, priority="CRITICAL")
    
    def send_system_failure(
        self,
        component: str,
        error: str,
    ) -> bool:
        """Send notification for system failure."""
        message = (
            f"<b>⚠️ System Failure</b>\n"
            f"Component: <code>{component}</code>\n"
            f"Error: {error[:200]}"
        )
        return self.send(message, priority="CRITICAL")
    
    def send_exchange_error(
        self,
        operation: str,
        error: str,
    ) -> bool:
        """Send notification for exchange connection error."""
        message = (
            f"<b>⚠️ Exchange Error</b>\n"
            f"Operation: {operation}\n"
            f"Error: {error[:200]}"
        )
        return self.send(message, priority="CRITICAL")


def get_notifier() -> Optional[TelegramNotifier]:
    """
    Get configured notifier instance.
    
    Returns:
        TelegramNotifier if configured, None otherwise
    """
    settings = get_settings()
    
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return None
    
    return TelegramNotifier(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )

