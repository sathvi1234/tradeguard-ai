"""Options Analyst Agent - Evaluates options contracts using real Alpaca data."""

from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.agents.base import BaseAgent, AgentAnalysis, AgentType
from app.alpaca.service import AlpacaService
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class OptionsContract:
    """Options contract data."""
    symbol: str
    option_type: str  # call or put
    strike: float
    expiration: str
    bid: float
    ask: float
    volume: int
    open_interest: int
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.ask - self.bid
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        if self.bid == 0 and self.ask == 0:
            return 0
        return (self.bid + self.ask) / 2
    
    @property
    def spread_basis_points(self) -> float:
        """Calculate spread in basis points."""
        if self.mid_price == 0:
            return float('inf')
        return (self.spread / self.mid_price) * 10000
    
    @property
    def is_liquid(self) -> bool:
        """Check if contract has sufficient liquidity."""
        return self.volume > 0 and self.open_interest > 100


class OptionsAnalystAgent(BaseAgent):
    """
    Analyzes options contracts using real Alpaca data.
    
    Evaluates:
    - Contract specifications
    - Bid/ask spreads
    - Liquidity
    - Greeks
    - Risk/reward metrics
    """
    
    def __init__(self, alpaca_service: Optional[AlpacaService] = None):
        """Initialize Options Analyst Agent."""
        super().__init__()
        self.agent_type = AgentType.OPTIONS_ANALYST
        self.alpaca_service = alpaca_service or AlpacaService()
        
        # Validation thresholds
        self.max_spread_bps = 50  # Maximum spread in basis points
        self.min_volume = 1
        self.min_open_interest = 100
        self.max_stale_minutes = 5
    
    async def analyze(
        self,
        symbol: str,
        option_type: str = "call",
        strike: Optional[float] = None,
        expiration: Optional[str] = None,
        **kwargs
    ) -> AgentAnalysis:
        """
        Analyze options contract.
        
        Args:
            symbol: Underlying symbol
            option_type: 'call' or 'put'
            strike: Strike price
            expiration: Expiration date
            **kwargs: Additional arguments
            
        Returns:
            AgentAnalysis with options assessment
        """
        timestamp = datetime.utcnow()
        errors = []
        
        try:
            # Validate inputs
            if not self._validate_symbol(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")
            
            if option_type.lower() not in ["call", "put"]:
                raise ValueError(f"Invalid option type: {option_type}")
            
            if not strike or strike <= 0:
                raise ValueError(f"Invalid strike: {strike}")
            
            if not expiration:
                raise ValueError("Expiration date required")
            
            # Get options data from Alpaca (MCP integration point)
            options_data = kwargs.get("option_data")
            if not options_data:
                options_data = await self._get_options_contract_data(
                    symbol,
                    option_type,
                    strike,
                    expiration,
                    occ_symbol=kwargs.get("occ_symbol"),
                )
            
            if not options_data:
                errors.append("Options data not available")
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning="Options data unavailable",
                    data={},
                    errors=errors
                )
            
            # Validate contract data
            validation_errors = self._validate_contract(options_data)
            if validation_errors:
                errors.extend(validation_errors)
                return AgentAnalysis(
                    agent_type=self.agent_type,
                    symbol=symbol,
                    timestamp=timestamp,
                    confidence=0.0,
                    reasoning=f"Contract validation failed: {'; '.join(validation_errors)}",
                    data={},
                    errors=errors
                )
            
            # Create contract object
            contract = self._build_contract(symbol, option_type, options_data)
            
            # Analyze Greeks
            greeks_analysis = self._analyze_greeks(contract)
            
            # Analyze liquidity
            liquidity_score, liquidity_analysis = self._analyze_liquidity(contract)
            
            # Calculate risk/reward
            risk_reward, risk_reward_analysis = self._calculate_risk_reward(
                contract,
                kwargs.get("underlying_price", 0)
            )
            
            # Overall confidence
            confidence = self._calculate_confidence(contract, liquidity_score, errors)
            
            # Build reasoning
            reasoning = self._build_reasoning(
                contract,
                greeks_analysis,
                liquidity_analysis,
                risk_reward_analysis
            )
            
            # Compile data
            data = {
                "contract": {
                    "symbol": contract.symbol,
                    "type": contract.option_type,
                    "strike": contract.strike,
                    "expiration": contract.expiration,
                    "bid": contract.bid,
                    "ask": contract.ask,
                    "mid": contract.mid_price,
                    "spread": contract.spread,
                    "spread_bps": contract.spread_basis_points,
                    "volume": contract.volume,
                    "open_interest": contract.open_interest,
                },
                "greeks": greeks_analysis,
                "liquidity": liquidity_analysis,
                "risk_reward": risk_reward_analysis,
                "viable": liquidity_score > 0.5,
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
            logger.error(f"Options analysis failed for {symbol}", error=str(e))
            
            return AgentAnalysis(
                agent_type=self.agent_type,
                symbol=symbol,
                timestamp=timestamp,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                data={},
                errors=[str(e)]
            )
    
    async def _get_options_contract_data(
        self,
        symbol: str,
        option_type: str,
        strike: float,
        expiration: str,
        occ_symbol: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load a real Alpaca option contract + snapshot. Never fabricates quotes or Greeks."""
        try:
            contracts = await self.alpaca_service.get_option_contracts(
                underlying_symbol=symbol,
                expiration_start=expiration,
                expiration_end=expiration,
                option_type=option_type,
            )
            match = None
            for contract in contracts:
                if occ_symbol and contract.occ_symbol == occ_symbol:
                    match = contract
                    break
                if (
                    contract.strike is not None
                    and abs(contract.strike - float(strike)) < 0.011
                    and (contract.expiration or "")[:10] == expiration[:10]
                    and (contract.option_type or "").lower() == option_type.lower()
                ):
                    match = contract
                    break
            if match is None:
                return None
            snap = await self.alpaca_service.get_option_snapshot(match.occ_symbol)
            payload = {
                "symbol": match.occ_symbol,
                "underlying": match.underlying_symbol,
                "option_type": match.option_type or option_type,
                "strike": match.strike,
                "expiration": match.expiration,
                "tradable": match.tradable,
                "open_interest": match.open_interest,
                "bid": snap.bid if snap else None,
                "ask": snap.ask if snap else None,
                "volume": snap.volume if snap else None,
                "iv": snap.implied_volatility if snap else None,
                "delta": snap.delta if snap else None,
                "gamma": snap.gamma if snap else None,
                "theta": snap.theta if snap else None,
                "vega": snap.vega if snap else None,
                "greeks_quality": snap.greeks_quality if snap else "DATA_UNAVAILABLE",
                "freshness": snap.freshness.value if snap else "DATA_UNAVAILABLE",
            }
            return payload
        except Exception as e:
            logger.error("Failed to get options data for %s: %s", symbol, type(e).__name__)
            return None
    
    def _validate_contract(self, contract_data: Dict[str, Any]) -> List[str]:
        """
        Validate contract data.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required fields
        required_fields = ["bid", "ask", "expiration"]
        for field in required_fields:
            if field not in contract_data or contract_data[field] is None:
                errors.append(f"Missing or invalid field: {field}")
        
        # Check bid/ask validity
        bid = contract_data.get("bid", 0)
        ask = contract_data.get("ask", 0)
        
        if bid < 0 or ask < 0:
            errors.append("Negative bid/ask price")
        
        if bid == 0 and ask == 0:
            errors.append("No quotes available (stale data)")
        
        if bid > ask and bid > 0 and ask > 0:
            errors.append("Bid exceeds ask (invalid quote)")
        
        # Check spread
        if bid > 0 and ask > 0:
            mid = (bid + ask) / 2
            spread_bps = ((ask - bid) / mid) * 10000 if mid > 0 else 0
            
            if spread_bps > self.max_spread_bps:
                errors.append(f"Spread too wide: {spread_bps:.0f} bps")
        
        # Check liquidity
        volume = contract_data.get("volume")
        open_interest = contract_data.get("open_interest")
        if volume is not None and volume < self.min_volume:
            errors.append(f"Insufficient volume: {volume}")
        if open_interest is not None and open_interest < self.min_open_interest:
            errors.append(f"Insufficient open interest: {open_interest}")
        
        return errors
    
    def _build_contract(
        self,
        symbol: str,
        option_type: str,
        data: Dict[str, Any]
    ) -> OptionsContract:
        """Build OptionsContract object."""
        return OptionsContract(
            symbol=symbol,
            option_type=option_type.lower(),
            strike=data["strike"],
            expiration=data["expiration"],
            bid=data.get("bid", 0),
            ask=data.get("ask", 0),
            volume=data.get("volume", 0),
            open_interest=data.get("open_interest", 0),
            iv=data.get("iv", 0),
            delta=data.get("delta", 0),
            gamma=data.get("gamma", 0),
            theta=data.get("theta", 0),
            vega=data.get("vega", 0),
        )
    
    def _analyze_greeks(self, contract: OptionsContract) -> Dict[str, Any]:
        """Analyze option Greeks."""
        return {
            "delta": contract.delta,
            "gamma": contract.gamma,
            "theta": contract.theta,
            "vega": contract.vega,
            "iv": contract.iv,
        }
    
    def _analyze_liquidity(self, contract: OptionsContract) -> tuple:
        """
        Analyze contract liquidity.
        
        Returns:
            Tuple of (score, analysis_dict)
        """
        score = 0.0
        
        # Volume score (0-0.5)
        volume_score = min(0.5, contract.volume / 100) if contract.volume > 0 else 0
        
        # Open interest score (0-0.5)
        oi_score = min(0.5, contract.open_interest / 1000) if contract.open_interest > 0 else 0
        
        # Spread score (0-1.0, inverted)
        if contract.mid_price > 0:
            spread_pct = (contract.spread / contract.mid_price)
            spread_score = max(0, 1.0 - (spread_pct * 100))  # Less spread = higher score
        else:
            spread_score = 0
        
        score = (volume_score * 0.3 + oi_score * 0.3 + spread_score * 0.4)
        
        analysis = {
            "volume_score": volume_score,
            "oi_score": oi_score,
            "spread_score": spread_score,
            "is_liquid": contract.is_liquid,
        }
        
        return score, analysis
    
    def _calculate_risk_reward(
        self,
        contract: OptionsContract,
        underlying_price: float
    ) -> tuple:
        """
        Calculate risk/reward metrics.
        
        Returns:
            Tuple of (ratio, analysis_dict)
        """
        premium = contract.mid_price
        
        if contract.option_type == "call":
            max_loss = premium
            potential_reward = max(0, underlying_price - contract.strike - premium) if underlying_price > contract.strike else 0
        else:  # put
            max_loss = premium
            potential_reward = max(0, contract.strike - underlying_price - premium) if underlying_price < contract.strike else 0
        
        # Calculate risk/reward ratio
        if potential_reward > 0 and max_loss > 0:
            ratio = potential_reward / max_loss
        elif potential_reward == 0:
            ratio = 0
        else:
            ratio = float('inf')
        
        analysis = {
            "premium": premium,
            "max_loss": max_loss,
            "potential_reward": potential_reward,
            "risk_reward_ratio": ratio if not isinstance(ratio, float) or ratio != float('inf') else None,
        }
        
        return min(ratio, 10.0) if not isinstance(ratio, float) or ratio != float('inf') else 0, analysis
    
    def _calculate_confidence(
        self,
        contract: OptionsContract,
        liquidity_score: float,
        errors: list
    ) -> float:
        """Calculate confidence score."""
        confidence = 0.5
        
        # Adjust for liquidity
        confidence += liquidity_score * 0.3
        
        # Adjust for quote quality
        if contract.spread > 0:
            confidence += 0.2
        
        # Reduce for errors
        if errors:
            confidence *= 0.5
        
        return min(1.0, max(0.0, confidence))
    
    def _build_reasoning(
        self,
        contract: OptionsContract,
        greeks_analysis: Dict,
        liquidity_analysis: Dict,
        risk_reward_analysis: Dict
    ) -> str:
        """Build reasoning explanation."""
        parts = [
            f"Options contract: {contract.symbol} {contract.option_type.upper()} ${contract.strike}",
            f"Spread: {contract.spread_basis_points:.0f} bps",
            f"Liquidity score: {liquidity_analysis.get('oi_score', 0):.2f}",
        ]
        
        if risk_reward_analysis.get("risk_reward_ratio"):
            parts.append(f"Risk/reward ratio: {risk_reward_analysis['risk_reward_ratio']:.2f}")
        
        return " | ".join(parts)