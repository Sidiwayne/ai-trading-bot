"""
Paper Trading Exchange for FusionBot
=====================================

Simulated exchange for testing without real money.
Uses CCXT directly for public market data (no auth needed).
"""

import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict

import ccxt
from dataclasses import dataclass, field

from src.infrastructure.exchange.base import (
    ExchangeInterface,
    OrderResult,
    Balance,
    Ticker,
    OHLCV,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PaperPosition:
    """Simulated position."""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime


@dataclass
class PaperOrder:
    """Simulated order."""
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float
    stop_price: Optional[float] = None
    status: str = "open"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PaperExchange(ExchangeInterface):
    """
    Paper trading exchange that simulates real trading.
    
    Uses real market data from Binance but simulates order execution.
    Perfect for testing strategies without risking real money.
    
    Usage:
        paper = PaperExchange(initial_balance=10000)
        paper.market_buy("BTC/USDT", 0.1)
    """
    
    def __init__(
        self,
        initial_balance: float = 10000.0,
        fee_rate: float = 0.001,  # 0.1% fee
    ):
        """
        Initialize paper exchange.
        
        Args:
            initial_balance: Starting USDT balance
            fee_rate: Trading fee rate
        """
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        
        # Simulated state
        self._balances: Dict[str, float] = {"USDT": initial_balance}
        self._positions: Dict[str, PaperPosition] = {}
        self._orders: Dict[str, PaperOrder] = {}
        self._trade_history: List[OrderResult] = []
        
        # Real market data source (CCXT directly, no auth needed for public data)
        self._ccxt: Optional[ccxt.binance] = None
        
        logger.info(
            "Paper exchange initialized",
            initial_balance=initial_balance,
            fee_rate=fee_rate,
        )
    
    def _get_ccxt(self) -> ccxt.binance:
        """Get or create CCXT client for public market data."""
        if self._ccxt is None:
            # Use CCXT directly for public data - no credentials needed
            self._ccxt = ccxt.binance({
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
            try:
                self._ccxt.load_markets()
                logger.info("CCXT market data initialized", markets=len(self._ccxt.markets))
            except Exception as e:
                logger.warning(f"Failed to load markets, will use fallback prices: {e}")
        return self._ccxt
    
    def _generate_order_id(self) -> str:
        """Generate a unique order ID."""
        return f"PAPER-{uuid.uuid4().hex[:12].upper()}"
    
    def get_balance(self, currency: str = "USDT") -> Balance:
        """Get simulated balance."""
        total = self._balances.get(currency, 0.0)
        return Balance(
            currency=currency,
            free=total,
            used=0.0,  # Simplified - no locked funds
            total=total,
        )
    
    def get_ticker(self, symbol: str) -> Ticker:
        """Get real ticker from Binance public API."""
        try:
            ccxt_client = self._get_ccxt()
            ticker_data = ccxt_client.fetch_ticker(symbol)
            return Ticker(
                symbol=symbol,
                bid=float(ticker_data.get("bid", 0)),
                ask=float(ticker_data.get("ask", 0)),
                last=float(ticker_data.get("last", 0)),
                volume=float(ticker_data.get("quoteVolume", 0)),
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            # Fallback to mock prices for testing
            mock_prices = {"BTC/USDT": 95000, "ETH/USDT": 3500}
            price = mock_prices.get(symbol, 100)
            return Ticker(
                symbol=symbol,
                bid=price * 0.999,
                ask=price * 1.001,
                last=price,
                volume=0,
                timestamp=datetime.now(timezone.utc),
            )
    
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "4h",
        limit: int = 100,
    ) -> List[OHLCV]:
        """Get real OHLCV from Binance public API."""
        try:
            ccxt_client = self._get_ccxt()
            ohlcv_data = ccxt_client.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                OHLCV(
                    timestamp=datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc),
                    open=float(candle[1]),
                    high=float(candle[2]),
                    low=float(candle[3]),
                    close=float(candle[4]),
                    volume=float(candle[5]),
                )
                for candle in ohlcv_data
            ]
        except Exception as e:
            logger.error(f"Failed to get OHLCV for {symbol}: {e}")
            # Return empty list - TA will handle gracefully
            return []
    
    def market_buy(self, symbol: str, quantity: float) -> OrderResult:
        """Simulate market buy order."""
        ticker = self.get_ticker(symbol)
        price = ticker.ask  # Buy at ask price
        
        # Calculate cost with fee
        cost = quantity * price
        fee = cost * self.fee_rate
        total_cost = cost + fee
        
        # Check balance
        usdt_balance = self._balances.get("USDT", 0)
        if usdt_balance < total_cost:
            from src.core.exceptions import InsufficientBalanceError
            logger.warning(
                "Paper trade rejected: insufficient balance",
                required=total_cost,
                available=usdt_balance,
            )
            raise InsufficientBalanceError(
                required=total_cost,
                available=usdt_balance,
                currency="USDT"
            )
        
        # Execute trade
        base_currency = symbol.split("/")[0]
        
        self._balances["USDT"] = usdt_balance - total_cost
        self._balances[base_currency] = self._balances.get(base_currency, 0) + quantity
        
        # Record position
        self._positions[symbol] = PaperPosition(
            symbol=symbol,
            quantity=quantity,
            entry_price=price,
            entry_time=datetime.now(timezone.utc),
        )
        
        order_id = self._generate_order_id()
        result = OrderResult(
            order_id=order_id,
            symbol=symbol,
            side="buy",
            order_type="market",
            quantity=quantity,
            price=price,
            status="closed",
            timestamp=datetime.now(timezone.utc),
            fee=fee,
            fee_currency="USDT",
        )
        
        self._trade_history.append(result)
        
        logger.info(
            "📝 Paper BUY executed",
            symbol=symbol,
            quantity=quantity,
            price=price,
            cost=total_cost,
            new_balance=self._balances["USDT"],
        )
        
        return result
    
    def market_sell(self, symbol: str, quantity: float, at_price: Optional[float] = None) -> OrderResult:
        """Simulate market sell order."""
        if at_price is not None:
            # Use specified price (for consistent TP/SL execution)
            price = at_price
        else:
            # Use current market bid price
            ticker = self.get_ticker(symbol)
            price = ticker.bid
        
        # Calculate proceeds with fee
        proceeds = quantity * price
        fee = proceeds * self.fee_rate
        net_proceeds = proceeds - fee
        
        base_currency = symbol.split("/")[0]
        
        # Execute trade
        self._balances["USDT"] = self._balances.get("USDT", 0) + net_proceeds
        self._balances[base_currency] = max(0, self._balances.get(base_currency, 0) - quantity)
        
        # Clear position if fully sold
        if symbol in self._positions:
            pos = self._positions[symbol]
            if self._balances[base_currency] <= 0.00001:
                del self._positions[symbol]
        
        order_id = self._generate_order_id()
        result = OrderResult(
            order_id=order_id,
            symbol=symbol,
            side="sell",
            order_type="market",
            quantity=quantity,
            price=price,
            status="closed",
            timestamp=datetime.now(timezone.utc),
            fee=fee,
            fee_currency="USDT",
        )
        
        self._trade_history.append(result)
        
        logger.info(
            "📝 Paper SELL executed",
            symbol=symbol,
            quantity=quantity,
            price=price,
            proceeds=net_proceeds,
            new_balance=self._balances["USDT"],
        )
        
        return result
    
    def stop_loss_order(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
    ) -> OrderResult:
        """Simulate stop loss order (stored but not executed until triggered)."""
        order_id = self._generate_order_id()
        
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            side="sell",
            order_type="stop_loss",
            quantity=quantity,
            price=stop_price,
            stop_price=stop_price,
            status="open",
        )
        
        self._orders[order_id] = order
        
        logger.info(
            "📝 Paper STOP LOSS placed",
            order_id=order_id,
            symbol=symbol,
            quantity=quantity,
            stop_price=stop_price,
        )
        
        return OrderResult(
            order_id=order_id,
            symbol=symbol,
            side="sell",
            order_type="stop_loss",
            quantity=quantity,
            price=stop_price,
            status="open",
            timestamp=datetime.now(timezone.utc),
        )
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel a paper order."""
        if order_id in self._orders:
            self._orders[order_id].status = "canceled"
            del self._orders[order_id]
            logger.info("📝 Paper order cancelled", order_id=order_id)
            return True
        return False
    
    def get_order(self, symbol: str, order_id: str) -> Optional[OrderResult]:
        """Get paper order details."""
        if order_id in self._orders:
            o = self._orders[order_id]
            return OrderResult(
                order_id=o.order_id,
                symbol=o.symbol,
                side=o.side,
                order_type=o.order_type,
                quantity=o.quantity,
                price=o.price,
                status=o.status,
                timestamp=o.created_at,
            )
        return None
    
    def get_open_orders(self, symbol: str = None) -> List[OrderResult]:
        """Get all open paper orders."""
        results = []
        for o in self._orders.values():
            if o.status == "open":
                if symbol is None or o.symbol == symbol:
                    results.append(OrderResult(
                        order_id=o.order_id,
                        symbol=o.symbol,
                        side=o.side,
                        order_type=o.order_type,
                        quantity=o.quantity,
                        price=o.price,
                        status=o.status,
                        timestamp=o.created_at,
                    ))
        return results
    
    def get_position(self, symbol: str) -> Optional[float]:
        """Get current position size."""
        base_currency = symbol.split("/")[0]
        balance = self._balances.get(base_currency, 0)
        return balance if balance > 0.00001 else None
    
    def health_check(self) -> bool:
        """Always healthy for paper trading."""
        return True
    
    def check_stop_orders(self) -> List[OrderResult]:
        """
        Check if any stop loss orders should be triggered.
        
        Call this periodically to simulate stop order execution.
        
        Returns:
            List of triggered orders
        """
        triggered = []
        
        for order_id, order in list(self._orders.items()):
            if order.status != "open" or order.order_type != "stop_loss":
                continue
            
            try:
                ticker = self.get_ticker(order.symbol)
                
                # Stop loss triggers when price falls to or below stop price
                if ticker.last <= order.stop_price:
                    logger.warning(
                        "📝 Paper STOP LOSS triggered!",
                        order_id=order_id,
                        symbol=order.symbol,
                        stop_price=order.stop_price,
                        current_price=ticker.last,
                    )
                    
                    # Execute the sell
                    result = self.market_sell(order.symbol, order.quantity)
                    
                    # Remove the stop order
                    del self._orders[order_id]
                    
                    triggered.append(result)
            
            except Exception as e:
                logger.error(
                    "Error checking stop order",
                    order_id=order_id,
                    error=str(e),
                )
        
        return triggered
    
    def get_equity(self) -> float:
        """Get total account equity in USDT."""
        equity = self._balances.get("USDT", 0)
        
        for symbol, position in self._positions.items():
            try:
                ticker = self.get_ticker(symbol)
                equity += position.quantity * ticker.last
            except Exception:
                # If can't get price, use entry price
                equity += position.quantity * position.entry_price
        
        return equity
    
    def get_pnl(self) -> Dict[str, float]:
        """Get P&L statistics."""
        equity = self.get_equity()
        pnl_amount = equity - self.initial_balance
        pnl_percent = pnl_amount / self.initial_balance
        
        return {
            "initial_balance": self.initial_balance,
            "current_equity": equity,
            "pnl_amount": pnl_amount,
            "pnl_percent": pnl_percent,
            "total_trades": len(self._trade_history),
        }
    
    def reset(self) -> None:
        """Reset paper exchange to initial state."""
        self._balances = {"USDT": self.initial_balance}
        self._positions.clear()
        self._orders.clear()
        self._trade_history.clear()
        logger.info("Paper exchange reset", initial_balance=self.initial_balance)

