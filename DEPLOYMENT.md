# Trade AI production deployment

This repository is **prepared** for deployment. It is **not** automatically deployed from this document. Do not paste real credentials into git, tickets, or chat.

Safety that must stay true in every environment:

- `ALPACA_PAPER_TRADE=true`
- `DRY_RUN=true`
- `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- `live_trading` remains `false`
- Demo User orders persist in PostgreSQL (or local SQLite) and **never** call Alpaca `POST /v2/orders`

Live market data (Alpaca IEX) is **not** live trading.

## Recommended architecture

```
User
  → Next.js frontend (Vercel)
      HTTPS + WSS to
  → FastAPI backend (Render)
      → Managed PostgreSQL (Render)
      → Alpaca paper API + IEX market data (server-side keys)
      → Groq LLM (server-side key)
```

| Layer | Platform | Root directory |
|-------|----------|----------------|
| Frontend | Vercel | `frontend` |
| Backend | Render web service | `backend` |
| Database | Render PostgreSQL | managed |

Do not host FastAPI WebSockets on Vercel serverless. The browser opens `wss://YOUR-BACKEND-DOMAIN/api/v1/stream/market`. Alpaca credentials stay on the backend.

**Cloudflare:** See [`CLOUDFLARE.md`](CLOUDFLARE.md) for compatibility analysis. The existing FastAPI app is **not** suitable for Cloudflare Python Workers; use **Cloudflare Containers** (`cloudflare/` + `backend/Dockerfile`) or keep Render for the API.

## 1. Frontend deployment (Vercel)

1. Create a Vercel project with **Root Directory** `frontend`.
2. Framework: Next.js (`frontend/vercel.json`).
3. Install: `npm install`
4. Build: `npm run build`
5. Start (if self-hosting): `npm run start`
6. Set environment variables **before** the first production build (`NEXT_PUBLIC_*` is inlined at build time):

```
NEXT_PUBLIC_API_URL=https://YOUR-BACKEND-DOMAIN
NEXT_PUBLIC_APP_URL=https://YOUR-FRONTEND-DOMAIN
```

Never set `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `GROQ_API_KEY`, `LLM_API_KEY`, `DATABASE_URL`, or JWT secrets on Vercel.

After the backend URL is known, **rebuild** the frontend.

Custom domain: attach the domain in Vercel, then put that origin in backend `FRONTEND_URL`.

## 2. Backend deployment (Render)

`render.yaml` defines `trade-ai-api` plus `trade-ai-db`. You can also create the same services in the Render dashboard.

Start command:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Health check path: `/health`

Dockerfile alternative (same directory `backend`):

```
docker build -t trade-ai-api ./backend
docker run --env-file backend/.env -e PORT=8001 -p 8001:8001 trade-ai-api
```

Platform `PORT` is used in production. Local development without `PORT` still binds `127.0.0.1:8001`.

## 3. PostgreSQL

Production **must** set `DATABASE_URL`. Demo trades, positions, and history are SQLAlchemy tables (`account`, `positions`, `trades`, plus lab tables). They are not in-memory dictionaries.

Acceptable URL forms:

```
postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
postgres://USER:PASSWORD@HOST:5432/DBNAME
```

The app rewrites `postgres://` and `postgresql://` to `postgresql+psycopg://`.

Local optional Postgres:

```
docker compose up -d postgres
```

If `DATABASE_URL` is empty, the API falls back to `backend/data/demo_ledger.sqlite` for **local development only**. Ephemeral Render disks will lose SQLite data — do not use SQLite in production.

## 4. Environment variables

### Backend (server-side only)

| Variable | Production value |
|----------|------------------|
| `ALPACA_API_KEY` | `<your-paper-api-key>` |
| `ALPACA_SECRET_KEY` | `<your-paper-secret-key>` |
| `ALPACA_PAPER_TRADE` | `true` |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` |
| `ALPACA_DATA_URL` | `https://data.alpaca.markets` |
| `DRY_RUN` | `true` |
| `LLM_PROVIDER` | `groq` |
| `LLM_API_KEY` | `<your-groq-api-key>` (alias: `GROQ_API_KEY`) |
| `LLM_MODEL` | `llama-3.1-8b-instant` |
| `DATABASE_URL` | managed Postgres URL |
| `FRONTEND_URL` | `https://YOUR-FRONTEND-DOMAIN` |
| `CORS_ORIGINS` | optional extra origins (CSV or JSON). Never `*` |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `LOG_LEVEL` | `INFO` |
| `DEMO_USER_EMAIL` | `demo@tradeai.local` |

Startup **refuses** to boot if `ALPACA_PAPER_TRADE` is false or `DRY_RUN` is false.

### Frontend (public)

| Variable | Production value |
|----------|------------------|
| `NEXT_PUBLIC_API_URL` | `https://YOUR-BACKEND-DOMAIN` |
| `NEXT_PUBLIC_APP_URL` | `https://YOUR-FRONTEND-DOMAIN` |

## 5. Database migration

From `backend/` with production `DATABASE_URL` loaded:

```
alembic upgrade head
```

The API also runs `alembic upgrade head` on PostgreSQL at startup, then `create_all` as a non-destructive safety net. It does **not** drop tables.

## 6. CORS

`allow_origins` is never `*`.

- `ENVIRONMENT=production`: only `FRONTEND_URL` and `CORS_ORIGINS`
- any other environment: those plus local Next.js (`http://localhost:3000`, `http://127.0.0.1:3000`, ports 3001/3002)

Set `FRONTEND_URL` to the exact browser origin, including `https://`, with no trailing slash.

## 7. Health check

```
GET https://YOUR-BACKEND-DOMAIN/health
GET https://YOUR-BACKEND-DOMAIN/api/v1/health
GET https://YOUR-BACKEND-DOMAIN/api/v1/alpaca/status
```

Safe fields include `healthy`, `live_market_data`, `paper_trading`, `dry_run`, `live_trading=false`, `llm_configured`, `database=connected`. Responses must not include API keys, tokens, or database passwords.

## 8. Custom domains

1. Point the frontend domain at Vercel.
2. Point the API domain at Render.
3. Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_APP_URL` to those https origins and rebuild the frontend.
4. Set backend `FRONTEND_URL` to the frontend https origin and restart the API.

## 9. WebSockets

Browser → backend only:

`wss://YOUR-BACKEND-DOMAIN/api/v1/stream/market`

Render web services support WebSockets on the same HTTP service. No extra plugin is required. The backend then connects to Alpaca IEX with server-side keys.

HTTPS frontend requires `wss://` (the client derives this from `NEXT_PUBLIC_API_URL`). Mixed content (`https` page + `ws://` API) will fail.

## 10. Local development

Backend (port **8001**):

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# fill paper keys locally; never commit .env
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Frontend (port **3000**):

```
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Optional local Postgres:

```
docker compose up -d postgres
```

Then set `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tradeguard` in `backend/.env`.

## 11. Troubleshooting

| Symptom | Check |
|---------|--------|
| Frontend calls `127.0.0.1` in production | `NEXT_PUBLIC_API_URL` missing at **build** time; rebuild |
| CORS errors | `FRONTEND_URL` must match the browser origin exactly |
| Charts empty / market unavailable | Alpaca paper keys, IEX stream, `/api/v1/alpaca/status` |
| Demo history vanishes after restart | `DATABASE_URL` unset (SQLite on ephemeral disk) |
| WebSocket fails on https site | API URL must be `https://` so the client uses `wss://` |
| App refuses to start | `ALPACA_PAPER_TRADE` or `DRY_RUN` is false |
| LLM review unavailable | `LLM_API_KEY` unset; UI must show unavailable, not invent output |
| CSS missing on `next dev` after `next build` | expected; `distDir` is `.next-dev` in development |

## Restricted LLM reviewer (unchanged)

The browser never calls Groq. The backend reviewer may return only `VETO`, `SHRINK`, or `NO_CHANGE`. It cannot approve a blocked trade, increase size, override risk limits, stale data, `MARKET_CLOSED`, CRITICAL drawdown, execute orders, or read Alpaca credentials. Risk Guardian remains the final deterministic authority.

## Demo User flow (must keep working)

Landing → Sign in → Demo User → Dashboard → select stock → real quote when available → virtual BUY/SELL → history and portfolio update in Postgres. No Alpaca live or paper `POST /v2/orders` on the demo path.
