"""Market Scout Agent - Analyzes market opportunities using real Alpaca data."""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from enum import Enum

from app.agents.base import BaseAgent, AgentAnalysis, AgentType
from app.alpaca.service import AlpacaService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MarketDirection(str, Enum):
    """Market direction enumeration."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MarketScoutAgent(BaseAgent):
    """
    Analyzes market opportunities using real Alpaca data.
    
    Evaluates:
    - Price trends
    - Momentum
    - Volume
    - Volatility
    - Recent price behavior
    - Market conditions
    """
    
    def __init__(self, alpaca_service: Optional[AlpacaService] = None):
        """Initialize Market Scout Agent."""
        super().__init__()
        self.agent_type = AgentType.MARKET_SCOUT
        self.alpaca_service = alpaca_service or AlpacaService()
    
    async def analyze(
        self,
        symbol: str,
        **kwargs
    ) -> AgentAnalysis:
        """
        Analyze market opportunity for a symbol.
        
        Args:
            symbol: Stock symbol to analyze
            **kwargs: Additional arguments
            
        Returns:
            AgentAnalysis with market assessment
        """
        timestamp = datetime.utcnow()
        errors = []
        
        try:
            # Validate symbol
            if not self._validate_symbol(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")
            
            # Get current market data
            try:
                market_data = await self.alpaca_service.get_market_data(symbol)
            except Exception as e:
                errors.append(f"Failed to get market data: {str(e)}")
                logger.warning(f"Market data unavailable for {symbol}: {e}")
                market_data = None

            if not market_data:
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning="WAITING FOR REQUIRED MARKET DATA: price",
                    data={"valid": False, "missing": ["price"], "status": "WAITING FOR REQUIRED MARKET DATA"},
                    errors=errors or ["WAITING FOR REQUIRED MARKET DATA: price"],
                )

            freshness = market_data.get("freshness") or "FRESH"
            current_price = market_data.get("last_trade_price") or market_data.get("current_price") or market_data.get("ask_price")
            bid_price = market_data.get("bid_price")
            ask_price = market_data.get("ask_price")
            missing = list(market_data.get("missing") or [])
            integrity_state = str(market_data.get("integrity_state") or "")
            if market_data.get("integrity_fail_closed"):
                reason = str(market_data.get("integrity_notes") or "Market data failed integrity checks. Fail closed.")
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning=reason,
                    data={
                        "freshness": freshness,
                        "valid": False,
                        "missing": missing,
                        "session": market_data.get("session"),
                        "integrity_state": integrity_state,
                        "integrity_fail_closed": True,
                        "status": integrity_state or "FAIL_CLOSED",
                    },
                    errors=[reason],
                )
            if not isinstance(current_price, (int, float)) or not current_price:
                missing.append("price")
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning="WAITING FOR REQUIRED MARKET DATA: price",
                    data={
                        "freshness": freshness,
                        "valid": False,
                        "missing": missing,
                        "session": market_data.get("session"),
                        "bid_price": bid_price,
                        "ask_price": ask_price,
                        "volume": market_data.get("volume"),
                        "status": "WAITING FOR REQUIRED MARKET DATA",
                    },
                    errors=["WAITING FOR REQUIRED MARKET DATA: price"],
                )
            if freshness in ("DATA_UNAVAILABLE", "INVALID") and not isinstance(current_price, (int, float)):
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning="WAITING FOR REQUIRED MARKET DATA: quote",
                    data={"freshness": freshness, "valid": False, "missing": ["quote"]},
                    errors=["WAITING FOR REQUIRED MARKET DATA: quote"],
                )
            bid_size = market_data.get("bid_size")
            ask_size = market_data.get("ask_size")
            spread = (ask_price - bid_price) if isinstance(bid_price, (int, float)) and isinstance(ask_price, (int, float)) else None
            spread_pct = (spread / ((bid_price + ask_price) / 2)) if spread is not None and bid_price and ask_price else None
            
            # Analyze price action
            direction, momentum_score, price_analysis = await self._analyze_price_action(
                symbol,
                current_price,
                market_data
            )
            
            # Analyze volume
            volume_score, volume_analysis = await self._analyze_volume(symbol)
            volatility_score, volatility_analysis = await self._analyze_volatility(symbol)
            
            # Calculate overall market score
            market_score = (momentum_score * 0.4 + volume_score * 0.3 + volatility_score * 0.3)
            
            # Determine confidence
            confidence = self._calculate_confidence(
                direction,
                market_score,
                market_data.get("market_open", False),
                errors
            )
            
            # Build reasoning
            reasoning = self._build_reasoning(
                direction,
                momentum_score,
                volume_score,
                volatility_score,
                price_analysis,
                volume_analysis,
                volatility_analysis
            )
            
            # Compile analysis data
            optional_notes = []
            if not isinstance(bid_price, (int, float)):
                optional_notes.append("bid: Not available")
            if not isinstance(ask_price, (int, float)):
                optional_notes.append("ask: Not available")
            if volume_analysis.get("volume_available") is False:
                optional_notes.append("volume: Not available")
            if volatility_analysis.get("volatility_available") is False:
                optional_notes.append("volatility: Not enough data")
            data = {
                "direction": direction.value,
                "market_score": market_score,
                "momentum_score": momentum_score,
                "volume_score": volume_score,
                "volatility_score": volatility_score,
                "current_price": current_price,
                "last_price": market_data.get("last_trade_price") or current_price,
                "bid_price": bid_price,
                "ask_price": ask_price,
                "bid_size": bid_size,
                "ask_size": ask_size,
                "spread": spread,
                "spread_pct": spread_pct,
                "volume": market_data.get("volume") if market_data.get("volume") is not None else volume_analysis.get("last_volume"),
                "previous_close": market_data.get("previous_close"),
                "day_change": market_data.get("day_change"),
                "day_change_pct": market_data.get("day_change_pct"),
                "session": market_data.get("session"),
                "timestamp": market_data.get("timestamp"),
                "freshness": freshness,
                "source": market_data.get("source", "alpaca"),
                "feed": market_data.get("feed", "iex"),
                "valid": True,
                "market_open": market_data.get("market_open"),
                "market_condition": direction.value,
                "trend": direction.value,
                "optional_notes": optional_notes,
                "price_analysis": price_analysis,
                "volume_analysis": volume_analysis,
                "volatility_analysis": volatility_analysis,
            }
            
            analysis = AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=confidence,
                reasoning=reasoning,
                data=data,
                errors=errors if errors else None
            )
            
            self._log_analysis(analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"Market Scout analysis failed for {symbol}", error=str(e))
            
            return AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                data={},
                errors=[str(e)]
            )
    
    async def _analyze_price_action(
        self,
        symbol: str,
        current_price: float,
        market_data: Dict[str, Any]
    ) -> tuple:
        """
        Analyze price action and momentum.
        
        Returns:
            Tuple of (direction, score, analysis_dict)
        """
        try:
            # In production, would use historical bars from Alpaca
            # For now, basic analysis based on spread and market conditions
            
            bid_price = market_data.get("bid_price", 0)
            ask_price = market_data.get("ask_price", 0)
            
            # Simple momentum indicator based on bid/ask relationship
            if ask_price > 0 and bid_price > 0:
                mid_price = (bid_price + ask_price) / 2
                momentum = (ask_price - bid_price) / mid_price if mid_price > 0 else 0
            else:
                momentum = 0
            
            # Determine direction (in real system, use historical data)
            if momentum > 0.001:
                direction = MarketDirection.BULLISH
                momentum_score = min(0.7, momentum * 100)  # Scale to 0-1
            elif momentum < -0.001:
                direction = MarketDirection.BEARISH
                momentum_score = min(0.7, abs(momentum) * 100)
            else:
                direction = MarketDirection.NEUTRAL
                momentum_score = 0.5
            
            analysis = {
                "momentum_indicator": momentum,
                "spread_basis_points": (ask_price - bid_price) / mid_price * 10000 if mid_price > 0 else 0,
            }
            
            return direction, momentum_score, analysis
            
        except Exception as e:
            logger.warning(f"Price analysis failed for {symbol}: {e}")
            return MarketDirection.NEUTRAL, 0.5, {"error": str(e)}
    
    async def _analyze_volume(self, symbol: str) -> tuple:
        """
        Analyze volume characteristics.
        
        Returns:
            Tuple of (score, analysis_dict)
        """
        try:
            bars = await self.alpaca_service.get_bars(symbol, timeframe="1Day", limit=5)
            if not bars:
                return 0.0, {"volume_available": False, "note": "Not available"}
            last_volume = bars[-1].volume
            return (0.6 if last_volume else 0.0), {
                "volume_available": last_volume is not None,
                "last_volume": last_volume,
                "source": "alpaca_bars",
            }
            
        except Exception as e:
            logger.warning(f"Volume analysis failed for {symbol}: {e}")
            return 0.5, {"error": str(e)}
    
    async def _analyze_volatility(self, symbol: str) -> tuple:
        """
        Analyze volatility.
        
        Returns:
            Tuple of (score, analysis_dict)
        """
        try:
            bars = await self.alpaca_service.get_bars(symbol, timeframe="1Day", limit=10)
            closes = [b.close for b in bars if b.close]
            if len(closes) < 2:
                return 0.0, {"volatility_available": False, "note": "Not enough data"}
            rets = []
            for i in range(1, len(closes)):
                if closes[i - 1]:
                    rets.append(abs(closes[i] - closes[i - 1]) / closes[i - 1])
            if not rets:
                return 0.0, {"volatility_available": False, "note": "Not enough data"}
            realized = sum(rets) / len(rets)
            return min(1.0, realized * 20), {
                "volatility_available": True,
                "mean_abs_return": realized,
                "source": "alpaca_bars",
            }
            
        except Exception as e:
            logger.warning(f"Volatility analysis failed for {symbol}: {e}")
            return 0.5, {"error": str(e)}
    
    def _calculate_confidence(
        self,
        direction: MarketDirection,
        market_score: float,
        market_open: bool,
        errors: list
    ) -> float:
        """Calculate overall confidence score."""
        confidence = 0.5
        
        # Adjust for direction
        if direction == MarketDirection.BULLISH:
            confidence = 0.6 + (market_score * 0.2)
        elif direction == MarketDirection.BEARISH:
            confidence = 0.5 + (market_score * 0.2)
        else:
            confidence = 0.4 + (market_score * 0.1)
        
        # Reduce confidence if market is closed
        if not market_open:
            confidence *= 0.8
        
        # Reduce confidence if there were errors
        if errors:
            confidence *= 0.9
        
        return min(1.0, max(0.0, confidence))
    
    def _build_reasoning(
        self,
        direction: MarketDirection,
        momentum_score: float,
        volume_score: float,
        volatility_score: float,
        price_analysis: Dict,
        volume_analysis: Dict,
        volatility_analysis: Dict
    ) -> str:
        """Build reasoning explanation."""
        parts = [
            f"Market direction: {direction.value}",
            f"Momentum score: {momentum_score:.2f}",
            f"Volume score: {volume_score:.2f}",
            f"Volatility score: {volatility_score:.2f}",
        ]
        
        if direction == MarketDirection.BULLISH:
            parts.append("Bullish bias detected based on price action.")
        elif direction == MarketDirection.BEARISH:
            parts.append("Bearish bias detected based on price action.")
        else:
            parts.append("Neutral market conditions detected.")
        
        return " ".join(parts)