"""
Technical Analyzer Service for FusionBot
=========================================

Computes technical indicators from OHLCV data.
Uses pandas_ta for indicator calculations.
"""

from typing import Optional, List
from datetime import datetime, timezone

import pandas as pd
import pandas_ta as ta

from src.core.models import TechnicalSignals
from src.core.enums import TrendDirection, RSIZone, MACDSignal
from src.infrastructure.exchange.base import ExchangeInterface, OHLCV
from src.config.constants import TA_PARAMS
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:
    """
    Computes technical analysis signals from market data.
    
    Indicators computed:
        - RSI (Relative Strength Index)
        - EMA (Exponential Moving Averages)
        - MACD (Moving Average Convergence Divergence)
        - ATR (Average True Range)
    
    Usage:
        analyzer = TechnicalAnalyzer(exchange)
        signals = analyzer.analyze("BTC/USDT")
        
        if signals.is_bullish and not signals.is_overbought:
            # Good entry opportunity
    """
    
    def __init__(
        self,
        exchange: ExchangeInterface,
        timeframe: str = None,
        candles_to_fetch: int = None,
    ):
        """
        Initialize technical analyzer.
        
        Args:
            exchange: Exchange for fetching OHLCV data
            timeframe: Candle timeframe (default: 4h)
            candles_to_fetch: Number of candles to fetch
        """
        self.exchange = exchange
        self.timeframe = timeframe or TA_PARAMS["candle_timeframe"]
        self.candles_to_fetch = candles_to_fetch or TA_PARAMS["candles_to_fetch"]
        
        # TA parameters
        self.rsi_period = TA_PARAMS["rsi_period"]
        self.rsi_overbought = TA_PARAMS["rsi_overbought"]
        self.rsi_oversold = TA_PARAMS["rsi_oversold"]
        self.ema_short = TA_PARAMS["ema_short"]
        self.ema_long = TA_PARAMS["ema_long"]
        self.macd_fast = TA_PARAMS["macd_fast"]
        self.macd_slow = TA_PARAMS["macd_slow"]
        self.macd_signal = TA_PARAMS["macd_signal"]
        self.atr_period = TA_PARAMS["atr_period"]
        
        logger.info(
            "Technical analyzer initialized",
            timeframe=self.timeframe,
            rsi_period=self.rsi_period,
        )
    
    def _candles_to_dataframe(self, candles: List[OHLCV]) -> pd.DataFrame:
        """Convert OHLCV list to pandas DataFrame."""
        data = {
            "timestamp": [c.timestamp for c in candles],
            "open": [c.open for c in candles],
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
            "volume": [c.volume for c in candles],
        }
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df
    
    def _classify_rsi(self, rsi: float) -> RSIZone:
        """Classify RSI into zones."""
        if rsi < self.rsi_oversold:
            return RSIZone.OVERSOLD
        elif rsi > self.rsi_overbought:
            return RSIZone.OVERBOUGHT
        else:
            return RSIZone.NEUTRAL
    
    def _determine_trend(
        self,
        ema_short: float,
        ema_long: float,
        current_price: float,
    ) -> TrendDirection:
        """
        Determine trend direction from EMAs.
        
        Bullish: Price above both EMAs, short EMA above long EMA
        Bearish: Price below both EMAs, short EMA below long EMA
        Neutral: Mixed signals
        """
        price_above_short = current_price > ema_short
        price_above_long = current_price > ema_long
        short_above_long = ema_short > ema_long
        
        if price_above_short and price_above_long and short_above_long:
            return TrendDirection.BULLISH
        elif not price_above_short and not price_above_long and not short_above_long:
            return TrendDirection.BEARISH
        else:
            return TrendDirection.NEUTRAL
    
    def _classify_macd(
        self,
        macd: float,
        signal: float,
        prev_macd: float,
        prev_signal: float,
    ) -> MACDSignal:
        """
        Classify MACD signal.
        
        Checks for crossovers and current positioning.
        """
        macd_above_signal = macd > signal
        prev_macd_above = prev_macd > prev_signal if prev_macd and prev_signal else macd_above_signal
        
        # Check for crossovers
        if macd_above_signal and not prev_macd_above:
            return MACDSignal.BULLISH_CROSS
        elif not macd_above_signal and prev_macd_above:
            return MACDSignal.BEARISH_CROSS
        elif macd_above_signal:
            return MACDSignal.BULLISH
        else:
            return MACDSignal.BEARISH
    
    def analyze(self, symbol: str) -> TechnicalSignals:
        """
        Perform technical analysis on a symbol.
        
        Args:
            symbol: Trading pair to analyze
        
        Returns:
            TechnicalSignals with computed indicators
        """
        logger.debug(f"Analyzing {symbol} with {self.timeframe} timeframe")
        
        # Fetch OHLCV data
        candles = self.exchange.get_ohlcv(
            symbol,
            timeframe=self.timeframe,
            limit=self.candles_to_fetch,
        )
        
        if len(candles) < self.ema_long:
            raise ValueError(f"Not enough candles: {len(candles)} < {self.ema_long}")
        
        # Convert to DataFrame
        df = self._candles_to_dataframe(candles)
        
        # Calculate indicators
        # RSI
        df["rsi"] = ta.rsi(df["close"], length=self.rsi_period)
        
        # EMAs
        df["ema_short"] = ta.ema(df["close"], length=self.ema_short)
        df["ema_long"] = ta.ema(df["close"], length=self.ema_long)
        
        # MACD
        macd_result = ta.macd(
            df["close"],
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal=self.macd_signal,
        )
        df["macd"] = macd_result.iloc[:, 0]  # MACD line
        df["macd_signal"] = macd_result.iloc[:, 1]  # Signal line
        df["macd_hist"] = macd_result.iloc[:, 2]  # Histogram
        
        # ATR
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=self.atr_period)
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = float(latest["close"])
        
        rsi = float(latest["rsi"])
        ema_short = float(latest["ema_short"])
        ema_long = float(latest["ema_long"])
        macd = float(latest["macd"])
        macd_signal = float(latest["macd_signal"])
        macd_hist = float(latest["macd_hist"])
        atr = float(latest["atr"])
        
        # Classify signals
        rsi_zone = self._classify_rsi(rsi)
        trend = self._determine_trend(ema_short, ema_long, current_price)
        macd_indication = self._classify_macd(
            macd, macd_signal,
            float(prev["macd"]), float(prev["macd_signal"]),
        )
        
        # ATR as percentage
        atr_percent = atr / current_price
        
        signals = TechnicalSignals(
            symbol=symbol,
            timeframe=self.timeframe,
            current_price=current_price,
            rsi=rsi,
            rsi_zone=rsi_zone,
            ema_short=ema_short,
            ema_long=ema_long,
            trend=trend,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_hist,
            macd_indication=macd_indication,
            atr=atr,
            atr_percent=atr_percent,
        )
        
        logger.info(
            "Technical analysis complete",
            symbol=symbol,
            price=current_price,
            rsi=round(rsi, 2),
            rsi_zone=str(rsi_zone),
            trend=str(trend),
            macd=str(macd_indication),
        )
        
        return signals
    
    def is_high_volatility(self, symbol: str, threshold_multiplier: float = 2.0) -> bool:
        """
        Check if current volatility is abnormally high.
        
        Args:
            symbol: Trading pair to check
            threshold_multiplier: ATR multiplier for "high" threshold
        
        Returns:
            True if volatility is high
        """
        try:
            candles = self.exchange.get_ohlcv(
                symbol,
                timeframe=self.timeframe,
                limit=50,
            )
            
            df = self._candles_to_dataframe(candles)
            df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=self.atr_period)
            
            current_atr = float(df["atr"].iloc[-1])
            avg_atr = float(df["atr"].mean())
            
            is_high = current_atr > (avg_atr * threshold_multiplier)
            
            if is_high:
                logger.warning(
                    "High volatility detected",
                    symbol=symbol,
                    current_atr=round(current_atr, 4),
                    avg_atr=round(avg_atr, 4),
                    ratio=round(current_atr / avg_atr, 2),
                )
            
            return is_high
            
        except Exception as e:
            logger.error(f"Failed to check volatility: {e}")
            return True  # Assume high volatility on error (conservative)

