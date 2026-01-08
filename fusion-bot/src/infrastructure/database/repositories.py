"""
Repository Pattern for FusionBot
=================================

Data access layer abstracting database operations.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from src.core.enums import TradeStatus, ExitReason
from src.core.models import NewsItem, Position
from src.core.exceptions import RecordNotFoundError, DuplicateRecordError
from src.infrastructure.database.models import (
    SeenNewsORM,
    TradeORM,
    MacroEventORM,
    SystemStateORM,
    DailyPerformanceORM,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NewsRepository:
    """
    Repository for news item operations.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def is_seen(self, news_id: str) -> bool:
        """
        Check if a news item has already been processed.
        
        Args:
            news_id: Unique news identifier
        
        Returns:
            True if news was already processed
        """
        exists = self.session.query(SeenNewsORM).filter(
            SeenNewsORM.id == news_id
        ).first()
        return exists is not None
    
    def mark_seen(
        self,
        news_item: NewsItem,
        action_taken: str,
        rejection_reason: Optional[str] = None,
    ) -> None:
        """
        Mark a news item as processed.
        
        Args:
            news_item: The news item to mark
            action_taken: What action was taken (BUY, WAIT, REJECTED)
            rejection_reason: If rejected, why
        """
        record = SeenNewsORM(
            id=news_item.id,
            title=news_item.title,
            source=news_item.source,
            url=news_item.url,
            published_at=news_item.published_at,
            processed_at=datetime.now(timezone.utc),
            detected_symbol=news_item.detected_symbol,
            action_taken=action_taken,
            rejection_reason=rejection_reason,
        )
        
        # Use merge to handle potential duplicates gracefully
        self.session.merge(record)
        self.session.flush()
        
        logger.debug(
            "News marked as seen",
            news_id=news_item.id[:8],
            action=action_taken,
        )
    
    def get_recent(self, hours: int = 24, limit: int = 100) -> List[SeenNewsORM]:
        """
        Get recently processed news items.
        
        Args:
            hours: How far back to look
            limit: Maximum number to return
        
        Returns:
            List of news records
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.session.query(SeenNewsORM).filter(
            SeenNewsORM.processed_at >= cutoff
        ).order_by(desc(SeenNewsORM.processed_at)).limit(limit).all()
    
    def count_today(self) -> int:
        """Get count of news processed today."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return self.session.query(SeenNewsORM).filter(
            SeenNewsORM.processed_at >= today_start
        ).count()


class TradeRepository:
    """
    Repository for trade operations.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        virtual_sl: float,
        virtual_tp: float,
        catastrophe_sl: float,
        entry_order_id: Optional[str] = None,
        exchange_stop_order_id: Optional[str] = None,
        news_id: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> TradeORM:
        """
        Create a new trade record.
        
        Returns:
            Created trade record
        """
        trade = TradeORM(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            virtual_sl_price=virtual_sl,
            virtual_tp_price=virtual_tp,
            catastrophe_sl_price=catastrophe_sl,
            entry_order_id=entry_order_id,
            exchange_stop_order_id=exchange_stop_order_id,
            status=TradeStatus.OPEN.value,
            news_id=news_id,
            gemini_reasoning=reasoning,
            opened_at=datetime.now(timezone.utc),
        )
        
        self.session.add(trade)
        self.session.flush()  # Get the ID
        
        logger.info(
            "Trade created",
            trade_id=trade.id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
        )
        
        return trade
    
    def get_by_id(self, trade_id: int) -> Optional[TradeORM]:
        """Get trade by ID."""
        return self.session.query(TradeORM).filter(
            TradeORM.id == trade_id
        ).first()
    
    def get_open_trades(self) -> List[TradeORM]:
        """Get all open trades."""
        return self.session.query(TradeORM).filter(
            TradeORM.status.in_([TradeStatus.OPEN.value, TradeStatus.PENDING.value])
        ).all()
    
    def get_open_by_symbol(self, symbol: str) -> Optional[TradeORM]:
        """Get open trade for a specific symbol."""
        return self.session.query(TradeORM).filter(
            and_(
                TradeORM.symbol == symbol,
                TradeORM.status.in_([TradeStatus.OPEN.value, TradeStatus.PENDING.value])
            )
        ).first()
    
    def count_open(self) -> int:
        """Count open positions across all symbols."""
        return self.session.query(TradeORM).filter(
            TradeORM.status.in_([TradeStatus.OPEN.value, TradeStatus.PENDING.value])
        ).count()
    
    def count_open_by_symbol(self, symbol: str) -> int:
        """Count open positions for a specific symbol."""
        return self.session.query(TradeORM).filter(
            TradeORM.symbol == symbol,
            TradeORM.status.in_([TradeStatus.OPEN.value, TradeStatus.PENDING.value])
        ).count()
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: Optional[float],
        exit_reason: ExitReason,
        exit_order_id: Optional[str] = None,
    ) -> TradeORM:
        """
        Close a trade and calculate P&L.
        
        Args:
            trade_id: Trade to close
            exit_price: Exit fill price (None for unknown exits like EXTERNAL_CLOSE)
            exit_reason: Why the trade was closed
            exit_order_id: Exchange order ID for exit
        
        Returns:
            Updated trade record
        """
        trade = self.get_by_id(trade_id)
        if not trade:
            raise RecordNotFoundError("trades", str(trade_id))
        
        # Calculate P&L (only if exit_price is known)
        if exit_price is not None:
            if trade.side == "BUY":
                pnl_amount = (exit_price - trade.entry_price) * trade.quantity
            else:
                pnl_amount = (trade.entry_price - exit_price) * trade.quantity
            
            pnl_percent = pnl_amount / (trade.entry_price * trade.quantity)
        else:
            # Unknown exit price (e.g., EXTERNAL_CLOSE) - set PnL to None
            pnl_amount = None
            pnl_percent = None
        
        # Update trade
        trade.status = TradeStatus.CLOSED.value
        trade.exit_price = exit_price
        trade.exit_order_id = exit_order_id
        trade.exit_reason = exit_reason.value
        trade.pnl_amount = pnl_amount
        trade.pnl_percent = pnl_percent
        trade.closed_at = datetime.now(timezone.utc)
        
        self.session.flush()
        
        if exit_price is not None:
            logger.info(
                "Trade closed",
                trade_id=trade_id,
                exit_price=exit_price,
                exit_reason=exit_reason.value,
                pnl_percent=f"{pnl_percent:+.2%}",
            )
        else:
            logger.warning(
                "Trade closed with unknown exit price (external close)",
                trade_id=trade_id,
                exit_reason=exit_reason.value,
            )
        
        return trade
    
    def update_stop_order_id(self, trade_id: int, order_id: str) -> None:
        """Update the exchange stop order ID."""
        trade = self.get_by_id(trade_id)
        if trade:
            trade.exchange_stop_order_id = order_id
            self.session.flush()
    
    def get_zombie_trades(self, max_hours: int = 4) -> List[TradeORM]:
        """Get trades that have been open too long."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_hours)
        return self.session.query(TradeORM).filter(
            and_(
                TradeORM.status == TradeStatus.OPEN.value,
                TradeORM.opened_at < cutoff
            )
        ).all()
    
    def get_recent_trades(self, limit: int = 50) -> List[TradeORM]:
        """Get recent trades (open and closed)."""
        return self.session.query(TradeORM).order_by(
            desc(TradeORM.opened_at)
        ).limit(limit).all()
    
    def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get trading performance statistics."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        trades = self.session.query(TradeORM).filter(
            and_(
                TradeORM.status == TradeStatus.CLOSED.value,
                TradeORM.closed_at >= cutoff
            )
        ).all()
        
        if not trades:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl_percent": 0.0,
                "avg_pnl_percent": 0.0,
            }
        
        wins = [t for t in trades if (t.pnl_percent or 0) > 0]
        losses = [t for t in trades if (t.pnl_percent or 0) <= 0]
        total_pnl = sum(t.pnl_percent or 0 for t in trades)
        
        return {
            "total_trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(trades) if trades else 0,
            "total_pnl_percent": total_pnl,
            "avg_pnl_percent": total_pnl / len(trades) if trades else 0,
        }


class MacroEventRepository:
    """
    Repository for macro event operations.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def record_event(
        self,
        keyword: str,
        headline: str,
        source: str,
        defensive_until: datetime,
        severity: str = "WARNING",
    ) -> MacroEventORM:
        """Record a macro event that triggered defensive mode."""
        event = MacroEventORM(
            keyword=keyword,
            headline=headline,
            source=source,
            severity=severity,
            detected_at=datetime.now(timezone.utc),
            defensive_mode_until=defensive_until,
        )
        self.session.add(event)
        self.session.flush()
        
        logger.warning(
            "Macro event recorded",
            keyword=keyword,
            headline=headline[:100],
            defensive_until=defensive_until.isoformat(),
        )
        
        return event
    
    def get_active_defensive_mode(self) -> Optional[MacroEventORM]:
        """Get active defensive mode event if any."""
        now = datetime.now(timezone.utc)
        return self.session.query(MacroEventORM).filter(
            MacroEventORM.defensive_mode_until > now
        ).order_by(desc(MacroEventORM.defensive_mode_until)).first()
    
    def get_recent(self, hours: int = 24) -> List[MacroEventORM]:
        """Get recent macro events."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.session.query(MacroEventORM).filter(
            MacroEventORM.detected_at >= cutoff
        ).order_by(desc(MacroEventORM.detected_at)).all()


class SystemStateRepository:
    """
    Repository for system state key-value store.
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a state value."""
        record = self.session.query(SystemStateORM).filter(
            SystemStateORM.key == key
        ).first()
        return record.value if record else default
    
    def set(self, key: str, value: str) -> None:
        """Set a state value."""
        record = self.session.query(SystemStateORM).filter(
            SystemStateORM.key == key
        ).first()
        
        if record:
            record.value = value
            record.updated_at = datetime.now(timezone.utc)
        else:
            record = SystemStateORM(key=key, value=value)
            self.session.add(record)
        
        self.session.flush()
    
    def delete(self, key: str) -> bool:
        """Delete a state value."""
        result = self.session.query(SystemStateORM).filter(
            SystemStateORM.key == key
        ).delete()
        self.session.flush()
        return result > 0
    
    def update_heartbeat(self) -> None:
        """Update the system heartbeat timestamp."""
        self.set("last_heartbeat", datetime.now(timezone.utc).isoformat())
    
    def get_last_heartbeat(self) -> Optional[datetime]:
        """Get the last heartbeat timestamp."""
        value = self.get("last_heartbeat")
        if value:
            return datetime.fromisoformat(value)
        return None
    
    def is_defensive_mode(self) -> bool:
        """Check if defensive mode is active."""
        return self.get("defensive_mode", "false").lower() == "true"
    
    def set_defensive_mode(self, active: bool) -> None:
        """Set defensive mode state."""
        self.set("defensive_mode", str(active).lower())

