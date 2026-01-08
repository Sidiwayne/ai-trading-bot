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
from src.infrastructure.exchange.base import ExchangeInterface, OrderResult
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
    
    def sync_with_exchange(self, position: Position) -> Tuple[Optional[ExitReason], Optional[OrderResult]]:
        """
        Check if position still exists on exchange.
        
        Detects if catastrophe stop was hit while bot was offline.
        
        Args:
            position: Position to verify
        
        Returns:
            Tuple of (ExitReason, stop_order).
            - If catastrophe stop detected: (ExitReason.CATASTROPHE_SL, stop_order)
            - Otherwise: (None, None)
            The stop_order is included to avoid re-fetching it in the caller.
        """
        try:
            # Check if we still hold the asset
            exchange_position = self.exchange.get_position(position.symbol)
            
            # If position still exists, no catastrophe stop
            if exchange_position is not None and exchange_position >= position.quantity * 0.9:
                return (None, None)
            
            # Position is missing - check if stop-loss order still exists
            stop_order = None
            if position.exchange_stop_order_id:
                try:
                    # Check if stop-loss order still exists
                    stop_order = self.exchange.get_order(
                        position.symbol,
                        position.exchange_stop_order_id
                    )
                    
                    if stop_order and stop_order.status == "open":
                        # Position is missing but stop order is still open
                        # This means position was sold EXTERNALLY (manual, compromise, or error)
                        # Log for investigation - do not auto-close yet
                        logger.error(
                            "🔍 INVESTIGATION: Position sold externally but stop order still open",
                            trade_id=position.id,
                            symbol=position.symbol,
                            expected_qty=position.quantity,
                            found_qty=exchange_position,
                            stop_order_id=position.exchange_stop_order_id,
                            entry_price=position.entry_price,
                            opened_at=position.opened_at.isoformat(),
                            note="Position may have been sold manually, via compromised API key, or exchange error. Requires manual investigation.",
                        )
                        # Return EXTERNAL_CLOSE for logging/investigation
                        return (ExitReason.EXTERNAL_CLOSE, stop_order)
                except Exception as e:
                    logger.debug(
                        "Could not verify stop order status",
                        trade_id=position.id,
                        stop_order_id=position.exchange_stop_order_id,
                        error=str(e),
                    )
            
            # Position is missing AND stop order is gone (or doesn't exist)
            # This could be:
            # 1. Catastrophe stop was hit (exit price ≈ catastrophe_sl)
            # 2. Normal exit via virtual TP/SL (exit price ≠ catastrophe_sl)
            # 3. Manual close
            
            # If position is missing and stop order is gone, it's likely a catastrophe stop
            # BUT we should verify the exit price matches the catastrophe stop price
            # Since we can't easily query trade history here, we'll log a warning
            # and let the normal flow handle it if it was a virtual TP/SL
            
            logger.warning(
                "Position missing from exchange - stop order also gone",
                trade_id=position.id,
                symbol=position.symbol,
                expected_qty=position.quantity,
                found_qty=exchange_position,
                catastrophe_sl=position.catastrophe_sl,
                note="Assuming catastrophe stop - verify exit price matches catastrophe_sl",
            )
            
            # Return CATASTROPHE_SL with the stop order (if available) to avoid re-fetching
            return (ExitReason.CATASTROPHE_SL, stop_order)
            
        except Exception as e:
            logger.error(
                "Failed to sync with exchange",
                trade_id=position.id,
                error=str(e),
            )
            return (None, None)
    
    def close_position(
        self,
        position: Position,
        reason: ExitReason,
        exit_price: Optional[float] = None,
    ) -> None:
        """
        Close a position and update database.
        
        Args:
            position: Position to close
            reason: Reason for closing
            exit_price: Target exit price (None for unknown exits like EXTERNAL_CLOSE)
        """
        try:
            # Skip execute_exit for EXTERNAL_CLOSE (position already sold externally)
            if reason != ExitReason.EXTERNAL_CLOSE:
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
        # Priority 1: Sync with exchange (detect catastrophe stop or external close)
        sync_reason, stop_order = self.sync_with_exchange(position)
        if sync_reason:
            # Handle EXTERNAL_CLOSE separately - close position to free limit, but mark for investigation
            if sync_reason == ExitReason.EXTERNAL_CLOSE:
                # Position was sold externally - close it to free position limit
                # Cancel orphaned stop order first
                if position.exchange_stop_order_id:
                    try:
                        self.exchange.cancel_order(position.symbol, position.exchange_stop_order_id)
                        logger.info(
                            "Cancelled orphaned stop order after external close",
                            trade_id=position.id,
                            stop_order_id=position.exchange_stop_order_id,
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed to cancel orphaned stop order",
                            trade_id=position.id,
                            stop_order_id=position.exchange_stop_order_id,
                            error=str(e),
                        )
                
                # Close position with None exit_price and PnL (unknown)
                # This frees the position limit while preserving investigation trail
                self.close_position(position, sync_reason, exit_price=None)
                return
            
            # Catastrophe stop was hit - try to get actual exit price from stop order
            exit_price = position.catastrophe_sl  # Default to catastrophe SL price
            
            # Use the stop order returned from sync_with_exchange (avoid re-fetching)
            # If stop order was filled, use the actual fill price
            if stop_order and stop_order.status == "closed":
                exit_price = stop_order.price
                logger.info(
                    "Catastrophe stop filled - using actual exit price",
                    trade_id=position.id,
                    stop_order_id=position.exchange_stop_order_id,
                    exit_price=exit_price,
                    catastrophe_sl=position.catastrophe_sl,
                )
            # Note: If stop_order.status == "open", sync_with_exchange() would have returned (None, None)
            # so we'd never reach this code. Only "closed" or None are possible here.
            
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

