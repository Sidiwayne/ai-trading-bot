"""
Position Manager Service for FusionBot
=======================================

Monitors and manages open positions.
Handles virtual SL/TP, time decay, and exchange sync.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from src.core.models import Position
from src.core.enums import TradeStatus, TradeSide, ExitReason
from src.infrastructure.exchange.base import ExchangeInterface
from src.infrastructure.database import get_session
from src.infrastructure.database.repositories import TradeRepository
from src.infrastructure.database.models import TradeORM
from src.config import get_settings
from src.utils.logging import get_logger, trade_logger

logger = get_logger(__name__)


class PositionManager:
    """
    Manages open trading positions.
    
    Responsibilities:
        - Monitor virtual SL/TP levels
        - Close positions when targets hit
        - Handle time decay (zombie trades)
        - Sync with exchange to detect offline fills
    
    Usage:
        manager = PositionManager(exchange)
        manager.check_all_positions()  # In main loop
    """
    
    def __init__(
        self,
        exchange: ExchangeInterface,
        order_executor: "OrderExecutor" = None,
    ):
        """
        Initialize position manager.
        
        Args:
            exchange: Exchange client for price data
            order_executor: Order executor for closing positions
        """
        self.settings = get_settings()
        self.exchange = exchange
        self._order_executor = order_executor
        
        self.max_trade_duration_hours = self.settings.max_trade_duration_hours
        
        logger.info(
            "Position manager initialized",
            max_duration_hours=self.max_trade_duration_hours,
        )
    
    @property
    def order_executor(self):
        """Get order executor (lazy import to avoid circular deps)."""
        if self._order_executor is None:
            from src.services.order_executor import OrderExecutor
            self._order_executor = OrderExecutor(self.exchange)
        return self._order_executor
    
    def _trade_to_position(self, trade: TradeORM) -> Position:
        """Convert ORM trade to Position model."""
        return Position(
            id=trade.id,
            symbol=trade.symbol,
            side=TradeSide(trade.side),
            entry_price=trade.entry_price,
            quantity=trade.quantity,
            virtual_sl=trade.virtual_sl_price,
            virtual_tp=trade.virtual_tp_price,
            catastrophe_sl=trade.catastrophe_sl_price,
            exchange_stop_order_id=trade.exchange_stop_order_id,
            status=TradeStatus(trade.status),
            opened_at=trade.opened_at,
            news_id=trade.news_id,
            reasoning=trade.gemini_reasoning,
        )
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        with get_session() as session:
            repo = TradeRepository(session)
            trades = repo.get_open_trades()
            return [self._trade_to_position(t) for t in trades]
    
    def check_virtual_targets(self, position: Position) -> Optional[Tuple[ExitReason, float]]:
        """
        Check if virtual SL or TP is hit.
        
        Args:
            position: Position to check
        
        Returns:
            Tuple of (ExitReason, trigger_price) if target hit, None otherwise
        """
        try:
            ticker = self.exchange.get_ticker(position.symbol)
            current_price = ticker.last
            
            if position.check_virtual_sl(current_price):
                logger.warning(
                    "Virtual stop loss hit",
                    trade_id=position.id,
                    symbol=position.symbol,
                    current_price=current_price,
                    sl_price=position.virtual_sl,
                )
                return (ExitReason.VIRTUAL_SL, current_price)
            
            if position.check_virtual_tp(current_price):
                logger.info(
                    "Virtual take profit hit",
                    trade_id=position.id,
                    symbol=position.symbol,
                    current_price=current_price,
                    tp_price=position.virtual_tp,
                )
                return (ExitReason.VIRTUAL_TP, current_price)
            
            return None
            
        except Exception as e:
            logger.error(
                "Failed to check virtual targets",
                trade_id=position.id,
                error=str(e),
            )
            return None
    
    def check_time_decay(self, position: Position) -> bool:
        """
        Check if position has exceeded max duration.
        
        Args:
            position: Position to check
        
        Returns:
            True if position is a "zombie" (too old)
        """
        age_hours = position.age_hours
        is_zombie = age_hours > self.max_trade_duration_hours
        
        if is_zombie:
            logger.warning(
                "Zombie trade detected",
                trade_id=position.id,
                symbol=position.symbol,
                age_hours=round(age_hours, 2),
                max_hours=self.max_trade_duration_hours,
            )
        
        return is_zombie
    
    def sync_with_exchange(self, position: Position) -> Optional[ExitReason]:
        """
        Check if position still exists on exchange.
        
        Detects if catastrophe stop was hit while bot was offline.
        
        Args:
            position: Position to verify
        
        Returns:
            ExitReason.CATASTROPHE_SL if stop was hit, None otherwise
        """
        try:
            # Check if we still hold the asset
            exchange_position = self.exchange.get_position(position.symbol)
            
            if exchange_position is None or exchange_position < position.quantity * 0.9:
                # Position is gone or significantly reduced
                logger.warning(
                    "Position missing from exchange - likely catastrophe stop hit",
                    trade_id=position.id,
                    symbol=position.symbol,
                    expected_qty=position.quantity,
                    found_qty=exchange_position,
                )
                return ExitReason.CATASTROPHE_SL
            
            return None
            
        except Exception as e:
            logger.error(
                "Failed to sync with exchange",
                trade_id=position.id,
                error=str(e),
            )
            return None
    
    def close_position(
        self,
        position: Position,
        reason: ExitReason,
        exit_price: float = None,
    ) -> None:
        """
        Close a position and update database.
        
        Args:
            position: Position to close
            reason: Reason for closing
            exit_price: Target exit price (for consistent TP/SL execution)
        """
        try:
            # Always execute exit (handles stop cancellation, selling)
            # Pass exit_price for consistent execution at trigger price
            actual_exit_price = self.order_executor.execute_exit(
                position, str(reason), at_price=exit_price
            )
            exit_price = actual_exit_price
            
            # Update database
            with get_session() as session:
                repo = TradeRepository(session)
                trade = repo.close_trade(
                    trade_id=position.id,
                    exit_price=exit_price,
                    exit_reason=reason,
                )
                
                # Log the result
                trade_logger.log_exit(
                    symbol=position.symbol,
                    side=str(position.side),
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    pnl_percent=trade.pnl_percent,
                    reason=str(reason),
                )
                
        except Exception as e:
            logger.error(
                "Failed to close position",
                trade_id=position.id,
                reason=str(reason),
                error=str(e),
            )
    
    def check_position(self, position: Position) -> None:
        """
        Check a single position for exit conditions.
        
        Args:
            position: Position to check
        """
        # Priority 1: Sync with exchange (detect catastrophe stop)
        sync_reason = self.sync_with_exchange(position)
        if sync_reason:
            # Catastrophe stop was hit - estimate exit price
            exit_price = position.catastrophe_sl
            self.close_position(position, sync_reason, exit_price)
            return
        
        # Priority 2: Check virtual targets
        target_result = self.check_virtual_targets(position)
        if target_result:
            target_reason, trigger_price = target_result
            # Pass the trigger price to ensure consistent execution price
            self.close_position(position, target_reason, exit_price=trigger_price)
            return
        
        # Priority 3: Check time decay
        if self.check_time_decay(position):
            self.close_position(position, ExitReason.TIME_DECAY)
            return
        
        # Position is fine, log status
        logger.debug(
            "Position OK",
            trade_id=position.id,
            symbol=position.symbol,
            age_hours=round(position.age_hours, 2),
        )
    
    def check_all_positions(self) -> int:
        """
        Check all open positions.
        
        This should be called frequently (every 10 seconds or so).
        
        Returns:
            Number of positions checked
        """
        positions = self.get_open_positions()
        
        if not positions:
            logger.debug("No open positions to check")
            return 0
        
        logger.info(f"Checking {len(positions)} open positions")
        
        for position in positions:
            self.check_position(position)
        
        return len(positions)
    
    def force_close_all(self, reason: str = "Manual close") -> int:
        """
        Force close all open positions.
        
        Use for emergency shutdown or end of day.
        
        Args:
            reason: Reason for force close
        
        Returns:
            Number of positions closed
        """
        positions = self.get_open_positions()
        closed = 0
        
        logger.warning(
            "Force closing all positions",
            count=len(positions),
            reason=reason,
        )
        
        for position in positions:
            try:
                self.close_position(position, ExitReason.MANUAL)
                closed += 1
            except Exception as e:
                logger.error(
                    "Failed to force close position",
                    trade_id=position.id,
                    error=str(e),
                )
        
        return closed
    
    def get_status(self) -> dict:
        """Get position manager status."""
        positions = self.get_open_positions()
        
        with get_session() as session:
            repo = TradeRepository(session)
            stats = repo.get_performance_stats()
        
        return {
            "open_positions": len(positions),
            "positions": [p.to_dict() for p in positions],
            "performance_30d": stats,
        }

