"""
Binance Exchange Client for FusionBot
======================================

CCXT-based Binance Spot trading implementation.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import ccxt

from src.infrastructure.exchange.base import (
    ExchangeInterface,
    OrderResult,
    Balance,
    Ticker,
    OHLCV,
)
from src.core.exceptions import (
    ExchangeError,
    ExchangeConnectionError,
    OrderExecutionError,
    InsufficientBalanceError,
    RateLimitError,
)
from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.retry import with_retry, RetryConfig
from src.services.notifier import get_notifier

logger = get_logger(__name__)


class BinanceClient(ExchangeInterface):
    """
    Binance Spot exchange client using CCXT.
    
    Supports both mainnet and testnet.
    
    Usage:
        client = BinanceClient(api_key, api_secret, testnet=True)
        ticker = client.get_ticker("BTC/USDC")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True,
    ):
        """
        Initialize Binance client.
        
        Args:
            api_key: Binance API key (defaults to settings)
            api_secret: Binance API secret (defaults to settings)
            testnet: Use testnet if True
        """
        settings = get_settings()
        
        api_key = api_key or settings.binance_api_key
        api_secret = api_secret or settings.binance_api_secret
        testnet = testnet if testnet is not None else settings.binance_testnet
        
        # Initialize CCXT Binance
        exchange_config = {
            "apiKey": api_key,
            "secret": api_secret,
            "sandbox": testnet,
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
                "adjustForTimeDifference": True,
            },
        }
        
        self.exchange = ccxt.binance(exchange_config)
        self.testnet = testnet
        
        # Create separate PUBLIC exchange for market data (always real Binance)
        # This ensures we get real OHLCV data even when using testnet for trading
        self._public_exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        
        # Load markets
        try:
            self.exchange.load_markets()
            self._public_exchange.load_markets()
            logger.info(
                "Binance client initialized",
                testnet=testnet,
                markets_loaded=len(self.exchange.markets),
                public_data="real Binance (not testnet)",
            )
        except Exception as e:
            logger.error("Failed to load Binance markets", error=str(e))
            # Send notification for exchange connection failure
            notifier = get_notifier()
            if notifier:
                notifier.send_exchange_error(
                    operation="Initialize Binance Client",
                    error=f"Failed to load markets: {str(e)[:200]}",
                )
            raise ExchangeConnectionError(f"Failed to connect to Binance: {e}")
    
    def _handle_error(self, e: Exception, operation: str) -> None:
        """Convert CCXT exceptions to our exceptions."""
        error_str = str(e)
        notifier = get_notifier()
        
        if isinstance(e, ccxt.InsufficientFunds):
            # Log the actual Binance error to understand what's really wrong
            logger.error(
                "Binance InsufficientFunds error (may be misleading)",
                operation=operation,
                error_message=error_str,
                note="This might not actually be a balance issue - check Binance error details",
            )
            # Try to extract balance info from error if available
            # CCXT InsufficientFunds might have balance info in the exception
            raise InsufficientBalanceError(0, 0, "USDC")
        elif isinstance(e, ccxt.RateLimitExceeded):
            # Send notification for rate limit errors
            if notifier:
                notifier.send_exchange_error(
                    operation=operation,
                    error=f"Rate limit exceeded: {error_str[:200]}",
                )
            raise RateLimitError()
        elif isinstance(e, ccxt.NetworkError):
            # Send notification for network errors
            if notifier:
                notifier.send_exchange_error(
                    operation=operation,
                    error=f"Network error: {error_str[:200]}",
                )
            raise ExchangeConnectionError(f"{operation} failed: {error_str}")
        elif isinstance(e, ccxt.AuthenticationError):
            # Send notification for authentication failures (critical)
            if notifier:
                notifier.send_exchange_error(
                    operation=operation,
                    error=f"Authentication failed: {error_str[:200]}",
                )
            raise ExchangeError(f"{operation} failed: Authentication error")
        elif isinstance(e, ccxt.ExchangeError):
            # Send notification for general exchange errors
            if notifier:
                notifier.send_exchange_error(
                    operation=operation,
                    error=f"Exchange error: {error_str[:200]}",
                )
            raise ExchangeError(f"{operation} failed: {error_str}")
        else:
            # Send notification for unexpected errors
            if notifier:
                notifier.send_exchange_error(
                    operation=operation,
                    error=f"Unexpected error: {error_str[:200]}",
                )
            raise ExchangeError(f"Unexpected error in {operation}: {error_str}")
    
    @with_retry(RetryConfig(max_attempts=3))
    def get_balance(self, currency: str = "USDC") -> Balance:
        """Get account balance."""
        try:
            balance = self.exchange.fetch_balance()
            
            if currency not in balance:
                return Balance(currency=currency, free=0, used=0, total=0)
            
            curr_balance = balance[currency]
            return Balance(
                currency=currency,
                free=float(curr_balance.get("free", 0) or 0),
                used=float(curr_balance.get("used", 0) or 0),
                total=float(curr_balance.get("total", 0) or 0),
            )
        except Exception as e:
            self._handle_error(e, "get_balance")
    
    @with_retry(RetryConfig(max_attempts=3))
    def get_ticker(self, symbol: str) -> Ticker:
        """Get current ticker from REAL Binance (public data)."""
        try:
            # Use public exchange for real market data (even on testnet)
            ticker = self._public_exchange.fetch_ticker(symbol)
            
            return Ticker(
                symbol=symbol,
                bid=float(ticker.get("bid", 0) or 0),
                ask=float(ticker.get("ask", 0) or 0),
                last=float(ticker.get("last", 0) or 0),
                volume=float(ticker.get("quoteVolume", 0) or 0),
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            self._handle_error(e, "get_ticker")
    
    @with_retry(RetryConfig(max_attempts=3))
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "4h",
        limit: int = 100,
    ) -> List[OHLCV]:
        """Get OHLCV candlestick data from REAL Binance (public data)."""
        try:
            # Use public exchange for real market data (even on testnet)
            candles = self._public_exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit,
            )
            
            return [
                OHLCV(
                    timestamp=datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc),
                    open=float(c[1]),
                    high=float(c[2]),
                    low=float(c[3]),
                    close=float(c[4]),
                    volume=float(c[5]),
                )
                for c in candles
            ]
        except Exception as e:
            self._handle_error(e, "get_ohlcv")
    
    def market_buy(self, symbol: str, quantity: float) -> OrderResult:
        """Execute market buy order."""
        try:
            logger.info(
                "Executing market buy",
                symbol=symbol,
                quantity=quantity,
            )
            
            order = self.exchange.create_market_buy_order(symbol, quantity)
            
            result = OrderResult(
                order_id=str(order["id"]),
                symbol=symbol,
                side="buy",
                order_type="market",
                quantity=float(order.get("filled", quantity)),
                price=float(order.get("average", 0) or order.get("price", 0) or 0),
                status=order.get("status", "closed"),
                timestamp=datetime.now(timezone.utc),
                fee=float(order.get("fee", {}).get("cost", 0) or 0),
                fee_currency=order.get("fee", {}).get("currency"),
                raw=order,
            )
            
            logger.info(
                "Market buy executed",
                order_id=result.order_id,
                fill_price=result.price,
            )
            
            return result
        
        except Exception as e:
            self._handle_error(e, "market_buy")
    
    def market_sell(self, symbol: str, quantity: float, at_price: Optional[float] = None) -> OrderResult:
        """Execute market sell order (at_price ignored - real exchange uses market price)."""
        try:
            logger.info(
                "Executing market sell",
                symbol=symbol,
                quantity=quantity,
            )
            
            order = self.exchange.create_market_sell_order(symbol, quantity)
            
            result = OrderResult(
                order_id=str(order["id"]),
                symbol=symbol,
                side="sell",
                order_type="market",
                quantity=float(order.get("filled", quantity)),
                price=float(order.get("average", 0) or order.get("price", 0) or 0),
                status=order.get("status", "closed"),
                timestamp=datetime.now(timezone.utc),
                fee=float(order.get("fee", {}).get("cost", 0) or 0),
                fee_currency=order.get("fee", {}).get("currency"),
                raw=order,
            )
            
            logger.info(
                "Market sell executed",
                order_id=result.order_id,
                fill_price=result.price,
            )
            
            return result
        
        except Exception as e:
            self._handle_error(e, "market_sell")
    
    def stop_loss_order(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
    ) -> OrderResult:
        """Place a stop loss order."""
        try:
            logger.info(
                "Placing stop loss order",
                symbol=symbol,
                quantity=quantity,
                stop_price=stop_price,
            )
            
            # Binance uses STOP_LOSS_LIMIT, need a limit price slightly below stop
            limit_price = stop_price * 0.995  # 0.5% below stop
            
            order = self.exchange.create_order(
                symbol=symbol,
                type="STOP_LOSS_LIMIT",
                side="sell",
                amount=quantity,
                price=limit_price,
                params={
                    "stopPrice": stop_price,
                    "timeInForce": "GTC",
                },
            )
            
            result = OrderResult(
                order_id=str(order["id"]),
                symbol=symbol,
                side="sell",
                order_type="stop_loss",
                quantity=quantity,
                price=stop_price,
                status=order.get("status", "open"),
                timestamp=datetime.now(timezone.utc),
                raw=order,
            )
            
            logger.info(
                "Stop loss order placed",
                order_id=result.order_id,
                stop_price=stop_price,
            )
            
            return result
        
        except Exception as e:
            # Log the actual error before handling to see what Binance really said
            logger.error(
                "Stop loss order placement failed",
                symbol=symbol,
                quantity=quantity,
                stop_price=stop_price,
                limit_price=limit_price,
                error_type=type(e).__name__,
                error_message=str(e),
                raw_error=repr(e),
            )
            self._handle_error(e, "stop_loss_order")
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an open order."""
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info("Order cancelled", order_id=order_id, symbol=symbol)
            return True
        except ccxt.OrderNotFound:
            logger.warning("Order not found for cancellation", order_id=order_id)
            return False
        except Exception as e:
            self._handle_error(e, "cancel_order")
    
    def get_order(self, symbol: str, order_id: str) -> Optional[OrderResult]:
        """Get order details."""
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            
            return OrderResult(
                order_id=str(order["id"]),
                symbol=symbol,
                side=order.get("side", ""),
                order_type=order.get("type", ""),
                quantity=float(order.get("amount", 0)),
                price=float(order.get("average", 0) or order.get("price", 0) or 0),
                status=order.get("status", ""),
                timestamp=datetime.now(timezone.utc),
                raw=order,
            )
        except ccxt.OrderNotFound:
            return None
        except Exception as e:
            self._handle_error(e, "get_order")
    
    def get_open_orders(self, symbol: str = None) -> List[OrderResult]:
        """Get all open orders."""
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            
            return [
                OrderResult(
                    order_id=str(o["id"]),
                    symbol=o.get("symbol", ""),
                    side=o.get("side", ""),
                    order_type=o.get("type", ""),
                    quantity=float(o.get("amount", 0)),
                    price=float(o.get("price", 0) or 0),
                    status=o.get("status", "open"),
                    timestamp=datetime.now(timezone.utc),
                    raw=o,
                )
                for o in orders
            ]
        except Exception as e:
            self._handle_error(e, "get_open_orders")
    
    def get_position(self, symbol: str) -> Optional[float]:
        """Get current position size (balance of base currency)."""
        try:
            # Extract base currency from symbol (e.g., BTC from BTC/USDC)
            base = symbol.split("/")[0]
            balance = self.get_balance(base)
            
            if balance.total > 0:
                return balance.total
            return None
        except Exception:
            return None
    
    def health_check(self) -> bool:
        """Check exchange connectivity."""
        try:
            self.exchange.fetch_time()
            return True
        except Exception as e:
            logger.error("Binance health check failed", error=str(e))
            return False

