# TradeGuard AI - Professional Autonomous Trading Platform

A sophisticated AI-powered options trading platform combining deep learning-based opportunity identification with deterministic risk management. Built with autonomous agents, real-time portfolio tracking, and paper trading safety.

## Overview

TradeGuard AI implements a complete autonomous trading system with:

- **7 Specialized AI Agents**: Market Scout, Options Analyst, Bull/Bear agents, Strategy Agent, Risk Agent, Decision Agent
- **Deterministic Risk Guardians**: Risk Guardian and Drawdown Guardian for safety
- **Real-time Portfolio Management**: Alpaca Trading API integration
- **Professional Dashboard**: Real-time metrics, charts, position tracking
- **Debate Pipeline**: Transparent AI decision-making visualization
- **Paper Trading**: Safe simulation without real money risk

## Architecture

### Frontend (Next.js)
```
frontend/
├── app/
│   ├── dashboard/         # Main portfolio overview
│   ├── ai-debate/        # AI decision pipeline visualization
│   ├── portfolio/        # Historical charts and stats
│   ├── positions/        # Open positions table
│   ├── trade-history/    # Order history
│   ├── activity-log/     # Audit trail timeline
│   ├── risk-center/      # Risk metrics and guardians
│   ├── opportunities/    # Market opportunities
│   └── settings/         # Configuration status
├── components/
│   ├── VoiceAlert.tsx    # Mock voice notifications
│   └── QRCode.tsx        # Mobile access QR
├── hooks/
│   └── useApi.ts         # SWR data fetching hooks
├── lib/
│   └── api.ts            # Axios API client
└── types/
    └── index.ts          # TypeScript definitions
```

### Backend (Python)
```
backend/
├── app/
│   ├── autonomous/       # Autonomous trading engine
│   ├── agents/          # AI agent implementations
│   ├── portfolio/       # Portfolio management
│   ├── debate/          # Debate pipeline
│   ├── risk/            # Risk guardians
│   └── main.py          # FastAPI app
├── tests/               # Comprehensive test suite
└── requirements.txt     # Dependencies
```

## AI Agents

### Market Scout Agent
Analyzes market conditions, price trends, and volatility to identify opportunities.
- Input: Market data, price history, technical indicators
- Output: Direction recommendation (bullish/bearish) + confidence score

### Bull Agent
Argues the bullish case for a trading opportunity.
- Analyzes: Favorable market conditions, momentum, technical levels
- Confidence: Based on evidence weight

### Bear Agent
Argues the bearish case to balance debate.
- Analyzes: Risk factors, resistance levels, negative catalysts
- Confidence: Reflects counter-argument strength

### Options Analyst
Selects viable option contracts with adequate liquidity.
- Checks: Spread width, volume, open interest
- Rejects: Illiquid or expensive contracts

### Strategy Agent
Determines optimal trading strategy (buy_call, buy_put, spreads).
- Based on: Market direction + risk/reward ratio
- Scores: Each strategy option

### Risk Agent
Evaluates position risk and portfolio impact.
- Checks: Portfolio exposure, correlation, Greeks
- Output: Risk level + recommendation

### Decision Agent
Synthesizes all inputs into final trading decision.
- Confidence: Weighted consensus from all agents
- Decision: TRADE / NO_TRADE with reasoning

## Risk Guardians

### Risk Guardian (Deterministic)
Enforces portfolio-level risk limits:
- Daily loss limit
- Max drawdown threshold
- Position size limits
- Sector exposure caps
- Rejects any trades violating limits

### Drawdown Guardian (Adaptive)
Protects against prolonged losses:
- Monitors peak-to-trough equity decline
- Transitions trading modes based on drawdown
- Modes: NORMAL (0-5%) → PROTECTION (5-10%) → CRITICAL (>10%)

## Trading Modes

| Mode | Drawdown | Behavior |
|------|----------|----------|
| **NORMAL** | 0-5% | Full autonomy, all strategies enabled |
| **PROTECTION** | 5-10% | Reduced position sizes, conservative strategies |
| **CRITICAL** | >10% | Stop trading, focus on reducing drawdown |

## API Endpoints

### Portfolio
```
GET  /api/v1/portfolio              # Current portfolio state
GET  /api/v1/portfolio/history      # Historical equity data
GET  /api/v1/portfolio/stats        # Portfolio statistics
GET  /api/v1/portfolio/health       # Health check with Risk Guardian status
GET  /api/v1/portfolio/positions    # Open positions
GET  /api/v1/portfolio/orders       # All orders
GET  /api/v1/portfolio/activity     # Activity audit trail
```

### Autonomous Engine
```
POST /api/v1/autonomous/start       # Start autonomous trading
POST /api/v1/autonomous/stop        # Stop autonomous trading
GET  /api/v1/autonomous/status      # Engine status
POST /api/v1/autonomous/run-cycle   # Execute one trading cycle
```

### Debate Pipeline
```
POST /api/v1/debate/run             # Execute debate for opportunity
GET  /api/v1/debate/{debate_id}     # Get debate result
GET  /api/v1/debate/                # List all debates
```

### Health
```
GET  /health                        # System health check
```

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Alpaca Trading API account (paper trading)
- Claude API key (for AI providers)

### Backend Setup

1. **Install dependencies**:
```bash
cd backend
pip install -r requirements.txt
```

2. **Create `.env`**:
```bash
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
CLAUDE_API_KEY=your_claude_key
```

3. **Run migrations**:
```bash
python -m alembic upgrade head
```

4. **Start backend**:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at `http://localhost:8000`

### Frontend Setup

1. **Install dependencies**:
```bash
cd frontend
npm install
```

2. **Create `.env.local`**:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

3. **Start frontend**:
```bash
npm run dev
```

Frontend will be available at `http://localhost:3000`

## Demo Mode

TradeGuard AI includes a **Demo Mode** for safe demonstration with simulated data.

### Enable Demo Mode
1. Go to Settings page
2. Click **ENABLE DEMO MODE** button
3. Page reloads with simulated data

### Demo Features
- **$100,000 paper capital** (simulated)
- **Autonomous cycle** with all 7 agents
- **Market Scout analysis** with mock market data
- **Options contracts** with realistic Greeks
- **Bull/Bear debate** with full reasoning
- **Risk Guardian decisions** with rejection examples
- **Drawdown Guardian** mode transitions
- **Position P&L** with realistic prices
- **Trading mode transitions** (NORMAL → PROTECTION → CRITICAL)
- **Mock voice alerts** on important events
- **Complete audit trail** in activity log

All data is clearly labeled **SIMULATED** to prevent confusion.

### Demo Scenario
1. Portfolio: $100k paper capital, $75k cash, $85k buying power
2. Run autonomous cycle → generates AI debate
3. Multiple opportunities identified → shows decision pipeline
4. Risk Guardian approves/rejects trades
5. Positions accumulate with P&L
6. Drawdown increases → triggers PROTECTION mode
7. Further losses trigger CRITICAL mode
8. Voice alert notifies of critical events
9. Activity log records all events

## Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v                      # All tests
pytest tests/test_autonomous.py -v   # Autonomous engine tests
pytest tests/test_risk.py -v         # Risk guardian tests
pytest tests/test_agents.py -v       # Agent tests
```

### Frontend Tests
```bash
cd frontend
npm run lint                          # ESLint
npm run type-check                   # TypeScript check
npm run build                        # Production build
```

## Security

- ✅ No API keys in frontend
- ✅ No secrets in QR codes
- ✅ Paper trading enforced (no live trading)
- ✅ All actions logged for audit trail
- ✅ Secrets stored server-side only
- ✅ HTTPS recommended in production
- ✅ Risk Guardian deterministic controls

## Monitoring

### Key Metrics
- Portfolio value and P&L
- Drawdown percentage
- Open positions count
- Trading mode (NORMAL/PROTECTION/CRITICAL)
- Risk scores
- Agent confidence levels

### Alerts
- Critical: Trading mode change to CRITICAL
- Warning: Approaching risk limits
- Info: Trade execution, debate completion

## Development

### Add New Page
```bash
# Create page component
touch frontend/app/[page-name]/page.tsx

# Add route in navigation
```

### Add New API Endpoint
```python
# In backend/app/routes/
@router.get("/api/v1/endpoint")
async def endpoint():
    return {...}
```

### Customize Risk Limits
Edit `backend/app/risk/risk_guardian.py`:
```python
DAILY_LOSS_LIMIT = 5000          # Max daily loss
MAX_DRAWDOWN = 0.15              # Max 15% drawdown
MAX_POSITION_SIZE = 0.05         # Max 5% per position
```

## Environment Variables

### Backend
```
ALPACA_API_KEY              # Alpaca paper trading key
ALPACA_SECRET_KEY           # Alpaca secret
ALPACA_BASE_URL             # Paper trading URL
CLAUDE_API_KEY              # Claude AI provider
DB_URL                      # Database connection
LOG_LEVEL                   # Logging level (INFO/DEBUG)
```

### Frontend
```
NEXT_PUBLIC_API_URL         # Backend API URL
NEXT_PUBLIC_APP_URL         # Frontend URL for QR codes
NEXT_PUBLIC_DEMO_MODE       # Force demo mode (optional)
```

## Troubleshooting

### Frontend Not Loading
1. Check backend is running: `http://localhost:8000/health`
2. Verify `NEXT_PUBLIC_API_URL` in `.env.local`
3. Clear browser cache and restart: `npm run dev`

### API Connection Error
1. Check backend logs for errors
2. Verify Alpaca credentials in `.env`
3. Ensure paper trading URL is used

### Demo Mode Not Working
1. Go to Settings page
2. Click to enable demo mode
3. Check browser console for errors

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check existing GitHub issues
2. Review API documentation
3. Check backend logs: `tail -f backend/logs/*.log`
4. Enable debug logging: `LOG_LEVEL=DEBUG`

## Hackathon Checklist

- ✅ Autonomous AI agent system (7 agents)
- ✅ Alpaca Trading API integration
- ✅ Options trading support
- ✅ Paper trading safety
- ✅ Professional dashboard
- ✅ Risk management system
- ✅ Drawdown protection
- ✅ Audit trail logging
- ✅ AI decision visualization
- ✅ Voice alerts (mock)
- ✅ Mobile QR code access
- ✅ Demo mode
- ✅ Production-ready build
- ✅ Comprehensive tests
- ✅ Security hardened

---

**Built with Next.js, FastAPI, Claude AI, and Alpaca Trading API**