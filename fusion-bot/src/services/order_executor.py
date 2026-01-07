"""
Order Executor Service for FusionBot
=====================================

Executes trades with the hybrid stop-loss system.
Handles entry logic with dual stop-loss protection.
"""

from typing import Optional
from datetime import datetime, timezone

from src.core.models import FusionDecision, TradeEntry, Position
from src.core.enums import TradeSide, TradeStatus
from src.core.exceptions import (
    OrderExecutionError,
    InsufficientBalanceError,
    PositionLimitError,
)
from src.infrastructure.exchange.base import ExchangeInterface
from src.infrastructure.database import get_session
from src.infrastructure.database.repositories import TradeRepository
from src.config import get_settings
from src.utils.logging import get_logger, trade_logger
from src.utils.helpers import calculate_position_size

logger = get_logger(__name__)


class OrderExecutor:
    """
    Executes trading orders with safety mechanisms.
    
    Entry flow:
        1. Validate position limits
        2. Calculate position size (risk-based)
        3. Execute market buy
        4. Place catastrophe stop loss on exchange
        5. Record virtual SL/TP in database
    
    Usage:
        executor = OrderExecutor(exchange)
        position = executor.execute_entry(decision)
    """
    
    def __init__(
        self,
        exchange: ExchangeInterface,
        dry_run: bool = None,
    ):
        """
        Initialize order executor.
        
        Args:
            exchange: Exchange client for order execution
            dry_run: If True, log but don't execute orders
        """
        self.settings = get_settings()
        self.exchange = exchange
        self.dry_run = dry_run if dry_run is not None else self.settings.dry_run
        
        # Risk parameters
        self.max_risk_per_trade = self.settings.max_risk_per_trade
        self.max_position_pct = self.settings.max_position_pct
        self.fee_rate = self.settings.trading_fee_rate
        self.max_open_positions = self.settings.max_open_positions
        self.virtual_sl_pct = self.settings.virtual_stop_loss_pct
        self.virtual_tp_pct = self.settings.virtual_take_profit_pct
        self.catastrophe_sl_pct = self.settings.catastrophe_stop_loss_pct
        
        logger.info(
            "Order executor initialized",
            dry_run=self.dry_run,
            max_risk=self.max_risk_per_trade,
            max_position_pct=self.max_position_pct,
            max_positions=self.max_open_positions,
        )
    
    def _check_position_limit(self) -> None:
        """Check if we can open another position."""
        with get_session() as session:
            repo = TradeRepository(session)
            open_count = repo.count_open()
            
            if open_count >= self.max_open_positions:
                raise PositionLimitError(open_count, self.max_open_positions)
    
    def _get_available_balance(self) -> float:
        """Get available USDT balance."""
        balance = self.exchange.get_balance("USDT")
        return balance.free
    
    def _calculate_entry(
        self,
        decision: FusionDecision,
        current_price: float,
        available_balance: float,
    ) -> TradeEntry:
        """
        Calculate trade entry parameters.
        
        Args:
            decision: The fusion decision
            current_price: Current market price
            available_balance: Available balance
        
        Returns:
            TradeEntry with calculated parameters
        """
        # Calculate stop loss price for position sizing
        stop_loss_price = current_price * (1 + self.virtual_sl_pct)  # virtual_sl_pct is negative
        
        # Calculate position size based on risk (with cap and fee adjustment)
        quantity = calculate_position_size(
            account_balance=available_balance,
            risk_per_trade=self.max_risk_per_trade,
            entry_price=current_price,
            stop_loss_price=stop_loss_price,
            max_position_pct=self.max_position_pct,
            fee_rate=self.fee_rate,
        )
        
        # Calculate target prices
        virtual_sl = current_price * (1 + self.virtual_sl_pct)
        virtual_tp = current_price * (1 + self.virtual_tp_pct)
        catastrophe_sl = current_price * (1 + self.catastrophe_sl_pct)
        
        # Ensure minimum order size (most exchanges have minimums)
        min_notional = 10.0  # $10 minimum
        if quantity * current_price < min_notional:
            quantity = min_notional / current_price
        
        return TradeEntry(
            symbol=decision.technicals.symbol,
            side=TradeSide.BUY,
            quantity=quantity,
            entry_price=current_price,
            virtual_sl=virtual_sl,
            virtual_tp=virtual_tp,
            catastrophe_sl=catastrophe_sl,
            news_id=decision.news_item.id,
            decision=decision,
        )
    
    def execute_entry(self, decision: FusionDecision) -> Optional[Position]:
        """
        Execute a trade entry.
        
        Args:
            decision: The fusion decision to execute
        
        Returns:
            Position object if successful, None otherwise
        """
        symbol = decision.technicals.symbol
        
        logger.info(
            "Executing trade entry",
            symbol=symbol,
            confidence=decision.confidence,
        )
        
        try:
            # Check position limit
            self._check_position_limit()
            
            # Get current price and balance
            ticker = self.exchange.get_ticker(symbol)
            current_price = ticker.last
            available_balance = self._get_available_balance()
            
            logger.info(
                "Entry parameters",
                symbol=symbol,
                price=current_price,
                available_balance=available_balance,
            )
            
            # Calculate entry
            entry = self._calculate_entry(decision, current_price, available_balance)
            
            if self.dry_run:
                logger.warning(
                    "DRY RUN - Order not executed",
                    symbol=symbol,
                    quantity=entry.quantity,
                    price=entry.entry_price,
                )
                return None
            
            # Step 1: Market Buy
            buy_result = self.exchange.market_buy(symbol, entry.quantity)
            
            logger.info(
                "Market buy executed",
                order_id=buy_result.order_id,
                fill_price=buy_result.price,
                quantity=buy_result.quantity,
            )
            
            # Step 2: Place Catastrophe Stop Loss
            stop_result = self.exchange.stop_loss_order(
                symbol=symbol,
                quantity=buy_result.quantity,
                stop_price=entry.catastrophe_sl,
            )
            
            logger.info(
                "Catastrophe stop loss placed",
                order_id=stop_result.order_id,
                stop_price=entry.catastrophe_sl,
            )
            
            # Step 3: Record in database
            with get_session() as session:
                repo = TradeRepository(session)
                trade = repo.create(
                    symbol=symbol,
                    side=TradeSide.BUY.value,
                    entry_price=buy_result.price,
                    quantity=buy_result.quantity,
                    virtual_sl=entry.virtual_sl,
                    virtual_tp=entry.virtual_tp,
                    catastrophe_sl=entry.catastrophe_sl,
                    entry_order_id=buy_result.order_id,
                    exchange_stop_order_id=stop_result.order_id,
                    news_id=entry.news_id,
                    reasoning=decision.reasoning,
                )
                
                position = Position(
                    id=trade.id,
                    symbol=symbol,
                    side=TradeSide.BUY,
                    entry_price=buy_result.price,
                    quantity=buy_result.quantity,
                    virtual_sl=entry.virtual_sl,
                    virtual_tp=entry.virtual_tp,
                    catastrophe_sl=entry.catastrophe_sl,
                    exchange_stop_order_id=stop_result.order_id,
                    status=TradeStatus.OPEN,
                    opened_at=datetime.now(timezone.utc),
                    news_id=entry.news_id,
                    reasoning=decision.reasoning,
                )
            
            trade_logger.log_entry(
                symbol=symbol,
                side="BUY",
                quantity=buy_result.quantity,
                price=buy_result.price,
                order_id=buy_result.order_id,
            )
            
            return position
            
        except PositionLimitError as e:
            logger.warning(
                "Position limit reached",
                current=e.current,
                max=e.maximum,
            )
            raise
            
        except InsufficientBalanceError as e:
            logger.error(
                "Insufficient balance",
                required=e.required,
                available=e.available,
            )
            raise
            
        except Exception as e:
            logger.error(
                "Trade execution failed",
                symbol=symbol,
                error=str(e),
            )
            raise OrderExecutionError(f"Entry failed: {e}", symbol=symbol)
    
    def execute_exit(
        self,
        position: Position,
        reason: str,
        at_price: Optional[float] = None,
    ) -> float:
        """
        Execute a position exit.
        
        Args:
            position: Position to close
            reason: Reason for closing
            at_price: Execute at this specific price (for consistent TP/SL execution)
        
        Returns:
            Exit price
        """
        symbol = position.symbol
        
        logger.info(
            "Executing position exit",
            trade_id=position.id,
            symbol=symbol,
            reason=reason,
        )
        
        if self.dry_run:
            price = at_price or self.exchange.get_ticker(symbol).last
            logger.warning(
                "DRY RUN - Exit not executed",
                symbol=symbol,
                price=price,
            )
            return price
        
        # Cancel the catastrophe stop order first
        if position.exchange_stop_order_id:
            try:
                self.exchange.cancel_order(symbol, position.exchange_stop_order_id)
                logger.info(
                    "Catastrophe stop cancelled",
                    order_id=position.exchange_stop_order_id,
                )
            except Exception as e:
                logger.warning(
                    "Failed to cancel stop order",
                    order_id=position.exchange_stop_order_id,
                    error=str(e),
                )
        
        # Execute market sell at specified price or current market
        sell_result = self.exchange.market_sell(symbol, position.quantity, at_price=at_price)
        
        logger.info(
            "Market sell executed",
            order_id=sell_result.order_id,
            fill_price=sell_result.price,
        )
        
        return sell_result.price

