# Trade AI on Cloudflare — compatibility and deployment guide

This document is **additive**. It does not replace `DEPLOYMENT.md`, `render.yaml`, `backend/Dockerfile`, or `frontend/vercel.json`.

**No Cloudflare deployment was performed from this repository.** There is no live Cloudflare URL until you run `wrangler deploy` yourself.

Safety that must remain true on every platform:

- `ALPACA_PAPER_TRADE=true`
- `DRY_RUN=true`
- `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- `live_trading=false`
- Demo User uses the virtual ledger only — never Alpaca `POST /v2/orders`
- Groq / Alpaca keys stay **backend-only**
- Risk Guardian remains final authority; LLM Reviewer returns only `VETO`, `SHRINK`, or `NO_CHANGE`

---

## A. Compatibility summary

| Component | Cloudflare Python Workers | Cloudflare Containers + existing Docker | Recommended |
|-----------|---------------------------|----------------------------------------|-------------|
| **Frontend (Next.js 14)** | N/A | N/A | **Keep Vercel** or optional **Pages static export** (see below) |
| **FastAPI backend** | **Incompatible** | **Compatible** | **Cloudflare Containers** |
| **PostgreSQL** | Requires Hyperdrive + major refactor | **Compatible** (`DATABASE_URL` unchanged) | External Postgres (Neon, Render, etc.) |
| **WebSocket `/api/v1/stream/market`** | **Incompatible** without Durable Objects rewrite | **Compatible** | Containers |
| **Alpaca REST + IEX hub** | **Incompatible** (no long-lived outbound WS task) | **Compatible** | Containers |
| **Groq (httpx)** | Per-request only; not current architecture | **Compatible** | Containers |

### Frontend — vinext / Workers

- Current version: **Next.js 14.0.4** (`frontend/package.json`)
- Cloudflare’s recommended Workers path is **[vinext](https://developers.cloudflare.com/workers/framework-guides/web-apps/nextjs/)**, which targets **Next.js 16** and a Vite-based toolchain.
- **Do not force vinext on this project without upgrading Next.js** and running `npx vinext check` on the upgraded app.
- This frontend is almost entirely **client-rendered** (`'use client'` on 28/29 route pages; no `middleware.ts`, no App Router `route.ts`, no `'use server'`). It talks to the API via `NEXT_PUBLIC_API_URL` and browser WebSocket.
- **Static export to Cloudflare Pages** is a possible *optional* path (`output: 'export'`) but was **not enabled** in `next.config.js` because it is a build-mode change. Keep **`frontend/vercel.json`** as the primary frontend deploy path unless you explicitly validate static export.

**Verdict: Frontend on Cloudflare Workers via vinext → incompatible without Next.js upgrade. Keep Vercel-compatible config.**

### Backend — Python Workers

The existing FastAPI app is **not compatible** with Cloudflare Python Workers as-is:

| Requirement | Current implementation | Workers issue |
|-------------|------------------------|---------------|
| Process model | `uvicorn` long-running server | Workers are request-scoped isolates |
| Lifespan startup | `init_db()`, `autonomous_engine.start()`, `get_iex_hub().start()` | No persistent background tasks after startup |
| IEX stream | `IexStreamHub` — `asyncio.create_task` + infinite loop + Alpaca outbound WebSocket | Outbound long-lived connections not supported in this model |
| Browser WebSocket | In-memory `_clients` set on hub; fan-out broadcast | Requires Durable Objects + hibernation redesign |
| Database | SQLAlchemy **sync** + `psycopg` + Alembic on startup | Sync ORM OK on Workers *only* with Hyperdrive, but startup/migration pattern must change |
| Threading | `threading.Lock` in `demo_ledger`, `db/session` | Not available / unsafe on Workers |
| Filesystem | SQLite fallback, `post_trade_memory.sqlite` | Ephemeral / unsupported for production on Workers |
| Demo ledger | PostgreSQL via `DATABASE_URL` | OK on Containers; fragile on Workers |

**Verdict: FastAPI on Python Workers → incompatible without removing/replacing major features. Do not rewrite for Workers.**

### Backend — Cloudflare Containers

The existing **`backend/Dockerfile`** (Python 3.11, `uvicorn app.main:app`) runs unchanged inside **Cloudflare Containers**. A thin **Worker router** in `cloudflare/` forwards HTTP and WebSocket traffic to the container on port **8001**.

**Verdict: Compatible — recommended Cloudflare backend path.**

### PostgreSQL

- Production must use **PostgreSQL** (`DATABASE_URL`). Do **not** use SQLite or D1 in production.
- On **Containers**: use the same `DATABASE_URL` + `alembic upgrade head` as Render. No D1 substitution.
- On **Python Workers**: would require **Hyperdrive** and redesign of `init_db()` / Alembic; **not approved here**.

**Verdict: Compatible on Containers; incompatible on Python Workers without approval.**

---

## B. Recommended Cloudflare architecture

```
User
  → Next.js (Vercel OR Cloudflare Pages static export)
      HTTPS + WSS to
  → Cloudflare Worker (router in cloudflare/)
      → Cloudflare Container (backend/Dockerfile → uvicorn :8001)
          → PostgreSQL (external managed)
          → Alpaca paper API + IEX (server-side keys)
          → Groq LLM (server-side key)
```

Keep **Render/Vercel** as the documented fallback (`DEPLOYMENT.md`).

---

## C. Files in this repo (Cloudflare-specific)

| File | Purpose |
|------|---------|
| `CLOUDFLARE.md` | This guide |
| `cloudflare/wrangler.jsonc` | Worker + Container binding (routes to `backend/Dockerfile`) |
| `cloudflare/src/index.ts` | Pass-through router to the API container |
| `cloudflare/package.json` | Wrangler + `@cloudflare/containers` dev deps |

Unchanged: `DEPLOYMENT.md`, `render.yaml`, `backend/Dockerfile`, `frontend/vercel.json`.

---

## D. Deploy commands (you run these — not automated here)

### Prerequisites

- Cloudflare account with **Workers** and **Containers** enabled
- Docker running locally (for first `wrangler deploy` with Dockerfile image)
- External **PostgreSQL** URL (not D1)
- Wrangler logged in: `npx wrangler login`

### 1. Backend API on Cloudflare Containers

From repository root:

```bash
cd cloudflare
npm install
npx wrangler deploy
```

Set secrets in the Cloudflare dashboard (or `wrangler secret put`) — **never** in git:

```bash
npx wrangler secret put ALPACA_API_KEY
npx wrangler secret put ALPACA_SECRET_KEY
npx wrangler secret put LLM_API_KEY
npx wrangler secret put DATABASE_URL
```

Also set plain env vars in the dashboard / `wrangler.jsonc` vars section:

- `FRONTEND_URL=https://YOUR-FRONTEND-DOMAIN`
- `ALPACA_PAPER_TRADE=true`
- `DRY_RUN=true`
- `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- `ENVIRONMENT=production`
- `DEBUG=false`

Run migrations **before or after first deploy** (against the same Postgres):

```bash
cd backend
alembic upgrade head
```

Health check after deploy:

```
https://YOUR-WORKER-SUBDOMAIN.workers.dev/health
```

WebSocket (browser):

```
wss://YOUR-WORKER-SUBDOMAIN.workers.dev/api/v1/stream/market
```

### 2. Frontend (recommended: keep Vercel)

Use `DEPLOYMENT.md` §1. Set:

```
NEXT_PUBLIC_API_URL=https://YOUR-WORKER-SUBDOMAIN.workers.dev
NEXT_PUBLIC_APP_URL=https://YOUR-FRONTEND-DOMAIN
```

Rebuild the frontend after the API URL is known.

### 3. Frontend (optional: Cloudflare Pages static export)

Only if you explicitly validate static export:

1. Add `output: 'export'` to `frontend/next.config.js` (or a Cloudflare-only config file).
2. `cd frontend && npm run build` → output in `out/`
3. Connect Cloudflare Pages to the repo with build output directory `out`.

Do **not** use vinext until Next.js is upgraded to 16+ and `vinext check` passes.

### 4. Local validation (no deploy)

```bash
cd cloudflare
npx wrangler deploy --dry-run
```

Requires Docker for Dockerfile build validation.

---

## E. Cloudflare dashboard steps

1. **Workers & Pages** → create / select the Worker deployed from `cloudflare/`.
2. **Settings → Variables** — set non-secret vars; use **Secrets** for keys and `DATABASE_URL`.
3. **Containers** — confirm the image built from `backend/Dockerfile` is healthy.
4. **Custom domain** — attach `api.yourdomain.com` to the Worker; use `https://` in `NEXT_PUBLIC_API_URL`.
5. **Frontend** (Vercel or Pages) — set `NEXT_PUBLIC_*` and rebuild.
6. **CORS** — set backend `FRONTEND_URL` to the exact frontend origin (no `*`).

---

## F. Features that cannot safely run on Cloudflare Python Workers

Do **not** attempt these on Python Workers without a full redesign:

- Long-lived **IEX Alpaca WebSocket** hub (`app/alpaca/iex_stream.py`)
- **Browser market stream** fan-out (`/api/v1/stream/market`)
- **Autonomous engine** background startup (`lifespan` → `autonomous_engine.start()`)
- **Alembic** migrations at process startup on ephemeral isolates
- **Demo ledger** + audit persistence without external Postgres + Containers
- **Threading** locks in demo ledger / DB session
- Local **SQLite** fallback and `post_trade_memory.sqlite` in production

All of the above **do** work on **Cloudflare Containers** with the existing Docker image.

---

## G. Environment variables

### Frontend (public — build time)

```
NEXT_PUBLIC_API_URL=https://YOUR-API-DOMAIN
NEXT_PUBLIC_APP_URL=https://YOUR-FRONTEND-DOMAIN
```

Never: `ALPACA_*`, `LLM_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`.

### Backend (private — Container / Worker secrets)

```
ALPACA_API_KEY=<your-paper-api-key>
ALPACA_SECRET_KEY=<your-paper-secret-key>
ALPACA_PAPER_TRADE=true
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DRY_RUN=true
LLM_API_KEY=<your-groq-api-key>
LLM_PROVIDER=groq
DATABASE_URL=<postgresql-url>
FRONTEND_URL=https://YOUR-FRONTEND-DOMAIN
ENVIRONMENT=production
DEBUG=false
```

---

## H. Test results

Run after any Cloudflare-related change:

```bash
# Backend
cd backend && .venv/Scripts/python.exe -m pytest -q

# Frontend
cd frontend && npm run lint && npm run typecheck && npm run build

# Cloudflare (optional, no account deploy)
cd cloudflare && npx wrangler deploy --dry-run
```

See the latest agent report for pass/fail counts.

---

## I. Deployment status

**Not deployed.** This repository only adds configuration and documentation. A live URL exists only after you run `wrangler deploy` and configure DNS/secrets yourself.
