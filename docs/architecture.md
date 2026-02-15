# architecture.md — System Architecture

## Components

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Telegram    │     │  Mini App    │     │  TON Network  │
│  Bot API     │     │  (Frontend)  │     │  (Blockchain) │
└──────┬───────┘     └──────┬───────┘     └───────┬───────┘
       │                    │                     │
       │ webhook            │ HTTPS               │ RPC
       ▼                    ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│  Bot Service │     │  API Service │     │  TON Provider  │
│  (aiogram)   │────▶│  (FastAPI)   │◀────│  (Toncenter)   │
└──────────────┘     └──────┬───────┘     └───────────────┘
                            │
                    ┌───────┼───────┐
                    ▼       ▼       ▼
              ┌──────┐ ┌───────┐ ┌────────┐
              │ Redis│ │  DB   │ │ Worker │
              │      │ │(PG16) │ │(Celery)│
              └──────┘ └───────┘ └────────┘
```

### Service Descriptions

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| **api** | `backend` | 8000 | FastAPI — main REST API for Mini App and bot |
| **bot** | `bot` | 8001 | aiogram v3 webhook — receives Telegram updates |
| **worker** | `worker` | — | Celery — background tasks (stats refresh, escrow monitoring, timeouts) |
| **db** | `postgres` | 5432 | PostgreSQL 16 — primary data store |
| **redis** | `redis` | 6379 | Broker for Celery, caching, rate limiting |
| **frontend** | `frontend` | 3000 | Vite dev server (dev) / static files (prod) |
| **nginx** | `nginx` | 80/443 | Reverse proxy with TLS termination |

---

## Data Flows

### 1. User Authentication (Mini App → Backend)

```
User opens Mini App
  → Telegram injects initData
  → Frontend sends POST /auth/telegram { initData }
  → Backend verifies HMAC signature
  → Backend upserts User record
  → Backend returns JWT access token
  → Frontend stores token, fetches user profile
```

### 2. Channel Addition (Owner Flow)

```
Owner clicks "Add Channel"
  → Frontend: wizard step 1 (enter channel username)
  → Frontend: wizard step 2 (instructions to add bot as admin)
  → POST /owner/channels { username }
  → Backend calls Bot API: getChatAdministrators(channel)
  → Backend verifies: bot is admin + user is admin
  → Backend stores Channel record
  → Backend calls getChatMemberCount → creates initial StatsSnapshot
  → Returns channel with stats to frontend
```

### 3. Listing Search (Advertiser Flow)

```
Advertiser opens Marketplace
  → GET /market/listings?min_subscribers=1000&language=en&max_price=100
  → Backend queries Listing JOIN Channel JOIN ChannelStatsSnapshot
  → Applies filters, pagination
  → Returns list with embedded stats
  → Frontend renders search results
```

### 4. Deal Creation

```
Advertiser views Listing → clicks "Create Deal"
  → POST /deals { listing_id, campaign_id?, message }
  → Backend creates Deal(status=DRAFT)
  → Backend transitions to NEGOTIATION
  → Bot sends notification to Owner: "New deal request"
  → Owner responds via bot or mini app
```

### 5. Escrow Payment

```
Deal reaches AWAITING_ESCROW_PAYMENT
  → Backend creates escrow contract (EscrowService.create_escrow_for_deal)
  → Returns escrow address + amount to frontend
  → Advertiser connects TON wallet via TON Connect
  → Advertiser sends deposit transaction
  → Worker polls Toncenter for incoming tx
  → Worker confirms deposit: Deal → ESCROW_FUNDED
  → Bot notifies both parties
```

### 6. Auto-posting & Verification

```
Creative approved, time reached
  → Worker: schedule_posting picks up job
  → Bot calls sendMessage/copyMessage to channel
  → Stores Posting(message_id, posted_at)
  → Deal → POSTED → RETENTION_CHECK
  → After retention period (e.g., 24h):
    → Worker: verify_posting checks message still exists & unchanged
    → If OK: Deal → RELEASED, escrow release_to_owner()
    → If removed/changed: Deal → REFUNDED, escrow refund_to_advertiser()
```

---

## Deal Lifecycle Diagram

```
                    ┌───────┐
                    │ DRAFT │
                    └───┬───┘
                        │ advertiser sends
                        ▼
                ┌──────────────┐
                │ NEGOTIATION  │◄─────────────────────────────┐
                └───────┬──────┘                              │
                        │ owner accepts                       │
                        ▼                                     │
              ┌─────────────────┐                             │
              │ OWNER_ACCEPTED  │                             │
              └────────┬────────┘                             │
                       │ system generates escrow              │
                       ▼                                      │
         ┌──────────────────────────┐                         │
         │ AWAITING_ESCROW_PAYMENT  │                         │
         └────────────┬─────────────┘                         │
                      │ deposit confirmed                     │
                      ▼                                       │
              ┌───────────────┐                               │
              │ ESCROW_FUNDED │                               │
              └───────┬───────┘                               │
                      │                                       │
                      ▼                                       │
        ┌──────────────────────────┐                          │
        │ CREATIVE_PENDING_OWNER   │                          │
        └────────────┬─────────────┘                          │
                     │ owner submits                          │
                     ▼                                        │
           ┌─────────────────────┐    ┌────────────────────────────────┐
           │ CREATIVE_SUBMITTED  │───▶│ CREATIVE_CHANGES_REQUESTED     │
           └──────────┬──────────┘    └────────────────┬───────────────┘
                      │ approved                       │ owner re-submits
                      ▼                                └──────────────────┘
           ┌─────────────────────┐
           │ CREATIVE_APPROVED   │
           └──────────┬──────────┘
                      │ time agreed
                      ▼
                ┌───────────┐
                │ SCHEDULED │
                └─────┬─────┘
                      │ bot posts
                      ▼
                 ┌─────────┐
                 │ POSTED  │
                 └────┬────┘
                      │ retention period starts
                      ▼
            ┌─────────────────┐
            │ RETENTION_CHECK │
            └────────┬────────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
        ┌──────────┐  ┌──────────┐
        │ RELEASED │  │ REFUNDED │
        └──────────┘  └──────────┘

Side transitions (from any active state):
  ──→ CANCELLED (mutual or pre-escrow)
  ──→ EXPIRED (inactivity timeout)
  ──→ REFUNDED (post-escrow cancellation)
```

---

## Escrow Flow (On-Chain)

```
1. Deal reaches OWNER_ACCEPTED
   → Backend deploys Escrow contract:
     init(deal_id, advertiser_addr, owner_addr, amount, deadline)

2. Contract state = INIT (0)
   → Backend returns contract address to frontend

3. Advertiser sends TON via TON Connect
   → Contract receives "deposit" message
   → Contract state = FUNDED (1)
   → Contract holds funds

4a. Happy path (delivery verified):
   → Backend calls contract: "release"
   → Contract sends funds to owner address
   → Contract state = RELEASED (2)

4b. Refund path:
   → Backend calls contract: "refund"
   → Contract sends funds back to advertiser
   → Contract state = REFUNDED (3)

4c. Deadline path:
   → Anyone calls "auto_refund" after deadline
   → Contract checks deadline passed & state == FUNDED
   → Contract sends funds back to advertiser
   → Contract state = REFUNDED (3)
```

### Security Considerations

- Platform controller key stored in secrets (never in code).
- Only platform address can call `release` and `refund`.
- `auto_refund` is permissionless but requires deadline to have passed.
- Backend verifies on-chain state before updating DB (never trust client).
- Idempotency: each operation checks contract state before executing.

---

## Infrastructure

### Dev Environment

```yaml
# docker-compose.yml + docker-compose.dev.yml (via ./docker.sh)
services:
  postgres:   # port 5432 exposed, volume for data
  redis:      # port 6379 exposed
  backend:    # uvicorn --reload, mounts ./backend
  bot:        # uvicorn --reload, mounts ./bot
  worker:     # celery worker, mounts ./backend
  frontend:   # vite dev server, mounts ./frontend
  nginx:      # HTTP on :80, dev config
```

### Prod Environment

```yaml
# docker-compose.yml (ENV=production)
services:
  postgres:   # volume, no exposed port
  redis:      # no exposed port
  backend:    # multi-stage build, gunicorn (4 workers)
  bot:        # gunicorn (2 workers)
  worker:     # celery (concurrency=4)
  frontend:   # internal nginx serving static build
  nginx:      # ports 80/443, Let's Encrypt SSL
```

### Routing (Nginx)

```
server {
    listen 443 ssl;
    server_name domain.com;

    /api/  → backend:8000
    /bot/  → bot:8001
    /      → frontend:80
}
```

---

## Production Hardening (Milestone 9)

### Rate Limiting

- Redis-backed rate limiting via `slowapi` with fixed-window strategy.
- Default limit: 60 requests/minute per IP (configurable via `APP_RATE_LIMIT_DEFAULT`).
- Auth endpoints: 10/min. Escrow endpoints: 5/min.
- Returns standard 429 with `Retry-After` header on limit exceeded.

### Audit Log

- `audit_logs` table records significant actions: deal cancel/release/refund, escrow creation, auto-posting, retention verification.
- Each entry: `user_id`, `action`, `entity_type`, `entity_id`, `details` (JSON), `ip_address`, `created_at`.
- Indexes on `(entity_type, entity_id)`, `user_id`, `action` for efficient querying.
- Fire-and-forget writes — audit failures never block the main request.

### Caching Layer

- Redis-based caching utility (`app/core/cache.py`) with `cache_get`, `cache_set`, `cache_delete_pattern`.
- Listing search results cached with configurable TTL (default: 60s, `APP_CACHE_LISTING_TTL`).
- Cache invalidated on listing create, update, and delete operations.
- Pattern-based deletion via `SCAN` for efficient key cleanup.

### Structured Logging

- JSON-formatted logs via `python-json-logger` with fields: `timestamp`, `level`, `name`, `message`.
- Request logging middleware adds: `request_id`, `method`, `path`, `status_code`, `duration_ms`.
- Every request gets a unique `X-Request-ID` header for end-to-end tracing.

### Metrics Endpoint

- `GET /api/metrics` returns business metrics as JSON:
  - `deals_by_status` — count of deals in each status
  - `escrows_by_state` — count of escrows in each on-chain state
  - `postings` — total, posted, verified, retained, failed counts
- Lightweight aggregates, no authentication required (intended for monitoring systems).
