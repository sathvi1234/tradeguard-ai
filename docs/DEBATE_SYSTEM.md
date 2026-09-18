# TradeGuard AI - Debate System Documentation

## Overview

The Debate System is the core autonomous trading analysis engine for TradeGuard AI. It orchestrates 7 specialized AI agents + 2 deterministic risk guardians to analyze market opportunities, debate trade viability, and make final trading decisions.

**Key Principle**: AI agents provide analysis and recommendations, but the Deterministic Risk Guardian has final authority and cannot be bypassed.

## Architecture

### Agent Flow

```
Market Scout Agent
    ↓ (analyzes market)
Options Analyst Agent
    ↓ (validates options)
Bull Agent ─┐
            ├─→ Options Strategy Agent
Bear Agent ─┘
    ↓
Risk Agent
    ↓
Decision Agent
    ↓
Risk Guardian (DETERMINISTIC - NO BYPASS)
    ↓
Drawdown Guardian (MODE MANAGEMENT)
```

## Agents

### 1. Market Scout Agent

**Purpose**: Analyzes market opportunity for a symbol.

**Analyzes**:
- Price trends
- Momentum  
- Volume
- Volatility
- Market conditions

**Returns**:
- `direction`: BULLISH, BEARISH, or NEUTRAL
- `market_score`: 0.0-1.0 confidence
- `momentum_score`: Price momentum indicator
- `volume_score`: Volume analysis
- `volatility_score`: Volatility analysis
- `timestamp`: Analysis time

**Uses Real Data**: ✅ Alpaca market data
**Can Bypass Risk**: ❌ No - advisory only

### 2. Options Analyst Agent

**Purpose**: Validates and analyzes options contracts.

**Validates**:
- Contract specifications
- Bid/ask spreads
- Liquidity metrics
- Quote freshness
- Strike/expiration validity

**Returns**:
- Contract details (strike, expiration, bid, ask, spread)
- Greeks (delta, gamma, theta, vega)
- IV and liquidity scores
- Risk/reward ratio
- `viable`: True if contract passes validation

**Rejection Reasons**:
- Missing options data
- Stale quotes (bid=0, ask=0)
- Excessive spread (>50 bps)
- Low liquidity (OI < 100)
- Invalid strike/expiration

**Uses Real Data**: ✅ Alpaca options data via MCP
**Can Bypass Risk**: ❌ No - validates only

### 3. Bull Agent

**Purpose**: Makes strongest bullish case FOR the trade.

**Analyzes**:
- Bullish evidence
- Trend strength
- Momentum support
- Volume confirmation
- Upside catalysts
- Options characteristics
- Positive delta exposure

**Returns**:
- `recommendation`: BUY, CONSIDER_BUY, or CAUTION
- `confidence`: 0.0-1.0
- `bullish_evidence`: Supporting reasons
- `upside_potential`: Estimated upside
- `risks`: Bull thesis risks

**Behavior**: Makes strongest case even if bearish
**Can Bypass Risk**: ❌ No - advisory only

### 4. Bear Agent

**Purpose**: Actively challenges the trade (makes bearish case AGAINST).

**Analyzes**:
- Bearish signals
- Weak trends
- Volatility risks
- Event risks
- Liquidity risks
- Expensive options
- Downside potential

**Returns**:
- `recommendation`: AVOID, WAIT_FOR_CLARITY, or RELUCTANT_APPROVAL
- `confidence`: 0.0-1.0
- `counter_arguments`: Against the trade
- `downside_risk`: Estimated downside
- `risks`: Risks to bull thesis

**Behavior**: Genuinely opposes when evidence warrants
**Can Bypass Risk**: ❌ No - advisory only

### 5. Options Strategy Agent

**Purpose**: Evaluates options and selects optimal strategy.

**Evaluates**:
- BUY_CALL: For bullish conviction
- BUY_PUT: For bearish conviction  
- DEFINED_RISK_SPREAD: For range-bound markets
- NO_TRADE: When none viable

**Considers**:
- Strike pricing
- Expiration selection
- Greeks characteristics
- IV environment
- Liquidity metrics
- Risk/reward ratios
- Theta decay

**Returns**:
- `strategy`: Selected strategy type
- `strategy_score`: 0.0-1.0 viability
- `strategy_details`: Execution details
- `confidence`: Strategy confidence

**Rule**: Prefers defined-risk strategies when appropriate

**Can Bypass Risk**: ❌ No - advisory only

### 6. Risk Agent

**Purpose**: AI risk analysis (ADVISORY ONLY - not binding).

**Analyzes**:
- Portfolio value and exposure
- Position sizing appropriateness
- Maximum loss estimation
- Concentration metrics
- Confidence/reward alignment
- Portfolio liquidity

**Returns**:
- `risk_level`: LOW, MODERATE, HIGH, or CRITICAL
- `risk_score`: 0.0-1.0 (1.0 = highest risk)
- `recommendation`: APPROVE_CANDIDATE, REJECT_CANDIDATE, or REQUIRES_REVIEW
- `warnings`: List of risk concerns

**Important**: This is ONLY an AI opinion.
The Deterministic Risk Guardian makes the final decision.

**Can Bypass Risk**: ❌ No - advisory only

### 7. Decision Agent

**Purpose**: Synthesizes all analyses and makes final recommendation.

**Synthesizes**:
- Market Scout direction and confidence
- Options Analyst contract viability
- Bull Agent bullish case
- Bear Agent bearish case
- Strategy Agent recommended strategy
- Risk Agent risk assessment

**Decision Rules**:
1. Missing analyses → NO_TRADE
2. Confidence < 50% → NO_TRADE
3. Risk/reward < 1.0 → NO_TRADE
4. High risk detected → NO_TRADE
5. Bull/Bear strong disagreement → Lower confidence

**Returns**:
- `decision`: Selected strategy (BUY_CALL, BUY_PUT, DEFINED_RISK_SPREAD, NO_TRADE)
- `confidence`: Final confidence 0.0-1.0
- `selected_contracts`: Contract specifications
- `proposed_size`: Recommended position size
- `reasoning`: Complete explanation
- `debate_summary`: All agent inputs

**Important**: Decision Agent NEVER submits orders - recommendation only.

**Can Bypass Risk**: ❌ No - advisory only

## Risk Guardians (DETERMINISTIC)

### Risk Guardian

**Purpose**: FINAL MATHEMATICAL SAFETY GATE.

**Authority**: ABSOLUTE - Cannot be bypassed by any LLM.

**Hard Limits** (non-negotiable):
- `MAX_PORTFOLIO_DRAWDOWN`: 15% - Blocks all trades
- `MAX_DAILY_LOSS`: 5% of portfolio
- `MAX_POSITION_SIZE`: $1,000 USD
- `MAX_PORTFOLIO_EXPOSURE`: 30% in single trade
- `MAX_POSITIONS`: 10 open positions
- `MIN_CONFIDENCE_SCORE`: 60% AI confidence
- `MIN_RISK_REWARD_RATIO`: 1.0 minimum
- `MIN_CONTRACT_LIQUIDITY`: 100 open interest
- `MAX_QUOTE_AGE`: 5 minutes max

**Checks**:
1. Paper trading enforced (global level)
2. Portfolio drawdown
3. Daily loss limit
4. Position size
5. Portfolio exposure
6. Open position count
7. Minimum confidence
8. Risk/reward ratio
9. Contract liquidity
10. Quote freshness
11. Trading mode restrictions
12. Contract validity

**Returns**:
- `decision`: APPROVED or REJECTED
- `risk_score`: 0.0-1.0 calculated risk
- `limits_checked`: List of checks performed
- `rejection_reasons`: Reasons if rejected

**Rejection Logic**: ANY mandatory failure = REJECTED

**Override Capability**: ❌ NONE - Deterministic math only

### DrawdownGuardian

**Purpose**: Tracks equity and manages trading modes automatically.

**Tracks**:
- Starting equity
- Peak equity
- Current equity
- Total P&L
- Daily P&L
- Drawdown percentage

**Modes**:

1. **NORMAL Mode**
   - Regular trading allowed
   - Standard position sizing
   - Normal confidence requirements
   - Entry condition: Drawdown < 10%

2. **PROTECTION Mode**
   - Trades allowed with stricter rules
   - Reduced position size caps
   - Higher confidence required (72%+)
   - Stricter risk/reward (1.5+:1)
   - Entry condition: 10% ≤ Drawdown < 15%

3. **CRITICAL Mode**
   - ALL NEW TRADES BLOCKED
   - Only position monitoring
   - Critical risk event logged
   - Voice alert triggered
   - Entry condition: Drawdown ≥ 15%

**Mode Transitions**:
- Purely mathematical - calculated, not overridable
- Recorded with timestamp, equity, drawdown, reason
- Logged as risk events
- Cannot be manually overridden by any agent

## API Endpoints

### POST /api/v1/debate/run

Run complete debate for trading opportunity.

**Request**:
```json
{
  "symbol": "AAPL",
  "option_type": "call",
  "strike": 105.0,
  "expiration": "2024-12-20",
  "portfolio_value": 100000.0,
  "current_equity": 100000.0,
  "current_positions": 2,
  "current_drawdown": 0.05
}
```

**Response**:
```json
{
  "debate_id": "uuid-here",
  "timestamp": "2024-09-04T15:30:00Z",
  "symbol": "AAPL",
  "completed": true,
  "agent_outputs": {
    "market_scout": { ... },
    "options_analyst": { ... },
    "bull_agent": { ... },
    "bear_agent": { ... },
    "strategy_agent": { ... },
    "risk_agent": { ... },
    "decision_agent": { ... }
  },
  "agent_errors": {},
  "final_decision": { ... },
  "risk_guardian_result": {
    "decision": "approved",
    "risk_score": 0.35,
    "limits_checked": [...],
    "rejection_reasons": []
  }
}
```

### GET /api/v1/debate/{debate_id}

Retrieve debate result by ID.

**Response**: Same as POST /api/v1/debate/run

### GET /api/v1/debate/

List all debates, optionally filtered by symbol.

**Query Parameters**:
- `symbol` (optional): Filter by stock symbol

**Response**:
```json
[
  { debate result 1 },
  { debate result 2 },
  ...
]
```

## Decision Logic

### When Debate Recommends NO_TRADE

The debate system recommends NO_TRADE when:
1. Required analyses are missing (Market Scout, Options Analyst, etc.)
2. Options contract fails validation (stale, low liquidity, wide spread)
3. Confidence drops below 50%
4. Risk/reward ratio < 1.0
5. Risk Agent assesses CRITICAL risk
6. Bull/Bear strongly disagree with high disagreement score
7. Any mandatory rule violated

### When Risk Guardian Rejects

Risk Guardian rejects when:
1. Portfolio drawdown ≥ 15% (CRITICAL)
2. Daily loss ≥ 5%
3. Proposed size > $1,000
4. Portfolio exposure > 30%
5. Open positions ≥ 10
6. AI confidence < 60%
7. Risk/reward < 1.0:1
8. Contract liquidity insufficient
9. Market data > 5 minutes old
10. Trading mode is CRITICAL
11. PROTECTION mode with confidence < 72%

### Final Decision Hierarchy

```
Risk Guardian: REJECTED
    ↓ YES → TRADE BLOCKED (no orders executed)
    ↓ NO
Decision Agent: Recommendation
    ↓
If NO_TRADE: Trade blocked
If BUY_CALL/PUT/SPREAD: Position sizing calculated
    ↓
Ready for Execution Engine
(Note: Execution engine NOT YET BUILT - next phase)
```

## Safety Guarantees

### What Cannot Happen

❌ LLM bypasses Risk Guardian limits
❌ Options data stale or invented  
❌ Risk Guardian override by any agent
❌ Live trading (only paper trading allowed)
❌ Position size > Risk Guardian limit
❌ Trades in CRITICAL mode
❌ Trades without market data validation
❌ Options without liquidity verification

### What Is Guaranteed

✅ All agents use same market snapshot
✅ Risk Guardian decision is deterministic math
✅ Every trade attempt logged with full reasoning
✅ Drawdown mode transitions automatic and mathematical
✅ Paper trading enforced at startup + runtime
✅ Stale data causes automatic NO_TRADE
✅ Failures logged, not invented

## Testing

Comprehensive test suite covers:
- ✅ Bullish opportunity analysis
- ✅ Bearish opportunity analysis
- ✅ Neutral market conditions
- ✅ Options data missing
- ✅ Stale quotes (0 bid/ask)
- ✅ Low liquidity rejection
- ✅ Bull/Bear disagreement
- ✅ Low confidence blocking
- ✅ Risk rejection
- ✅ PROTECTION mode restrictions
- ✅ CRITICAL drawdown blocking
- ✅ Insufficient buying power
- ✅ Invalid contract rejection
- ✅ Alpaca service unavailable
- ✅ Full debate flow integration

Run tests:
```bash
pytest tests/test_debate_engine.py -v
```

## Next Phases

### Phase 2: Execution Engine
- Order placement module
- Position tracking
- Real-time P&L
- Stop-loss management

### Phase 3: Voice Alerts
- Critical drawdown alerts
- Mode transition notifications
- Trade recommendation alerts
- Risk event alerts

### Phase 4: Dashboard Updates
- Real-time debate results
- Agent confidence metrics
- Position monitoring
- Risk status display

### Phase 5: Live Trading
- Real account integration (future)
- Position verification
- Trade verification
- Regulatory compliance