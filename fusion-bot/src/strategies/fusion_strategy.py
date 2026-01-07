"""
Fusion Strategy for FusionBot
==============================

Main trading strategy with FULL CONTEXT philosophy:
- Hard limits enforced in CODE
- Macro climate provided as CONTEXT to AI (not binary block)
- Crypto news + technicals + macro → AI makes holistic decision
- Code can veto after AI decision (catastrophes only)
"""

from typing import Optional, List, Tuple
from datetime import datetime, timezone

from src.core.models import NewsItem, TechnicalSignals, Position
from src.core.enums import TradeAction, SystemMode, TradeSide, TradeStatus, NewsStatus
from src.core.exceptions import PositionLimitError
from src.infrastructure.exchange.base import ExchangeInterface
from src.infrastructure.database import get_session
from src.infrastructure.database.repositories import TradeRepository
from src.services.news_aggregator import NewsAggregator
from src.services.macro_context import MacroContext  # NEW: Context, not Guard
from src.services.technical_analyzer import TechnicalAnalyzer
from src.services.trading_brain import TradingBrain, TradingDecision
from src.services.order_executor import OrderExecutor
from src.services.position_manager import PositionManager
from src.config import get_settings
from src.utils.logging import get_logger, trade_logger

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# HARD LIMITS - Enforced in CODE, not prompt
# ════════════════════════════════════════════════════════════════════════════

class HardLimits:
    """
    Non-negotiable safety limits enforced programmatically.
    AI never even sees opportunities that violate these.
    
    Split into:
    - Symbol-level checks (technicals) - run ONCE per symbol
    - News-level checks (age) - run per news item
    """
    
    # Absolute RSI limits (AI gets context for gray zone)
    RSI_EXTREME_OVERBOUGHT = 85  # Never buy above this
    RSI_EXTREME_OVERSOLD = 15    # Might be falling knife
    
    # Minimum confidence from AI to execute
    MIN_CONFIDENCE = 60
    
    # News age limits
    MAX_NEWS_AGE_HOURS = 6
    
    # Price movement since news (chase prevention)
    MAX_PRICE_MOVE_PCT = 0.03  # 3%
    
    @classmethod
    def check_symbol(
        cls,
        technicals: TechnicalSignals,
    ) -> Tuple[bool, Optional[NewsStatus], Optional[str]]:
        """
        Symbol-level hard limits (technicals).
        Run ONCE per symbol - rejects ALL news for that symbol if failed.
        
        Returns:
            (is_valid, status_if_rejected, reason)
        """
        if technicals.rsi > cls.RSI_EXTREME_OVERBOUGHT:
            return (
                False,
                NewsStatus.HARD_LIMIT_RSI,
                f"RSI {technicals.rsi:.1f} > {cls.RSI_EXTREME_OVERBOUGHT} (extreme overbought)"
            )
        
        if technicals.rsi < cls.RSI_EXTREME_OVERSOLD:
            return (
                False,
                NewsStatus.HARD_LIMIT_RSI,
                f"RSI {technicals.rsi:.1f} < {cls.RSI_EXTREME_OVERSOLD} (potential falling knife)"
            )
        
        return True, None, None
    
    @classmethod
    def check_news(
        cls,
        news: NewsItem,
    ) -> Tuple[bool, Optional[NewsStatus], Optional[str]]:
        """
        News-level hard limits (age, etc).
        Run per news item.
        
        Returns:
            (is_valid, status_if_rejected, reason)
        """
        if news.published_at:
            age_hours = (datetime.now(timezone.utc) - news.published_at).total_seconds() / 3600
            if age_hours > cls.MAX_NEWS_AGE_HOURS:
                return (
                    False,
                    NewsStatus.HARD_LIMIT_AGE,
                    f"News is {age_hours:.1f}h old (max {cls.MAX_NEWS_AGE_HOURS}h)"
                )
        
        return True, None, None
    
    @classmethod
    def check_post_ai(
        cls,
        decision: TradingDecision,
        technicals: TechnicalSignals,
    ) -> Tuple[bool, Optional[NewsStatus], Optional[str]]:
        """
        Post-AI sanity checks. Can veto AI's decision.
        
        Returns:
            (is_valid, status_if_rejected, reason)
        """
        if decision.action != TradeAction.BUY:
            return True, None, None  # Only check BUY decisions
        
        # Confidence too low
        if decision.confidence < cls.MIN_CONFIDENCE:
            return (
                False,
                NewsStatus.VETO_CONFIDENCE,
                f"AI confidence {decision.confidence} < {cls.MIN_CONFIDENCE} minimum"
            )
        
        # AI said noise but still recommended BUY (sanity check)
        if decision.catalyst_strength == "noise":
            return (
                False,
                NewsStatus.VETO_INCONSISTENT,
                "AI classified catalyst as noise but recommended BUY (inconsistent)"
            )
        
        return True, None, None


class FusionStrategy:
    """
    Main trading strategy with FULL CONTEXT AI decision making.
    
    Philosophy:
        - Hard limits in CODE (pre/post AI)
        - Macro climate as CONTEXT (not binary block)
        - ONE AI call with macro + crypto + technicals
        - AI weighs all factors holistically
        - Only TRUE CATASTROPHES block in code
    """
    
    def __init__(
        self,
        exchange: ExchangeInterface,
        news_aggregator: Optional[NewsAggregator] = None,
        macro_context: Optional[MacroContext] = None,
        technical_analyzer: Optional[TechnicalAnalyzer] = None,
        trading_brain: Optional[TradingBrain] = None,
        order_executor: Optional[OrderExecutor] = None,
        position_manager: Optional[PositionManager] = None,
    ):
        """Initialize the fusion strategy."""
        self.settings = get_settings()
        self.exchange = exchange
        
        # Initialize services
        self.news_aggregator = news_aggregator or NewsAggregator()
        self.macro_context = macro_context or MacroContext()  # NEW: Context, not Guard
        self.technical_analyzer = technical_analyzer or TechnicalAnalyzer(exchange)
        self.trading_brain = trading_brain or TradingBrain()
        self.order_executor = order_executor or OrderExecutor(exchange)
        self.position_manager = position_manager or PositionManager(
            exchange, self.order_executor
        )
        
        # State
        self._mode = SystemMode.ACTIVE
        self._last_cycle_time: Optional[datetime] = None
        self._last_trade_time: Optional[datetime] = None
        self._cycle_count = 0
        self._cached_macro_climate: Optional[str] = None
        
        logger.info("Fusion strategy initialized (macro-aware AI mode)")
    
    @property
    def mode(self) -> SystemMode:
        """Get current system mode."""
        return self._mode
    
    def _is_in_cooldown(self) -> bool:
        """Check if we're in trade cooldown period."""
        if self._last_trade_time is None:
            return False
        
        cooldown_minutes = self.settings.trade_cooldown_minutes
        if cooldown_minutes <= 0:
            return False
        
        elapsed = (datetime.now(timezone.utc) - self._last_trade_time).total_seconds() / 60
        return elapsed < cooldown_minutes
    
    def _manage_positions(self) -> None:
        """Manage existing positions. Always runs."""
        try:
            self.position_manager.check_all_positions()
        except Exception as e:
            logger.error(f"Position management error: {e}")
    
    def _gather_macro_context(self) -> Tuple[bool, str]:
        """
        Gather macro-economic context for AI decision.
        
        Returns:
            (is_catastrophe, macro_climate_text)
            - is_catastrophe: True only for TRUE disasters (code-level block)
            - macro_climate_text: Formatted headlines for AI prompt
        """
        try:
            climate = self.macro_context.get_current_climate()
            
            # Only TRUE CATASTROPHES trigger code-level block
            if climate.is_catastrophe:
                self._mode = SystemMode.DEFENSIVE
                self.macro_context.record_catastrophe(
                    keyword=climate.catastrophe_reason.split(":")[0] if climate.catastrophe_reason else "unknown",
                    headline=climate.catastrophe_reason or "Unknown catastrophe",
                    source="macro_scan",
                )
                logger.error(f"🚨 CATASTROPHE: {climate.catastrophe_reason}")
                return True, climate.to_prompt_section()
            
            # Normal macro context - pass to AI
            self._mode = SystemMode.ACTIVE
            self._cached_macro_climate = climate.to_prompt_section()
            
            if climate.headlines:
                logger.info(f"Macro context: {len(climate.headlines)} relevant headlines gathered")
            
            return False, self._cached_macro_climate
            
        except Exception as e:
            logger.error(f"Macro context error: {e}")
            # On error, continue with empty context (don't block)
            return False, "Macro data unavailable."
    
    def _gather_opportunities(self) -> List[Tuple[NewsItem, TechnicalSignals]]:
        """
        Gather all potential opportunities with their technicals.
        Applies PRE-AI hard limits.
        
        Returns:
            List of (NewsItem, TechnicalSignals) pairs that pass hard limits
        """
        opportunities = []
        rejected_count = 0
        
        # Get current positions to check per-symbol limits
        current_positions = self.position_manager.get_open_positions()
        # Count positions per symbol
        positions_per_symbol: dict[str, int] = {}
        for pos in current_positions:
            positions_per_symbol[pos.symbol] = positions_per_symbol.get(pos.symbol, 0) + 1
        
        # Get actionable news
        news_items = self.news_aggregator.get_actionable_news()
        
        if not news_items:
            return []
        
        logger.info(f"Evaluating {len(news_items)} news items")
        
        # Get unique symbols from news
        symbols_needed = set()
        news_by_symbol: dict[str, List[NewsItem]] = {}
        
        for news in news_items:
            symbol = news.detected_symbol
            
            if not symbol:
                self.news_aggregator.mark_processed(
                    news, NewsStatus.NO_SYMBOL.value, "No tradeable symbol detected"
                )
                continue
            
            if symbol not in self.settings.watchlist_symbols:
                self.news_aggregator.mark_processed(
                    news, NewsStatus.NOT_IN_WATCHLIST.value, f"Symbol {symbol} not in watchlist"
                )
                continue
            
            # Check per-symbol position limit
            current_count = positions_per_symbol.get(symbol, 0)
            if current_count >= self.settings.max_positions_per_symbol:
                self.news_aggregator.mark_processed(
                    news, NewsStatus.POSITION_EXISTS.value, 
                    f"Max positions per symbol reached: {current_count}/{self.settings.max_positions_per_symbol} for {symbol}"
                )
                continue
            
            symbols_needed.add(symbol)
            if symbol not in news_by_symbol:
                news_by_symbol[symbol] = []
            news_by_symbol[symbol].append(news)
        
        if not symbols_needed:
            return []
        
        # Fetch technicals and check SYMBOL-LEVEL limits ONCE per symbol
        technicals_cache: dict[str, TechnicalSignals] = {}
        rejected_symbols: set[str] = set()
        
        for symbol in symbols_needed:
            try:
                technicals = self.technical_analyzer.analyze(symbol)
                
                # SYMBOL-LEVEL hard limit check (RSI) - run ONCE per symbol
                is_valid, status, reason = HardLimits.check_symbol(technicals)
                
                if not is_valid:
                    # Reject ALL news for this symbol
                    rejected_symbols.add(symbol)
                    for news in news_by_symbol[symbol]:
                        self.news_aggregator.mark_processed(news, status.value, reason)
                        rejected_count += 1
                    logger.debug(f"Symbol {symbol} rejected: {reason}")
                    continue
                
                technicals_cache[symbol] = technicals
                
            except Exception as e:
                logger.error(f"Failed to get technicals for {symbol}: {e}")
        
        # Build opportunities, applying NEWS-LEVEL hard limits
        for symbol, news_list in news_by_symbol.items():
            if symbol in rejected_symbols or symbol not in technicals_cache:
                continue
            
            technicals = technicals_cache[symbol]
            
            for news in news_list:
                # NEWS-LEVEL hard limit check (age) - run per news
                is_valid, status, reason = HardLimits.check_news(news)
                
                if not is_valid:
                    self.news_aggregator.mark_processed(news, status.value, reason)
                    rejected_count += 1
                    logger.debug(f"News rejected [{status}]: {reason}")
                    continue
                
                opportunities.append((news, technicals))
        
        logger.info(
            f"Opportunities after hard limits: {len(opportunities)} "
            f"(rejected {rejected_count} by pre-AI checks)"
        )
        
        return opportunities
    
    def _execute_decision(self, decision: TradingDecision, opportunities: List[Tuple[NewsItem, TechnicalSignals]]) -> Optional[Position]:
        """
        Execute a BUY decision from AI.
        
        Args:
            decision: AI's trading decision
            opportunities: Original opportunities list
        
        Returns:
            Position if trade executed, None otherwise
        """
        if decision.action != TradeAction.BUY:
            return None
        
        # Find the news item and technicals
        target_news = None
        target_technicals = None
        
        for news, technicals in opportunities:
            if news.id.startswith(decision.headline_id or ""):
                target_news = news
                target_technicals = technicals
                break
        
        if not target_news or not target_technicals:
            logger.error(f"Could not find headline {decision.headline_id} in opportunities")
            return None
        
        # Apply POST-AI hard limits
        is_valid, veto_status, reason = HardLimits.check_post_ai(decision, target_technicals)
        
        if not is_valid:
            logger.warning(f"Post-AI veto [{veto_status}]: {reason}")
            self.news_aggregator.mark_processed(target_news, veto_status.value, reason)
            trade_logger.log_rejection(
                symbol=decision.symbol,
                reason=f"Post-AI veto [{veto_status}]: {reason}",
                details={"ai_confidence": decision.confidence, "catalyst": decision.catalyst_strength}
            )
            return None
        
        # Create a FusionDecision-like object for the executor
        # (We're bridging to the existing order executor interface)
        from src.core.models import FusionDecision
        
        fusion_decision = FusionDecision(
            action=TradeAction.BUY,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
            news_item=target_news,
            technicals=target_technicals,
        )
        
        try:
            # Mark news as SELECTED BEFORE trade execution
            # (Required: trades table has FK constraint to seen_news)
            self.news_aggregator.mark_processed(target_news, NewsStatus.SELECTED.value)
            
            position = self.order_executor.execute_entry(fusion_decision)
            
            if position:
                # Update cooldown
                self._last_trade_time = datetime.now(timezone.utc)
                
                # Log the trade with AI reasoning
                logger.info(
                    f"🎯 Trade executed based on AI decision",
                    extra={
                        "symbol": decision.symbol,
                        "confidence": decision.confidence,
                        "catalyst_strength": decision.catalyst_strength,
                        "reasoning": decision.reasoning,
                        "risk_factors": decision.risk_factors,
                    }
                )
            
            return position
            
        except PositionLimitError:
            self.news_aggregator.mark_processed(
                target_news, NewsStatus.POSITION_LIMIT.value, "Max positions reached"
            )
            return None
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            self.news_aggregator.mark_processed(
                target_news, NewsStatus.EXECUTION_FAILED.value, f"Execution error: {e}"
            )
            return None
    
    def _seek_opportunities(self, macro_climate: str) -> List[Position]:
        """
        Look for trading opportunities using unified AI decision.
        
        Flow:
        1. Gather all opportunities with technicals
        2. Apply PRE-AI hard limits
        3. ONE AI call with MACRO + CRYPTO + TECHNICALS
        4. Apply POST-AI hard limits
        5. Execute if approved
        
        Args:
            macro_climate: Formatted macro headlines for AI context
        
        Returns:
            List of positions opened (max 1)
        """
        new_positions = []
        
        try:
            # Pre-checks
            if self._is_in_cooldown():
                remaining = self.settings.trade_cooldown_minutes - \
                    (datetime.now(timezone.utc) - self._last_trade_time).total_seconds() / 60
                logger.info(f"Trade cooldown: {remaining:.1f} min remaining")
                return []
            
            # Early exit if total position limit reached (avoids unnecessary AI calls)
            current_positions = self.position_manager.get_open_positions()
            if len(current_positions) >= self.settings.max_total_positions:
                logger.debug(f"Total position limit reached: {len(current_positions)}/{self.settings.max_total_positions}")
                return []
            
            # Gather opportunities (applies PRE-AI hard limits)
            opportunities = self._gather_opportunities()
            
            if not opportunities:
                logger.debug("No opportunities passed pre-AI filters")
                return []
            
            # ONE AI call with FULL CONTEXT (macro + crypto + technicals)
            decision = self.trading_brain.evaluate_opportunities(
                opportunities=opportunities,
                macro_climate=macro_climate,  # NEW: Pass macro context
            )
            
            # Log AI's full reasoning
            logger.info(f"AI Decision: {decision.action}")
            logger.info(f"  Confidence: {decision.confidence}")
            logger.info(f"  Catalyst: {decision.catalyst_strength}")
            logger.info(f"  Macro: {decision.macro_assessment}")  # NEW
            logger.info(f"  Technicals: {decision.technical_assessment}")
            logger.info(f"  Reasoning: {decision.reasoning}")
            if decision.risk_factors:
                logger.info(f"  Risk factors: {decision.risk_factors}")
            
            # Execute if BUY (POST-AI limits checked inside)
            if decision.action == TradeAction.BUY:
                position = self._execute_decision(decision, opportunities)
                if position:
                    new_positions.append(position)
                
                # Mark other news as COMPARED_OUT - they were evaluated but a better option existed
                for news, _ in opportunities:
                    if decision.headline_id and not news.id.startswith(decision.headline_id):
                        self.news_aggregator.mark_processed(
                            news, 
                            NewsStatus.COMPARED_OUT.value, 
                            f"AI chose {decision.symbol} (headline {decision.headline_id[:8]})"
                        )
            else:
                # AI said WAIT - no good opportunities in this batch
                for news, _ in opportunities:
                    self.news_aggregator.mark_processed(
                        news,
                        NewsStatus.AI_WAIT.value,
                        f"AI evaluated batch and said WAIT: {decision.reasoning[:100]}"
                    )
            
        except Exception as e:
            logger.error(f"Error in seek_opportunities: {e}")
        
        return new_positions
    
    def run_cycle(self) -> dict:
        """
        Run one strategy cycle.
        
        NEW FLOW:
        1. Manage existing positions (always)
        2. Gather macro context (as information, not block)
        3. If CATASTROPHE → block (rare)
        4. Otherwise → AI sees macro + crypto + technicals
        """
        self._cycle_count += 1
        cycle_start = datetime.now(timezone.utc)
        
        logger.info(f"═══ Cycle {self._cycle_count} | Mode: {self._mode} ═══")
        
        results = {
            "cycle": self._cycle_count,
            "mode": str(self._mode),
            "positions_checked": 0,
            "trades_opened": 0,
            "ai_available": self.trading_brain.is_available(),
            "macro_headlines": 0,
        }
        
        try:
            # Always manage existing positions
            self._manage_positions()
            results["positions_checked"] = len(self.position_manager.get_open_positions())
            
            # Gather macro context (NEW: context, not binary block)
            is_catastrophe, macro_climate = self._gather_macro_context()
            
            if is_catastrophe:
                # TRUE CATASTROPHE - code-level block (rare: market crash, exchange hack)
                logger.error("🚨 CATASTROPHE MODE - blocking all new trades")
                results["mode"] = "CATASTROPHE"
            else:
                # Normal operation: AI sees FULL context (macro + crypto + technicals)
                results["mode"] = str(self._mode)
                new_positions = self._seek_opportunities(macro_climate=macro_climate)
                results["trades_opened"] = len(new_positions)
            
        except Exception as e:
            logger.error(f"Cycle error: {e}")
            results["error"] = str(e)
        
        results["duration_ms"] = int(
            (datetime.now(timezone.utc) - cycle_start).total_seconds() * 1000
        )
        self._last_cycle_time = datetime.now(timezone.utc)
        
        logger.info(f"Cycle complete: {results}")
        
        return results
    
    def health_check(self) -> dict:
        """Check all components."""
        return {
            "exchange": self.exchange.health_check(),
            "database": True,  # Assume OK if we got here
            "ai": self.trading_brain.test_connection() if self.trading_brain.is_available() else False,
            "overall": self.exchange.health_check(),
        }
    
    def get_status(self) -> dict:
        """Get strategy status."""
        return {
            "mode": str(self._mode),
            "cycle_count": self._cycle_count,
            "last_cycle": self._last_cycle_time.isoformat() if self._last_cycle_time else None,
            "last_trade": self._last_trade_time.isoformat() if self._last_trade_time else None,
            "positions": self.position_manager.get_status(),
            "health": self.health_check(),
        }
    
    def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.warning("Strategy shutdown")
        self._mode = SystemMode.SHUTDOWN
