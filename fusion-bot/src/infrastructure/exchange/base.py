"""
Exchange Interface for FusionBot
=================================

Abstract base class defining the exchange API contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class OrderResult:
    """Result of an order execution."""
    
    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', 'stop_loss'
    quantity: float
    price: float  # Fill price for market orders
    status: str  # 'open', 'closed', 'canceled'
    timestamp: datetime
    fee: Optional[float] = None
    fee_currency: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None  # Raw exchange response


@dataclass
class Balance:
    """Account balance for a currency."""
    
    currency: str
    free: float  # Available balance
    used: float  # In orders
    total: float  # free + used


@dataclass
class Ticker:
    """Current ticker data."""
    
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime


@dataclass
class OHLCV:
    """Candlestick data."""
    
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class ExchangeInterface(ABC):
    """
    Abstract interface for exchange operations.
    
    Implementations must provide all abstract methods.
    This allows swapping between live and paper trading.
    """
    
    @abstractmethod
    def get_balance(self, currency: str = "USDC") -> Balance:
        """
        Get account balance for a currency.
        
        Args:
            currency: Currency code (e.g., 'USDC', 'BTC')
        
        Returns:
            Balance object
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """
        Get current ticker for a symbol.
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDC')
        
        Returns:
            Ticker object
        """
        pass
    
    @abstractmethod
    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "4h",
        limit: int = 100,
    ) -> List[OHLCV]:
        """
        Get OHLCV candlestick data.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 1h, 4h, 1d)
            limit: Number of candles
        
        Returns:
            List of OHLCV objects
        """
        pass
    
    @abstractmethod
    def market_buy(
        self,
        symbol: str,
        quantity: float,
    ) -> OrderResult:
        """
        Execute a market buy order.
        
        Args:
            symbol: Trading pair
            quantity: Amount to buy (in base currency)
        
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def market_sell(
        self,
        symbol: str,
        quantity: float,
        at_price: Optional[float] = None,
    ) -> OrderResult:
        """
        Execute a market sell order.
        
        Args:
            symbol: Trading pair
            quantity: Amount to sell
            at_price: Execute at this price (paper trading only, ignored for real exchange)
        
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def stop_loss_order(
        self,
        symbol: str,
        quantity: float,
        stop_price: float,
    ) -> OrderResult:
        """
        Place a stop loss order.
        
        Args:
            symbol: Trading pair
            quantity: Amount to sell when triggered
            stop_price: Trigger price
        
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def cancel_order(
        self,
        symbol: str,
        order_id: str,
    ) -> bool:
        """
        Cancel an open order.
        
        Args:
            symbol: Trading pair
            order_id: Order to cancel
        
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    def get_order(
        self,
        symbol: str,
        order_id: str,
    ) -> Optional[OrderResult]:
        """
        Get order details.
        
        Args:
            symbol: Trading pair
            order_id: Order ID
        
        Returns:
            OrderResult or None if not found
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: str = None) -> List[OrderResult]:
        """
        Get all open orders.
        
        Args:
            symbol: Optional filter by symbol
        
        Returns:
            List of open orders
        """
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional[float]:
        """
        Get current position size for a symbol.
        
        Args:
            symbol: Trading pair
        
        Returns:
            Position size or None if no position
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Check exchange connectivity.
        
        Returns:
            True if healthy
        """
        pass

