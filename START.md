# TradeGuard AI - Quick Start Guide

Get TradeGuard AI running in 5 minutes.

## Prerequisites

- Python 3.11+
- Node.js 18+ (with npm)
- Git

Verify:
```bash
python --version
node --version
npm --version
```

## Step 1: Backend Setup (2 minutes)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy and edit):
# ALPACA_API_KEY=your_key
# ALPACA_SECRET_KEY=your_secret
# ALPACA_BASE_URL=https://paper-api.alpaca.markets
# CLAUDE_API_KEY=your_claude_key

# Start backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Success**: See `Uvicorn running on http://0.0.0.0:8000`

## Step 2: Frontend Setup (2 minutes)

In a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Environment variables are pre-configured in .env.local:
# NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_APP_URL=http://localhost:3000

# Start frontend
npm run dev
```

**Success**: See `ready - started server on 0.0.0.0:3000`

## Step 3: Open Dashboard (1 minute)

Navigate to: **http://localhost:3000**

You should see:
- TradeGuard AI header
- PAPER TRADING badge
- Portfolio metrics
- Quick links to all pages

## Step 4: Enable Demo Mode (Optional)

1. Click **Settings** link
2. Click **ENABLE DEMO MODE** button
3. Page reloads with SIMULATED data

All data is now clearly labeled as simulated for demonstration.

## Verify Everything Works

### Check Backend Health
```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Check Frontend
Open DevTools (F12) → Console → No errors

### Check Integration
1. Dashboard loads
2. Portfolio value shows (from backend)
3. Click through pages
4. No 404 errors

## Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Need 3.11+

# Check dependencies
pip list | grep -i alpaca

# Check port 8000 is free
# On Windows: netstat -ano | findstr :8000
# On macOS/Linux: lsof -i :8000

# If port busy, kill process or use different port:
# python -m uvicorn app.main:app --port 8001
```

### Frontend won't start
```bash
# Clean install
rm -rf node_modules package-lock.json
npm install
npm run dev

# Check Node version
node --version  # Need 18+
```

### API Connection Error
1. Backend running at http://localhost:8000? ✓
2. NEXT_PUBLIC_API_URL=http://localhost:8000 in .env.local? ✓
3. Browser console shows error? Copy error text.

### Demo Mode Not Working
1. Go to Settings page
2. Look for Demo Mode section
3. Click ENABLE button
4. Check browser console (F12) for errors

## Next Steps

### Run Tests
```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend type check
cd frontend
npm run type-check
```

### Try Different Scenarios

1. **View AI Debate**: Click "AI Debate" to see decision pipeline
2. **Check Risk System**: Go to "Risk Center" to see risk controls
3. **View History**: "Portfolio" page shows equity curves
4. **Track Positions**: "Positions" page shows open trades
5. **Review Audit**: "Activity Log" shows all events

### Build for Production

```bash
# Backend (already production-ready)
cd backend

# Frontend production build
cd frontend
npm run build
npm start  # Runs production server
```

## Environment Variables Reference

### Backend (.env)

```
ALPACA_API_KEY=sk_...                           # Your Alpaca API key
ALPACA_SECRET_KEY=...                           # Your Alpaca secret key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading URL
CLAUDE_API_KEY=sk-...                           # Claude AI key
DB_URL=sqlite:///./tradeguard.db                # Database URL
LOG_LEVEL=INFO                                  # Logging level
```

### Frontend (.env.local)

```
NEXT_PUBLIC_API_URL=http://localhost:8000      # Backend API URL
NEXT_PUBLIC_APP_URL=http://localhost:3000      # Frontend URL for QR codes
```

## Architecture Overview

```
TradeGuard AI
├── Frontend (Next.js + React)
│   ├── Dashboard (portfolio overview)
│   ├── AI Debate (decision visualization)
│   ├── Portfolio (charts & history)
│   ├── Positions (open trades)
│   ├── Trade History (orders)
│   ├── Activity Log (audit trail)
│   ├── Risk Center (risk management)
│   ├── Opportunities (market opportunities)
│   └── Settings (configuration)
│
├── Backend (FastAPI + Python)
│   ├── Autonomous Engine (trading loop)
│   ├── 7 AI Agents (decision making)
│   ├── Risk Guardians (safety)
│   ├── Portfolio Manager (tracking)
│   ├── Debate Engine (visualization)
│   └── Alpaca Integration (paper trading)
│
└── Database
    └── Portfolio history, orders, events
```

## Key Features Explained

### Autonomous Trading
- System runs 24/7 when enabled
- Each cycle: analyze → debate → decide → execute
- Completely autonomous, no human intervention

### AI Debate Pipeline
- 7 specialized agents analyze opportunities
- Bull vs Bear agents debate each trade
- Transparent reasoning visible in UI
- Final decision with confidence score

### Risk Management
- Risk Guardian enforces hard limits
- Drawdown Guardian adapts trading mode
- Modes: NORMAL (0-5%) → PROTECTION (5-10%) → CRITICAL (>10%)
- All decisions logged for compliance

### Paper Trading
- Completely safe simulation
- Uses real Alpaca APIs (paper account)
- No real money at risk
- Perfect for testing and learning

## Demo Scenario

1. Open dashboard
2. Enable demo mode
3. View AI Debate to see decision process
4. Check positions and P&L
5. View risk center to see safety mechanisms
6. Review activity log for audit trail
7. Scan QR code to see mobile version

Takes about 15 minutes for complete demo.

## Support

- **Frontend Issues**: Check browser console (F12)
- **Backend Issues**: Check terminal logs
- **API Issues**: Verify endpoints at http://localhost:8000/docs
- **General Help**: See README.md for detailed documentation

---

**You're ready to explore autonomous AI trading! 🚀**