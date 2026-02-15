# Telegram Ads Marketplace Bot

MVP Telegram Mini App + text bot for buying and selling advertising in Telegram channels. Features: channel analytics, a 16-status deal workflow with state machine, on-chain TON escrow (Tact), creative approval flow and auto-posting with retention verification.

## Key Features

- **Channel Catalog** — Owners connect Telegram channels with verified analytics (subscriber growth, views, engagement, posting frequency)
- **Marketplace Search** — Advertisers find channels by price, language, subscribers, views, growth rate
- **16-Status Deal Workflow** — Explicit state machine with role-based transitions, from DRAFT through escrow, creative approval, posting, and retention verification
- **On-Chain TON Escrow** — Each deal gets a dedicated Tact smart contract; deposit, platform-controlled release and refund, with backend inactivity timeouts
- **Creative Approval** — Versioned creative submissions with approve/request-changes loop
- **Auto-Posting** — Celery workers post to channels via Bot API at scheduled time
- **Retention Verification** — Automated check that posts remain unchanged during retention period; triggers escrow release or refund
- **Channel Team Management** — RBAC with Owner/Manager/Viewer roles, granular permissions (accept deals, post, payout), Telegram admin re-verification before critical actions
- **Dual Interface** — Telegram Mini App (React) + text bot (aiogram) with FSM
- **i18n** — English + Russian, stored per user

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Node.js 20+, Python 3.12+ for local development outside Docker

### Initial Setup

```bash
git clone <repo-url>
cd Telegram-Ads-Marketplace-Bot
make setup          # Interactive wizard — fills in all env variables
```

All environment variables are documented in the [configuration guide](config/env_template/readme.md).

### Development

Hot-reload, source volumes, Postgres/Redis ports exposed to host, HTTP-only nginx.

```bash
make build          # Build dev images
make dev            # Start all services (foreground)
make dev-d          # Start all services (detached)
```

| What | Where |
|------|-------|
| Mini App | http://localhost |
| Swagger UI | http://localhost/api/docs |
| ReDoc | http://localhost/api/redoc |
| OpenAPI JSON | http://localhost/api/openapi.json |
| Metrics | http://localhost/api/metrics |
| Health | http://localhost/api/health |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

### Production

Gunicorn workers, no source mounts, nginx with SSL.

```bash
# 1. Set DOMAIN in config/env/.core.env (nginx picks it up automatically)
# 2. Place SSL certificates:
#      config/certs/fullchain.pem
#      config/certs/privkey.pem

make build-prod     # Build production images
make prod-d         # Start all services (detached)
make health         # Verify all services are running
```

### Local Development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install && npm run dev

# Bot
cd bot
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Make Commands

`make setup` — interactive env setup wizard

### Development

| Command | Description |
|---------|-------------|
| `make build` | Build dev images |
| `make dev` | Start dev stack (foreground) |
| `make dev-d` | Start dev stack (detached) |
| `make stop` | Stop containers |
| `make down` | Stop and remove containers |
| `make restart` | Restart containers |
| `make logs` | Follow logs |

### Production

| Command | Description |
|---------|-------------|
| `make build-prod` | Build production images |
| `make prod` | Start prod stack (foreground) |
| `make prod-d` | Start prod stack (detached) |
| `make prod-down` | Stop prod stack |
| `make prod-restart` | Restart prod stack |
| `make prod-logs` | Follow prod logs |
| `make health` | Check all services health |

### Testing, Quality & Database

| Command | Description |
|---------|-------------|
| `make test` | Run all tests |
| `make test-backend` | Run pytest |
| `make test-frontend` | Run vitest |
| `make lint` | Run ruff linter |
| `make format` | Run ruff formatter |
| `make migrate` | Apply database migrations |
| `make generate-migration msg="desc"` | Create new Alembic migration |

## Architecture

- [Architecture](docs/architecture.md) — system components, data flows, infrastructure
- [Modules](docs/modules.md) — all models, services, handlers
- [Security](docs/security.md) — auth, RBAC, rate limiting, escrow security

```
┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│  Telegram    │     │  Mini App    │     │  TON Network  │
│  Bot API     │     │  (Frontend)  │     │  (Blockchain) │
└──────┬───────┘     └──────┬───────┘     └───────┬───────┘
       │ webhook            │ HTTPS               │ RPC
       ▼                    ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│  Bot Service │     │  API Service │     │  TON Provider │
│  (aiogram)   │────▶│  (FastAPI)   │◀────│  (Toncenter)  │
└──────────────┘     └──────┬───────┘     └───────────────┘
                            │
                    ┌───────┼───────┐
                    ▼       ▼       ▼
              ┌──────┐ ┌───────┐ ┌────────┐
              │ Redis│ │  DB   │ │ Worker │
              │      │ │(PG16) │ │(Celery)│
              └──────┘ └───────┘ └────────┘
```

| Service | Technology | Purpose |
|---------|-----------|---------|
| **API** | FastAPI (Python 3.12, async) | REST API for Mini App and bot |
| **Bot** | aiogram v3 (webhook mode) | Telegram updates, notifications, auto-posting |
| **Worker** | Celery + Redis | Background tasks (stats refresh, escrow monitoring, timeouts, auto-posting, retention verification) |
| **Frontend** | Vite + React + TypeScript | Telegram Mini App UI |
| **Database** | PostgreSQL 16 | Primary data store |
| **Cache/Broker** | Redis 7 | Celery broker, rate limiting, caching |
| **Reverse Proxy** | Nginx | TLS termination, routing, security headers, gzip |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TON smart contract | **Tact** (not FunC) | Simpler syntax, better documentation, safer defaults |
| Channel analytics | **Bot API + MTProto** | Bot API for basic data; MTProto (Pyrogram) for views, reactions, forwards, and post verification |
| Auth | **Telegram initData HMAC → JWT** | Native Telegram verification, stateless tokens |
| State machine | **Explicit transition table** | Single source of truth, illegal transitions raise exceptions |
| i18n | **i18next (frontend) + locale in DB** | EN + RU from day one |
| Background tasks | **Celery + Redis** | Mature, reliable for periodic tasks and monitoring |
| Channel RBAC | **Owner/Manager/Viewer** | Granular permissions + Telegram admin re-check with Redis cache |
| Rate limiting | **slowapi + Redis** | Per-endpoint limits with fixed-window strategy |
| Logging | **JSON structured logs** | Machine-parseable, request tracing via X-Request-ID |
| Retry | **tenacity** | Exponential backoff for Telegram API and TON RPC calls |

## MTProto Integration

The project uses **MTProto** (via [Pyrogram](https://pyrogram.org)) alongside the standard Bot API. This is necessary because Bot API has significant limitations for channel analytics:

| Capability | Bot API | MTProto |
|-----------|---------|---------|
| Subscriber count | Yes | Yes |
| Post views | Only via `channel_post` webhook (real-time, no history) | Full history for any channel |
| Reactions count | No | Yes |
| Forward count | No | Yes |
| Post edit detection | Only via `edited_channel_post` webhook (real-time) | Read any message on demand |
| Backfill historical posts | No | Yes |

**Why MTProto is needed:**

- **Channel analytics** — Bot API can only count subscribers and receive new posts via webhooks. It cannot read historical posts or retrieve view/reaction/forward counts for existing messages. MTProto fetches the last 100 posts with full metrics, enabling computed stats like average views, engagement rate, reach percentage, and posting frequency.
- **Retention verification** — after an ad is posted, the system must verify that the post was not deleted or edited during the retention period. Bot API cannot read arbitrary channel messages by ID. MTProto reads the specific message and compares its content against the approved creative.
- **Graceful degradation** — MTProto is optional. If not configured (no `API_ID`, `API_HASH`, `SESSION_STRING`), the system continues with Bot API data only. All MTProto calls are wrapped in try/except and log failures without crashing.

MTProto client runs as a singleton with lazy initialization, `no_updates=True` mode (read-only, no event handling), and automatic FloodWait retry.

## Project Structure

```
/backend          FastAPI async API
  /app/api          Route handlers (auth, owner, advertiser, market, escrow, metrics)
  /app/core         Config, security, rate limiting, RBAC, caching, middleware
  /app/db           Database engine, base model
  /app/models       SQLAlchemy ORM models (14 models)
  /app/services     Business logic (deal, listing, channel, escrow, creative, posting, team_permissions, audit)
  /app/workers      Celery tasks (stats, timeouts, escrow monitor, posting, verification)
  /alembic          Database migrations
  /tests            pytest async tests

/bot              aiogram v3 webhook bot
  /app              Bot setup, webhook endpoint
  /handlers         Command, callback, FSM handlers
  /services         Backend API client
  /states           FSM states for multi-step flows
  /middleware        Auth, i18n middleware
  /templates        Message templates (EN, RU)

/frontend         Vite + React + TypeScript
  /src/screens      Page components (Deals, Search, Channels, etc.)
  /src/ui           Reusable UI components (Skeleton, EmptyState, ErrorMessage, SubscribersChart)
  /src/api          Typed HTTP client with timeout, retry, 429 backoff
  /src/i18n         i18next locales (EN, RU)
  /src/context      Auth, Theme context providers
  /src/hooks        Custom hooks (useTonEscrow)

/config           Docker, nginx, and env template configs
/docs             Architecture, specifications, guidelines
```

## Known Limitations

- **No Telegram Statistics API access**: Channel analytics use Bot API and MTProto (user session via Pyrogram) for views, reactions, forwards. Native Statistics API (available only to large channels) is not integrated; deeper metrics require TGStat or similar services.
- **No manual dispute resolution**: Only auto-rules (inactivity timeout, retention check). Manual arbitration requires an admin panel.
- **Single format per listing**: Multi-format pricing per listing is deferred.
- **No admin panel**: All operations go through the Mini App and bot.

## Future Plans

### Post Types & Formats
- **Repost support** — deals for reposting advertiser's existing channel posts (forward / quote repost)
- **Stories support** — short-lived story ads with separate pricing and retention rules
- **Multi-format listings** — multiple ad formats per channel (e.g. 1/24h post, 2/48h post, repost, story) with independent pricing

### Retention & Verification
- **First-position retention** — configurable requirement for the post to stay as the latest (top) post in the channel for a specified period (e.g. 1 hour) without new posts pushing it down
- **Negotiable retention terms** — owner and advertiser can agree on custom retention duration and first-position hold time as part of the deal terms
- **Graceful edit handling** — instead of immediate refund on post edit, ask the advertiser whether the edit was approved; only trigger refund if the advertiser rejects the change

### Disputes & Moderation
- **Admin panel** — web dashboard for platform operators: user management, deal oversight, manual interventions, system metrics
- **Dispute resolution** — manual arbitration flow where either party can open a dispute, provide evidence, and an admin makes a ruling on escrow release/refund
- **Report system** — ability to report channels, users, or creatives for policy violations

### Analytics & Insights
- **Advanced channel analytics** — deeper engagement metrics, audience overlap detection, best posting time recommendations
- **Campaign performance reports** — post-deal analytics for advertisers: actual views, engagement, ROI relative to price paid
- **Pricing recommendations** — suggested pricing based on channel stats, market averages, and historical deal data

### Platform & Payments
- **Multi-currency support** — accept USDT (TON jetton).
- **Rating & review system** — mutual ratings after deal completion; reputation scores visible in marketplace search
- **Referral program** — invite bonuses for bringing new channels or advertisers to the platform
- **Channel recommendation engine** — personalized channel suggestions for advertisers based on past deals and campaign criteria

### Workflow Improvements
- **Bulk deal management** — create and manage multiple deals from a single campaign in batch
- **Recurring deals** — subscription-style agreements for periodic postings with auto-renewal
- **Creative templates** — reusable creative templates for advertisers running similar ads across multiple channels

## License

Private. All rights reserved.
