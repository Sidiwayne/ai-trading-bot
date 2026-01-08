"""
Trading Brain for FusionBot
=============================

Unified AI decision engine that evaluates ALL opportunities
in a single call. Provides FULL context (macro + crypto + technicals).

Philosophy:
- Hard limits enforced in CODE (not prompt)
- FULL context provided: macro climate + crypto news + technicals
- AI makes the decision with full reasoning
- Code can still veto after AI decision
"""

import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from google import genai
from google.genai import types

from src.core.models import NewsItem, TechnicalSignals
from src.core.enums import TradeAction
from src.core.exceptions import AIAnalysisError
from src.config import get_settings
from src.utils.logging import get_logger
from src.services.notifier import get_notifier

logger = get_logger(__name__)


@dataclass
class TradingDecision:
    """
    Unified trading decision from AI.
    
    Contains the decision, which headline triggered it,
    and full reasoning for transparency.
    """
    action: TradeAction
    symbol: Optional[str]
    headline_id: Optional[str]
    headline_text: Optional[str]
    confidence: int
    reasoning: str
    risk_factors: List[str]
    catalyst_strength: str  # "paradigm_shift", "significant", "moderate", "noise"
    technical_assessment: str
    macro_assessment: str  # How AI assessed macro climate
    macro_factors_considered: List[str]  # Which macro headlines AI found relevant
    raw_response: Optional[Dict[str, Any]] = None


# The prompt that treats AI as an intelligent analyst with FULL context
UNIFIED_DECISION_PROMPT = '''You are a senior crypto trading analyst at a hedge fund.
Your job: Evaluate trading opportunities considering BOTH macro climate AND crypto catalysts.

═══════════════════════════════════════════════════════════════════════════════
MACRO-ECONOMIC CLIMATE (RAW KEYWORD MATCHES - FILTER REQUIRED)
═══════════════════════════════════════════════════════════════════════════════

{macro_climate}

⚠️ IMPORTANT: These headlines matched financial keywords but may contain NOISE.

YOUR FILTERING TASK:
1. IGNORE metaphorical/irrelevant keyword uses:
   - "EV Price War", "Streaming War", "Browser War" → NOT real conflicts
   - "FedEx", "Federal Express" → NOT the Federal Reserve
   - "Software", "Hardware" → NOT related to "war"
   
2. IDENTIFY actual systemic macro factors:
   - Fed policy decisions (rate hikes/cuts, FOMC meetings)
   - Geopolitical conflicts (Ukraine, Middle East tensions)
   - Economic data (CPI, GDP, unemployment, inflation)
   - Market-wide events (corrections, liquidity crises)

3. STATE in your reasoning which macro headlines you considered RELEVANT (if any)

MACRO → CRYPTO IMPACT GUIDE:
- Fed rate CUTS → typically BULLISH for risk assets like crypto
- Fed rate HIKES → typically BEARISH (tighter liquidity)
- Lower inflation (CPI) → BULLISH (less need for rate hikes)
- Higher inflation → BEARISH (more rate hikes coming)
- Geopolitical tension → mixed (BTC can be safe haven OR risk-off)

DO NOT automatically reject trades due to keyword matches.
WEIGH actual macro impact against the crypto catalyst strength.

═══════════════════════════════════════════════════════════════════════════════
CRYPTO OPPORTUNITIES
═══════════════════════════════════════════════════════════════════════════════

{opportunities}

═══════════════════════════════════════════════════════════════════════════════
ANALYSIS FRAMEWORK
═══════════════════════════════════════════════════════════════════════════════

CATALYST STRENGTH:
- "Paradigm Shift": ETF approvals, country adoption, major regulations
  → Can override weak technicals AND mild macro headwinds
- "Significant": Major partnerships, institutional buys, upgrades
  → Strong, but consider macro and technicals
- "Moderate": Minor partnerships, listings, dev updates
  → Need supportive macro AND technicals
- "Noise": Predictions, opinions, recycled news
  → Not actionable regardless of conditions

MACRO IMPACT:
- "Supportive": Macro tailwinds (rate cuts, low inflation, risk-on)
- "Neutral": No significant macro impact
- "Headwind": Mild macro concerns (uncertainty, mixed signals)
- "Adverse": Strong macro headwinds (but NOT catastrophe)

TECHNICAL CONTEXT:
- RSI > 70: Elevated reversal risk
- RSI < 30: Potential bounce or falling knife
- Bullish trend: Momentum up
- Bearish trend: Bull trap risk

DECISION MATRIX:
| Catalyst     | Macro      | Technicals | Action |
|--------------|------------|------------|--------|
| Paradigm     | Any        | Any        | BUY    |
| Significant  | Supportive | Bullish    | BUY    |
| Significant  | Headwind   | Bullish    | MAYBE  |
| Moderate     | Supportive | Bullish    | BUY    |
| Moderate     | Headwind   | Any        | WAIT   |
| Noise        | Any        | Any        | WAIT   |

RISK TOLERANCE: Conservative. Capital preservation first.

═══════════════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

1. Assess the macro climate: supportive, neutral, headwind, or adverse?
2. Which crypto headline has the strongest catalyst?
3. Can the catalyst overcome any macro headwinds?
4. Do technicals support entry?
5. Is this FOMO or genuine opportunity?

Make ONE recommendation: BUY the best opportunity, or WAIT if none qualify.

═══════════════════════════════════════════════════════════════════════════════
RESPONSE FORMAT (JSON only)
═══════════════════════════════════════════════════════════════════════════════

{{
  "action": "BUY" or "WAIT",
  "symbol": "BTC/USDT" (if BUY, null if WAIT),
  "headline_id": "abc123" (if BUY, null if WAIT),
  "confidence": 0-100,
  "catalyst_strength": "paradigm_shift" | "significant" | "moderate" | "noise",
  "macro_assessment": "supportive" | "neutral" | "headwind" | "adverse",
  "macro_factors_considered": ["Fed rate decision", "..."] or [] if none relevant,
  "technical_assessment": "supportive" | "neutral" | "cautionary" | "adverse",
  "risk_factors": ["list", "of", "concerns"],
  "reasoning": "2-3 sentences explaining the decision, including which macro factors mattered"
}}'''


def _format_news_age(published_at: Optional[datetime]) -> str:
    """Format news age as human-readable string."""
    if not published_at:
        return "unknown"
    age_minutes = (datetime.now(timezone.utc) - published_at).total_seconds() / 60
    if age_minutes < 60:
        return f"{int(age_minutes)}m ago"
    return f"{int(age_minutes / 60)}h ago"


def _format_opportunities_grouped(
    opportunities: List[Tuple["NewsItem", "TechnicalSignals"]],
) -> str:
    """
    Format opportunities GROUPED BY SYMBOL.
    
    Technicals shown ONCE per symbol, headlines listed under it.
    Much more token-efficient than repeating technicals per headline.
    """
    from collections import defaultdict
    
    # Group by symbol
    by_symbol: Dict[str, Dict] = defaultdict(lambda: {"technicals": None, "headlines": []})
    
    for news, technicals in opportunities:
        symbol = technicals.symbol
        by_symbol[symbol]["technicals"] = technicals
        by_symbol[symbol]["headlines"].append(news)
    
    # Format output
    sections = []
    
    for symbol, data in by_symbol.items():
        tech = data["technicals"]
        headlines = data["headlines"]
        
        # Symbol header with technicals (ONCE)
        section = f"""
══ {symbol} ══
Price: ${tech.current_price:,.2f} | RSI: {tech.rsi:.1f} ({tech.rsi_zone}) | Trend: {tech.trend}
MACD: {tech.macd_indication} | Volatility: {tech.atr_percent:.2%}

Headlines:"""
        
        # Add all headlines for this symbol
        for news in headlines:
            age = _format_news_age(news.published_at)
            section += f"\n  [{news.id[:8]}] \"{news.title}\" ({news.source}, {age})"
        
        sections.append(section)
    
    return "\n".join(sections)


class TradingBrain:
    """
    Unified AI trading decision engine.
    
    Takes ALL context (macro + crypto + technicals) and makes
    ONE holistic decision. Provides full context, not rules.
    
    Usage:
        brain = TradingBrain()
        decision = brain.evaluate_opportunities(
            opportunities=[(news, technicals), ...],
            macro_climate="Fed signals rate cuts...",
        )
        
        if decision.action == TradeAction.BUY:
            # AI recommends buying
            # Apply post-decision code checks if needed
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize trading brain."""
        settings = get_settings()
        api_key = api_key or settings.google_api_key
        
        if not api_key:
            logger.warning("Google API key not configured - AI decisions unavailable")
            self._client = None
            return
        
        # Initialize the new google-genai client
        self._client = genai.Client(api_key=api_key)
        self._model = "gemini-2.0-flash"
        
        # Generation config
        self._generation_config = types.GenerateContentConfig(
            temperature=0.3,  # Slightly creative but mostly consistent
            top_p=0.85,
            max_output_tokens=1000,
        )
        
        logger.info("Trading brain initialized with macro-aware prompt")
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse AI response to JSON."""
        text = response_text.strip()
        
        # Clean markdown formatting
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.error(f"Response was: {text[:500]}")
            raise AIAnalysisError(f"Invalid JSON from AI: {e}")
    
    def evaluate_opportunities(
        self,
        opportunities: List[tuple[NewsItem, TechnicalSignals]],
        macro_climate: str = "No significant macro headlines.",
    ) -> TradingDecision:
        """
        Evaluate ALL opportunities with FULL context.
        
        Args:
            opportunities: List of (NewsItem, TechnicalSignals) pairs
            macro_climate: Formatted macro headlines for context
        
        Returns:
            TradingDecision with action and full reasoning
        """
        if not self._client:
            logger.warning("AI client not available, returning WAIT")
            return TradingDecision(
                action=TradeAction.WAIT,
                symbol=None,
                headline_id=None,
                headline_text=None,
                confidence=0,
                reasoning="AI client not configured",
                risk_factors=["no_ai"],
                catalyst_strength="noise",
                technical_assessment="unknown",
                macro_assessment="unknown",
                macro_factors_considered=[],
            )
        
        if not opportunities:
            return TradingDecision(
                action=TradeAction.WAIT,
                symbol=None,
                headline_id=None,
                headline_text=None,
                confidence=0,
                reasoning="No opportunities to evaluate",
                risk_factors=[],
                catalyst_strength="noise",
                technical_assessment="neutral",
                macro_assessment="neutral",
                macro_factors_considered=[],
            )
        
        # Format opportunities GROUPED BY SYMBOL (efficient)
        formatted_opportunities = _format_opportunities_grouped(opportunities)
        
        prompt = UNIFIED_DECISION_PROMPT.format(
            macro_climate=macro_climate,
            opportunities=formatted_opportunities,
        )
        
        logger.info(f"Evaluating {len(opportunities)} opportunities with macro context")
        logger.debug(f"Prompt length: {len(prompt)} chars")
        
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._generation_config,
            )
            
            if not response.text:
                raise AIAnalysisError("Empty response from AI")
            
            parsed = self._parse_response(response.text)
            
            # Build decision object
            action = TradeAction.BUY if parsed.get("action") == "BUY" else TradeAction.WAIT
            
            # Find the headline text if BUY
            headline_text = None
            if action == TradeAction.BUY and parsed.get("headline_id"):
                for news, _ in opportunities:
                    if news.id.startswith(parsed["headline_id"]):
                        headline_text = news.title
                        break
            
            macro_factors = parsed.get("macro_factors_considered", [])
            
            decision = TradingDecision(
                action=action,
                symbol=parsed.get("symbol"),
                headline_id=parsed.get("headline_id"),
                headline_text=headline_text,
                confidence=int(parsed.get("confidence", 0)),
                reasoning=parsed.get("reasoning", "No reasoning provided"),
                risk_factors=parsed.get("risk_factors", []),
                catalyst_strength=parsed.get("catalyst_strength", "unknown"),
                technical_assessment=parsed.get("technical_assessment", "unknown"),
                macro_assessment=parsed.get("macro_assessment", "neutral"),
                macro_factors_considered=macro_factors if isinstance(macro_factors, list) else [],
                raw_response=parsed,
            )
            
            logger.info(
                f"AI Decision: {decision.action} | "
                f"Confidence: {decision.confidence} | "
                f"Catalyst: {decision.catalyst_strength} | "
                f"Macro: {decision.macro_assessment}"
            )
            if decision.macro_factors_considered:
                logger.info(f"Macro factors considered: {decision.macro_factors_considered}")
            logger.info(f"Reasoning: {decision.reasoning}")
            
            return decision
            
        except Exception as e:
            logger.error(f"AI evaluation failed: {e}")
            # Send notification for AI service failure
            notifier = get_notifier()
            if notifier:
                notifier.send_system_failure(
                    component="AI Service (TradingBrain)",
                    error=f"Evaluation failed: {str(e)[:200]}",
                )
            return TradingDecision(
                action=TradeAction.WAIT,
                symbol=None,
                headline_id=None,
                headline_text=None,
                confidence=0,
                reasoning=f"AI error: {str(e)}",
                risk_factors=["ai_error"],
                catalyst_strength="unknown",
                technical_assessment="unknown",
                macro_assessment="unknown",
                macro_factors_considered=[],
            )
    
    def is_available(self) -> bool:
        """Check if AI is available."""
        return self._client is not None
    
    def test_connection(self) -> bool:
        """Test AI connectivity."""
        if not self._client:
            return False
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents="Reply with just: OK",
            )
            return bool(response.text)
        except Exception as e:
            logger.error(f"AI connection test failed: {e}")
            # Send notification for AI connection failure
            notifier = get_notifier()
            if notifier:
                notifier.send_system_failure(
                    component="AI Service (Connection Test)",
                    error=f"Connection test failed: {str(e)[:200]}",
                )
            return False
