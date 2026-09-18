# TradeGuard AI - Quick Reference Card

## URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

## Commands

### Backend

```bash
# Start
cd backend && python -m uvicorn app.main:app --reload

# Tests
cd backend && pytest tests/ -v

# Install deps
pip install -r requirements.txt
```

### Frontend

```bash
# Start dev
cd frontend && npm run dev

# Build prod
cd frontend && npm run build

# Type check
cd frontend && npm run type-check

# Lint
cd frontend && npm run lint

# Install deps
npm install
```

## Pages

| Page | URL | Purpose |
|------|-----|---------|
| Dashboard | /dashboard | Portfolio overview |
| AI Debate | /ai-debate | Decision visualization |
| Portfolio | /portfolio | Charts & history |
| Positions | /positions | Open trades |
| Orders | /trade-history | Order history |
| Activity | /activity-log | Audit trail |
| Risk | /risk-center | Risk metrics |
| Opportunities | /opportunities | Market opportunities |
| Settings | /settings | Config & demo mode |

## API Endpoints

```
GET  /health                          # Backend health
GET  /api/v1/portfolio                # Current portfolio
GET  /api/v1/portfolio/history        # Equity history
GET  /api/v1/portfolio/stats          # Statistics
GET  /api/v1/portfolio/health         # Health + risk
GET  /api/v1/portfolio/positions      # Open positions
GET  /api/v1/portfolio/orders         # Order history
GET  /api/v1/portfolio/activity       # Audit trail
GET  /api/v1/autonomous/status        # Engine status
POST /api/v1/autonomous/run-cycle     # Run one cycle
GET  /api/v1/debate/                  # Debate results
```

## File Locations

### Pages
```
frontend/app/dashboard/page.tsx       # Main dashboard
frontend/app/ai-debate/page.tsx       # Debate viz
frontend/app/portfolio/page.tsx       # Charts
frontend/app/positions/page.tsx       # Positions
frontend/app/trade-history/page.tsx   # Orders
frontend/app/activity-log/page.tsx    # Audit
frontend/app/risk-center/page.tsx     # Risk
frontend/app/opportunities/page.tsx   # Opportunities
frontend/app/settings/page.tsx        # Settings
```

### Components
```
frontend/components/VoiceAlert.tsx    # Voice notifications
frontend/components/QRCode.tsx        # QR code
```

### Utilities
```
frontend/lib/api.ts                   # API client
frontend/hooks/useApi.ts              # Data hooks
frontend/types/index.ts               # Types
```

## Environment Variables

### Backend (.env)
```
ALPACA_API_KEY=sk_...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
CLAUDE_API_KEY=sk-...
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Key Features

- ✅ 7 autonomous AI agents
- ✅ Debate pipeline visualization
- ✅ Real Alpaca paper trading
- ✅ Risk guardians (hard limits)
- ✅ Drawdown protection (mode transitions)
- ✅ Professional dashboard
- ✅ Mobile responsive
- ✅ Demo mode
- ✅ Audit trail
- ✅ Mock voice alerts

## Trading Modes

| Mode | Drawdown | Behavior |
|------|----------|----------|
| NORMAL | 0-5% | Full autonomy |
| PROTECTION | 5-10% | Reduced sizes |
| CRITICAL | >10% | Stop trading |

## AI Agents

1. **Market Scout** - Market analysis
2. **Options Analyst** - Contract selection
3. **Bull Agent** - Bullish case
4. **Bear Agent** - Bearish case
5. **Strategy Agent** - Strategy selection
6. **Risk Agent** - Risk evaluation
7. **Decision Agent** - Final synthesis

## Risk Limits (Hard-coded)

- Daily loss: $5,000
- Max drawdown: 15%
- Position size: 5% of portfolio
- Sector exposure: 30%

## Demo Mode

**Toggle in Settings**:
1. Go to `/settings`
2. Click "ENABLE DEMO MODE"
3. Data shows "SIMULATED" labels

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend won't start | Check port 8000 free, Python 3.11+ |
| Frontend won't start | npm install, Node 18+ |
| API connection error | Check NEXT_PUBLIC_API_URL |
| Demo mode not working | Go to Settings, enable toggle |
| No data showing | Check backend health: localhost:8000/health |

## Document Reference

| Document | Purpose |
|----------|---------|
| README.md | Full documentation |
| START.md | Setup instructions |
| DEMO_GUIDE.md | Demo walkthrough |
| HACKATHON_COMPLIANCE.md | Requirements verification |
| COMPLETION_SUMMARY.md | Technical summary |
| FINAL_STATUS.md | Project status |

## Quick Demo (15 min)

1. Open /dashboard (2 min)
2. Enable demo mode in Settings (1 min)
3. View /ai-debate (4 min)
4. Check /portfolio charts (2 min)
5. View /risk-center (2 min)
6. Scan QR in /settings (1 min)
7. Mobile check (3 min)

## Contact

**For questions**: Check documentation files  
**For errors**: Check console (F12) and terminal logs  
**For demo**: Follow DEMO_GUIDE.md  
**For setup**: Follow START.md

---

**Production Ready • Hackathon Compliant • 100% Feature Complete ✅**