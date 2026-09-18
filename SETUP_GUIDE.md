# TradeGuard AI - Complete Setup Guide

## Project Structure

```
tradeguard-ai/
├── backend/
│   ├── app/
│   │   ├── agents/                    # AI agents for debate
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Base agent class + enums
│   │   │   ├── market_scout.py       # Market analysis agent
│   │   │   ├── options_analyst.py    # Options validation agent
│   │   │   ├── bull_agent.py         # Bullish case agent
│   │   │   ├── bear_agent.py         # Bearish case agent
│   │   │   ├── strategy_agent.py     # Strategy selection agent
│   │   │   ├── risk_agent.py         # Risk analysis agent (advisory)
│   │   │   └── decision_agent.py     # Final decision synthesis
│   │   ├── autonomous/                # Debate orchestration
│   │   │   ├── __init__.py
│   │   │   └── debate_engine.py      # Main debate engine
│   │   ├── risk/                      # Risk management system
│   │   │   ├── __init__.py
│   │   │   ├── risk_guardian.py      # Deterministic risk gate
│   │   │   └── drawdown_guardian.py  # Equity & mode tracking
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── health.py             # Health check endpoint
│   │   │   ├── alpaca.py             # Alpaca integration endpoint
│   │   │   └── debate.py             # Debate system endpoints
│   │   ├── models/
│   │   │   └── __init__.py           # TradingMode enum
│   │   ├── alpaca/                    # Alpaca API integration
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── service.py
│   │   │   └── exceptions.py
│   │   ├── utils/                     # Utilities
│   │   │   ├── __init__.py
│   │   │   └── logging.py
│   │   ├── database/                  # Database models
│   │   ├── config.py                  # Configuration
│   │   └── main.py                    # FastAPI app
│   ├── tests/
│   │   └── test_debate_engine.py     # Comprehensive tests
│   ├── requirements.txt               # Python dependencies
│   └── pytest.ini
├── frontend/                          # Next.js frontend
│   └── ...
├── docs/
│   ├── DEBATE_SYSTEM.md              # System documentation
│   └── ...
├── IMPLEMENTATION_SUMMARY.md          # This implementation
└── SETUP_GUIDE.md                     # This file
```

## Installation

### 1. Prerequisites

- Python 3.8+
- Node.js 16+ (for frontend)
- pip/poetry (Python package management)
- npm/yarn (Node package management)

### 2. Backend Setup

```bash
cd tradeguard-ai/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

```bash
# Create .env file in backend directory
cp .env.example .env

# Edit .env with your Alpaca credentials
# ALPACA_API_KEY=your_api_key
# ALPACA_SECRET_KEY=your_secret_key
# ALPACA_BASE_URL=https://paper-api.alpaca.markets (paper trading)
```

### 4. Database Setup (Optional - not required for debate analysis)

```bash
cd backend

# Create database
# This is handled automatically by SQLAlchemy
```

## Running the System

### 1. Start Backend Server

```bash
cd tradeguard-ai/backend

# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Start FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at: http://localhost:8000

API Docs: http://localhost:8000/docs (Swagger UI)

### 2. Run Tests

```bash
cd tradeguard-ai/backend

# Run all tests
pytest tests/test_debate_engine.py -v

# Run with coverage
pytest tests/test_debate_engine.py -v --cov=app.agents --cov=app.risk --cov=app.autonomous

# Run specific test class
pytest tests/test_debate_engine.py::TestMarketScoutAgent -v

# Run specific test
pytest tests/test_debate_engine.py::TestMarketScoutAgent::test_market_scout_bullish_opportunity -v
```

## Using the Debate System

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "service": "TradeGuard AI",
  "version": "1.0.0"
}
```

### 2. Run a Debate

```bash
curl -X POST http://localhost:8000/api/v1/debate/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "option_type": "call",
    "strike": 105.0,
    "expiration": "2024-12-20",
    "portfolio_value": 100000.0,
    "current_equity": 100000.0,
    "current_positions": 0,
    "current_drawdown": 0.0
  }'
```

Response:
```json
{
  "debate_id": "550e8400-e29b-41d4-a716-446655440000",
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
    "limits_checked": [
      "paper_trading",
      "max_portfolio_drawdown",
      "max_daily_loss",
      ...
    ],
    "rejection_reasons": []
  }
}
```

### 3. Retrieve Debate Result

```bash
curl http://localhost:8000/api/v1/debate/550e8400-e29b-41d4-a716-446655440000
```

### 4. List All Debates

```bash
curl http://localhost:8000/api/v1/debate/
```

Filter by symbol:
```bash
curl http://localhost:8000/api/v1/debate/?symbol=AAPL
```

## Understanding the Output

### Final Decision Structure

```json
{
  "decision": "buy_call",           // BUY_CALL, BUY_PUT, DEFINED_RISK_SPREAD, or NO_TRADE
  "confidence": 0.64,               // 0.0-1.0, composite confidence
  "proposed_size": 500.0,           // Recommended position size in USD
  "selected_contracts": {
    "symbol": "AAPL",
    "type": "call",
    "strike": 105.0,
    "expiration": "2024-12-20",
    "entry_price": 2.50,            // Mid bid/ask
    "bid": 2.45,
    "ask": 2.55
  },
  "reasoning": "Bull recommendation: BUY | Supporting evidence score: 3.0/3.0 | ...",
  "debate_summary": {
    "market_view": "bullish",
    "bull_recommendation": "BUY",
    "bear_recommendation": "RELUCTANT_APPROVAL",
    "strategy_recommendation": "buy_call",
    "risk_level": "MODERATE"
  }
}
```

### Risk Guardian Result

```json
{
  "decision": "approved",           // APPROVED or REJECTED
  "risk_score": 0.35,               // 0.0-1.0, calculated risk
  "limits_checked": [               // All hard limits checked
    "paper_trading",
    "max_portfolio_drawdown",
    "max_daily_loss",
    "max_position_size",
    "max_portfolio_exposure",
    "max_open_positions",
    "min_confidence_score",
    "min_risk_reward_ratio",
    "contract_liquidity",
    "quote_freshness",
    "trading_mode",
    "contract_validity"
  ],
  "rejection_reasons": []           // Empty if approved, reasons if rejected
}
```

## Common Scenarios

### Scenario 1: Bullish Opportunity

```bash
# Analyze a bullish opportunity
curl -X POST http://localhost:8000/api/v1/debate/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NVDA",
    "option_type": "call",
    "strike": 500.0,
    "expiration": "2024-10-18",
    "portfolio_value": 100000.0,
    "current_equity": 100000.0,
    "current_positions": 1,
    "current_drawdown": 0.02
  }'
```

Expected: Market Scout shows BULLISH, Bull Agent confident, Bear Agent cautious, Risk Guardian approves.

### Scenario 2: High Drawdown (PROTECTION Mode)

```bash
# High drawdown triggers PROTECTION mode
curl -X POST http://localhost:8000/api/v1/debate/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "QQQ",
    "option_type": "put",
    "strike": 350.0,
    "expiration": "2024-09-20",
    "portfolio_value": 100000.0,
    "current_equity": 90000.0,         # 10% drawdown
    "current_positions": 3,
    "current_drawdown": 0.10
  }'
```

Expected: DrawdownGuardian in PROTECTION mode, Risk Guardian enforces stricter rules.

### Scenario 3: Critical Drawdown (CRITICAL Mode)

```bash
# Critical drawdown blocks all trades
curl -X POST http://localhost:8000/api/v1/debate/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "SPY",
    "option_type": "call",
    "strike": 450.0,
    "expiration": "2024-09-29",
    "portfolio_value": 100000.0,
    "current_equity": 84000.0,         # 16% drawdown
    "current_positions": 5,
    "current_drawdown": 0.16
  }'
```

Expected: DrawdownGuardian in CRITICAL mode, Risk Guardian rejects trade.

### Scenario 4: Stale Data

```bash
# System handles unavailable market data gracefully
# (Simulate by stopping Alpaca service or network issue)
```

Expected: Market Scout returns 0.0 confidence, Decision Agent recommends NO_TRADE.

## Debugging

### Enable Debug Logging

```python
# In app/config.py or environment
LOG_LEVEL=DEBUG
```

### Check Logs

```bash
# Logs are output to console
# Look for lines like:
# [Agent Scout Analysis] confidence=0.65 symbol=AAPL
# [Risk Guardian Decision] decision=approved risk_score=0.35
# [Trade Rejected] reason=high_drawdown
```

### Test Individual Agent

```python
# Create a test script: test_agent.py
import asyncio
from app.agents import MarketScoutAgent

async def test():
    agent = MarketScoutAgent()
    analysis = await agent.analyze(symbol="AAPL")
    print(f"Confidence: {analysis.confidence}")
    print(f"Direction: {analysis.data.get('direction')}")
    print(f"Reasoning: {analysis.reasoning}")

asyncio.run(test())
```

Run:
```bash
cd tradeguard-ai/backend
python test_agent.py
```

## Troubleshooting

### Issue: "Paper trading disabled" error

**Solution**: Check .env file has `ALPACA_PAPER_TRADE=true`

```bash
# In .env
ALPACA_PAPER_TRADE=true
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

### Issue: "Alpaca service unavailable" error

**Solution**: 
1. Check Alpaca API key and secret in .env
2. Verify internet connection
3. Check Alpaca market hours (market-closed analysis still works)
4. Check Alpaca API status: https://alpacamarkets.com/status

### Issue: Tests fail with import errors

**Solution**:
```bash
# Make sure you're in backend directory
cd tradeguard-ai/backend

# Verify virtual environment is activated
which python  # Should show venv path

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Issue: Port 8000 already in use

**Solution**:
```bash
# Use different port
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Next Steps

1. **Review Documentation**
   - Read `docs/DEBATE_SYSTEM.md` for complete system details
   - Read `IMPLEMENTATION_SUMMARY.md` for implementation overview

2. **Explore Agent Outputs**
   - Run debates with different symbols/parameters
   - Study agent reasoning and confidence scores
   - Observe Risk Guardian decision-making

3. **Test Edge Cases**
   - High drawdown scenarios
   - Low liquidity options
   - Market closed conditions
   - API unavailable scenarios

4. **Integrate with Frontend**
   - Frontend already built and ready
   - Can display debate results and recommendations
   - Dashboard shows agent confidence metrics

5. **Next Development Phase**
   - Execution engine (order placement)
   - Voice alerts for critical events
   - Real-time P&L tracking
   - Live trading integration (future)

## Support

For questions or issues:
1. Check `docs/DEBATE_SYSTEM.md` for architecture details
2. Review test cases in `tests/test_debate_engine.py`
3. Check logs for error details
4. Verify Alpaca API connectivity

## Summary

✅ Complete AI debate system implemented and ready to use
✅ 7 agents + 2 risk guardians
✅ REST APIs for debate analysis
✅ Comprehensive test coverage
✅ Full documentation provided
✅ Paper trading enforced for safety

The system is ready for analysis, testing, and future integration with execution and live trading capabilities.