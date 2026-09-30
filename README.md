🛡️ TradeGuard AI

Autonomous Multi-Agent Options Trading with Adaptive Risk Protection

TradeGuard AI is an AI-powered autonomous trading system that combines multi-agent market analysis, options strategy reasoning, deterministic risk protection, portfolio monitoring, and paper-trading execution into a single platform.

Unlike systems where an AI model directly controls trading decisions, TradeGuard AI follows a Separation of Powers architecture:

AI Agents Analyze → Debate → Decision → Deterministic Risk Guardian → Validated Execution

The AI can reason about opportunities, but risk controls always have the final authority.

🚀 Live Demo

Add your deployed application URL here.

Demo Mode: Paper Trading / Simulated Trading

TradeGuard AI is designed to demonstrate autonomous trading workflows without exposing real capital.

📌 Problem

Automated trading systems can process market information much faster than humans, but fully autonomous AI trading introduces significant risks.

An AI system may:

Misinterpret market conditions
Make decisions using incomplete data
Overreact to market volatility
Generate conflicting trading recommendations
Continue trading during excessive drawdown
Execute duplicate or invalid orders
Make decisions using stale market data

The key question behind TradeGuard AI was:

Can AI agents reason and act autonomously while a deterministic safety system remains in complete control of financial risk?

💡 Solution

TradeGuard AI combines specialized AI agents with a deterministic risk-control layer.

Each AI agent has a specific responsibility:

📊 Market analysis
📈 Bullish analysis
📉 Bearish analysis
🧮 Options strategy analysis
🛡️ Risk analysis
🤖 Trading decision generation

These agents communicate through a structured Debate Engine before a final decision is produced.

However, AI-generated decisions are never trusted blindly.

Every proposed trade passes through:

RiskGuardian → DrawdownGuardian → Order Validation → Paper Execution

If risk limits are violated, the system automatically blocks the trade.

✨ Key Features
🤖 Multi-Agent Trading Intelligence

TradeGuard AI uses multiple specialized agents instead of relying on a single AI response.

MarketScoutAgent

Analyzes available market information and identifies relevant trading opportunities.

OptionsAnalystAgent

Analyzes options-related market information and evaluates potential strategies.

BullAgent

Builds the bullish case for a potential trade.

BearAgent

Builds the bearish case and identifies downside risks.

OptionsStrategyAgent

Evaluates possible options strategies based on the available market context.

RiskAgent

Analyzes potential portfolio and trade-level risks.

🗣️ AI Debate Engine

The system brings opposing perspectives together before making a decision.

                 Market Data
                     │
                     ▼
          ┌─────────────────────┐
          │   Market Scout      │
          └──────────┬──────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ┌──────────────┐      ┌──────────────┐
   │  Bull Agent  │      │  Bear Agent  │
   └──────┬───────┘      └──────┬───────┘
          │                     │
          └──────────┬──────────┘
                     ▼
             ┌───────────────┐
             │ Debate Engine │
             └───────┬───────┘
                     ▼
             ┌───────────────┐
             │ DecisionAgent │
             └───────┬───────┘
                     ▼
             RiskGuardian

This allows the system to consider both opportunity and risk before generating a trade decision.

🛡️ Deterministic Risk Guardian

The most important architectural principle of TradeGuard AI is:

LLMs can recommend. Deterministic code decides whether the trade is allowed.

The RiskGuardian operates independently of the AI reasoning layer.

It can block trades when:

Risk limits are exceeded
Required market information is unavailable
Data is stale
Order parameters are invalid
Portfolio exposure is too high
Drawdown protection is triggered
The system enters CRITICAL mode

AI agents cannot override the RiskGuardian.

📉 Adaptive Drawdown Protection

TradeGuard AI continuously monitors portfolio drawdown.

The system operates using three protection modes:

🟢 NORMAL

Normal trading operations are permitted when portfolio risk remains within configured limits.

🟡 PROTECTION

Trading restrictions are increased when portfolio risk or drawdown begins approaching configured thresholds.

🔴 CRITICAL

New trades are blocked.

The system continues monitoring existing positions and records a risk event.

NORMAL
   │
   │ Risk increases
   ▼
PROTECTION
   │
   │ Critical threshold reached
   ▼
CRITICAL
   │
   ├── New trades BLOCKED
   ├── Existing positions monitored
   ├── Risk event created
   └── Alert generated
📊 Portfolio Monitoring

TradeGuard AI monitors:

Portfolio value
Available cash
Buying power
Open positions
Trade history
Exposure
Drawdown
Risk state
Recent autonomous decisions

This allows the system to continuously evaluate the portfolio rather than treating every trade as an isolated event.

📋 Audit Trail

Every important autonomous action is recorded.

The audit system tracks:

Market analysis
Agent decisions
Debate results
Risk decisions
Order validation
Order execution
Portfolio changes
Risk events
System activity

This creates a traceable record of what happened, why it happened, and which component authorized the action.

🐘 PostgreSQL Database
PostgreSQL is a core part of TradeGuard AI's architecture.

TradeGuard AI uses PostgreSQL as the production-ready relational database layer for persistent trading, portfolio, risk, agent, and audit information.

The database provides structured persistence for an autonomous system where historical decisions and financial events need to remain traceable.

PostgreSQL stores information such as:
👤 Users / demo users
📊 Market and trading records
💼 Portfolio information
📈 Positions
📝 Orders
🤖 Agent decisions
🗣️ Debate results
🛡️ Risk events
📉 Drawdown events
📜 Audit logs
⚙️ System configuration
🗄️ PostgreSQL Data Architecture
                    PostgreSQL
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
   PORTFOLIO           TRADING            AI
       │                 │                 │
       │                 │                 │
       ▼                 ▼                 ▼
  positions          orders          agent_decisions
  balances           executions      debate_results
  exposure            trade_history  risk_decisions
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
                   RISK & AUDIT
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        risk_events            audit_logs

The relational structure allows trading activity, AI reasoning, portfolio state, and risk events to remain connected.

🔗 Database Relationships

A simplified relationship can be represented as:

User
 │
 ├──────────────► Portfolio
 │                    │
 │                    ▼
 │                 Positions
 │                    │
 │                    ▼
 └──────────────► Orders
                      │
                      ▼
                  Executions


AI Agents
    │
    ▼
Agent Decisions
    │
    ▼
Debate Results
    │
    ▼
Final Decision
    │
    ▼
Risk Guardian
    │
    ▼
Audit Log

This structure makes it possible to reconstruct the lifecycle of an autonomous trading decision.

🔄 PostgreSQL Trading Workflow

When an autonomous trading cycle begins:

1. Market information is collected
              ↓
2. AI agents analyze the market
              ↓
3. Bull/Bear agents produce opposing views
              ↓
4. Debate Engine combines the analysis
              ↓
5. Decision Agent generates a proposed action
              ↓
6. RiskGuardian evaluates the proposal
              ↓
7. Approved decision is validated
              ↓
8. Paper order is submitted
              ↓
9. Execution result is recorded
              ↓
10. Portfolio state is updated
              ↓
11. Complete activity is stored in PostgreSQL

This provides persistent state instead of relying only on temporary application memory.

🏗️ System Architecture
                         USER
                           │
                           ▼
                ┌────────────────────┐
                │   Next.js Dashboard │
                │   React + TypeScript│
                └──────────┬─────────┘
                           │
                           ▼
                ┌────────────────────┐
                │     FastAPI        │
                │      Backend       │
                └──────────┬─────────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
        AI Agents      Risk Engine   Alpaca API
             │             │             │
             ▼             ▼             ▼
        Debate Engine  RiskGuardian   Paper Trading
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                    ┌─────────────┐
                    │ PostgreSQL  │
                    │  Database   │
                    └──────┬──────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        Audit Logs     Portfolio      Risk Events
🧠 AI Decision Architecture

TradeGuard AI separates reasoning from authority.

┌─────────────────────────────────────────┐
│              AI REASONING               │
│                                         │
│ MarketScout                             │
│ OptionsAnalyst                          │
│ Bull Agent                              │
│ Bear Agent                              │
│ Options Strategy Agent                  │
│ Risk Agent                              │
│                                         │
│          ↓ Debate Engine ↓              │
│                                         │
│           Decision Agent                │
└───────────────────┬─────────────────────┘
                    │
                    ▼
          ┌──────────────────┐
          │ RISK AUTHORITY   │
          │                  │
          │ RiskGuardian     │
          │ DrawdownGuardian │
          └────────┬─────────┘
                   │
            ┌──────┴──────┐
            │             │
          ALLOW           BLOCK
            │             │
            ▼             ▼
       Order Flow      No Trade
            │
            ▼
       Validation
            │
            ▼
     Alpaca Paper Trading
🔌 Trading Integration

TradeGuard AI integrates with Alpaca Paper Trading for simulated order execution.

The trading layer is responsible for:

Order creation
Order validation
Order submission
Order tracking
Position tracking
Portfolio synchronization
Duplicate-order protection

The architecture is designed so that autonomous trading can be tested without using real capital.

🚫 No-Trade Safety Conditions

TradeGuard AI follows a strict NO TRADE principle.

A trade should not be executed when:

Market data is missing
Market data is stale
Required information is invalid
Risk limits are exceeded
Drawdown enters CRITICAL mode
Order validation fails
Trading conditions cannot be verified
Required dependencies are unavailable
Invalid / Missing / Stale Data
              │
              ▼
           NO TRADE

The system prefers not trading over making an unsafe assumption.

🛠️ Tech Stack
Technology	Purpose
Next.js	Frontend web application
React	Interactive dashboard
TypeScript	Frontend development
Tailwind CSS	UI styling
Python	Backend and trading logic
FastAPI	Backend REST APIs
PostgreSQL	Primary relational database
SQLAlchemy	Database ORM
Alembic	Database migrations
Alpaca API	Paper trading and market integration
LLM Providers	AI agent reasoning
Redis	Caching / real-time support where configured
ChromaDB	Vector storage where configured
Prometheus	Monitoring
Grafana	Metrics visualization
Docker	Containerization
GitHub Actions	CI/CD
GitHub	Version control
⭐ Why PostgreSQL?

PostgreSQL was selected because TradeGuard AI requires a database capable of handling structured and relational financial information.

PostgreSQL provides:
Reliable relational storage
Strong consistency
Structured relationships
Transaction support
Persistent portfolio state
Persistent order history
Persistent risk events
Auditable trading records
Production scalability

For an autonomous trading platform, database persistence is important because the system needs to remember previous decisions, orders, positions, risk events, and audit information.

📂 Project Structure
tradeguard-ai/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── risk/
│   │   ├── trading/
│   │   ├── services/
│   │   └── main.py
│   │
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── package.json
│   └── ...
│
├── docker-compose.yml
├── README.md
└── .gitignore
🔌 Backend API

The FastAPI backend provides endpoints for:

Health
GET /health

Used to verify that the backend is running.

Portfolio
GET /api/portfolio

Returns portfolio information and current state.

Positions
GET /api/positions

Returns currently tracked positions.

Trading
POST /api/orders

Handles validated paper-trading orders.

AI Analysis
GET /api/analysis

Provides AI-generated market/trading analysis.

Risk
GET /api/risk

Returns the current risk and drawdown state.

Audit
GET /api/audit

Retrieves recorded system activity and trading events.

Exact API routes may vary depending on the final backend implementation.

💻 Getting Started
Prerequisites

Make sure you have installed:

Python 3.12+
Node.js
npm
Git
PostgreSQL
Docker (optional)
Alpaca Paper Trading account
1️⃣ Clone the Repository
git clone <YOUR_GITHUB_REPOSITORY_URL>

Move into the project directory:

cd tradeguard-ai
2️⃣ Configure PostgreSQL

Create a PostgreSQL database for the application.

Example:

tradeguard

Then configure the database connection in the backend environment.

Example:

DATABASE_URL=postgresql://username:password@localhost:5432/tradeguard

For a hosted PostgreSQL provider, use the provider's PostgreSQL connection string.

3️⃣ Configure Environment Variables

Create a .env file in the backend.

Example:

DATABASE_URL=postgresql://username:password@localhost:5432/tradeguard

ALPACA_API_KEY=your_alpaca_paper_api_key
ALPACA_SECRET_KEY=your_alpaca_paper_secret_key

ALPACA_BASE_URL=https://paper-api.alpaca.markets

LLM_PROVIDER=your_provider
LLM_API_KEY=your_llm_api_key

DRY_RUN=true
⚠️ Security

Never commit:

.env
API keys
Secret keys
Database passwords
Private credentials

to GitHub.

4️⃣ Install Backend Dependencies
cd backend

Create a virtual environment:

py -3.12 -m venv .venv

Activate it on Windows:

.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt
5️⃣ Initialize PostgreSQL Database

Run the database migrations:

alembic upgrade head

This creates the required PostgreSQL database structure.

6️⃣ Start the Backend
uvicorn app.main:app --reload --port 8001

Backend:

http://localhost:8001

API documentation:

http://localhost:8001/docs
7️⃣ Start the Frontend

Open another terminal:

cd frontend

Install dependencies:

npm install

Start the development server:

npm run dev

Open:

http://localhost:3000
🔄 Complete Application Flow
                   USER
                    │
                    ▼
             Trading Dashboard
                    │
                    ▼
               FastAPI API
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
     Market       AI Agents    Portfolio
      Data           │           │
                     ▼           │
                AI Debate        │
                     │           │
                     ▼           │
               Decision Agent    │
                     │           │
                     ▼           │
                RiskGuardian ◄───┘
                     │
              ┌──────┴──────┐
              ▼             ▼
           ALLOW           BLOCK
              │             │
              ▼             ▼
        Order Validator   Risk Event
              │             │
              ▼             │
       Alpaca Paper API     │
              │             │
              └──────┬──────┘
                     ▼
                PostgreSQL
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      Orders     Portfolio     Audit Logs
🔐 Security Architecture

TradeGuard AI follows a defense-in-depth approach.

AI Safety

AI agents cannot directly override deterministic risk controls.

Trading Safety

The project uses Alpaca Paper Trading during development and demonstration.

Risk Safety

CRITICAL drawdown mode blocks new trades.

Data Safety

Missing, invalid, or stale information results in a NO TRADE decision.

Credential Safety

API credentials are stored through environment variables.

Database Safety

PostgreSQL credentials are never exposed through frontend code.

🧪 Testing

TradeGuard AI includes testing for critical components such as:

Backend APIs
Agent behavior
Risk calculations
Drawdown protection
Order validation
Trading workflow
Database operations
Portfolio state
Autonomous decision flow

The objective is to ensure that autonomous behavior remains predictable even when individual components fail.

📚 What I Learned

Building TradeGuard AI helped me understand how to combine AI with reliable software engineering rather than treating an LLM as the entire system.

Key takeaways:

Multi-agent systems require clearly defined responsibilities.
AI reasoning should be separated from execution authority.
Deterministic risk controls are essential for autonomous financial systems.
PostgreSQL is important for maintaining persistent and relational trading data.
Database design becomes critical when multiple entities such as orders, positions, decisions, and audit events are interconnected.
Paper trading provides a safer environment for testing autonomous workflows.
API failures and missing data must be treated as first-class failure conditions.
Autonomous systems need strong observability and auditability.
A good AI system needs both intelligence and guardrails.
🚧 What Was Harder Than Expected

One of the biggest challenges was coordinating multiple AI components while ensuring that AI-generated decisions could never bypass the safety layer.

Other challenges included:

Connecting frontend and backend reliably
Managing backend port configuration
Integrating Alpaca Paper Trading
Designing the multi-agent communication flow
Maintaining consistent structured outputs
Implementing deterministic risk controls
Managing PostgreSQL persistence
Handling stale or missing market information
Preventing duplicate orders
Maintaining an auditable autonomous workflow

These challenges shaped the final Separation of Powers architecture.

🔮 Future Improvements

Planned improvements include:

Advanced options strategy optimization
More sophisticated portfolio optimization
Real-time market event detection
Improved multi-agent debate
More LLM provider integrations
Advanced backtesting
Historical strategy evaluation
Real-time risk analytics
Improved anomaly detection
Voice-based trading assistant
Mobile-optimized monitoring
Advanced PostgreSQL analytics
More comprehensive observability
Expanded paper-trading scenarios

The long-term goal is to create a robust autonomous trading research platform where AI can reason, analyze, and act within clearly defined safety boundaries.

🏆 What Makes TradeGuard AI Different?
🧠 Multi-Agent Intelligence

Multiple specialized agents analyze the same trading opportunity from different perspectives.

🛡️ AI + Deterministic Safety

The LLM does not have unrestricted control over trading decisions.

📉 Adaptive Risk Protection

Drawdown conditions dynamically change the system's trading behavior.

🐘 PostgreSQL Persistence

Trading, portfolio, AI reasoning, risk events, and audit information are stored in a structured relational database.

🔍 Explainable Decisions

The system maintains an audit trail that helps reconstruct autonomous decisions.

🧪 Paper Trading First

The system is designed around simulated trading for safer development and demonstration.

🔗 Links
GitHub Repository
https://github.com/sathvi1234/tradeguard-ai

Live Demo
https://tradeguard-ai-three.vercel.app/

Demo Video
https://youtu.be/lPzSqNlcFbY?feature=shared

👩‍💻 Authoragent risk architecture.

TradeGuard AI — Let AI reason. Let deterministic risk controls decide.
