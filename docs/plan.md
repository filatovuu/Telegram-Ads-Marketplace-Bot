# plan.md — Telegram Ads Marketplace Mini App (MVP)

> **Goal:** Build an MVP application (Telegram Mini App + text bot) for an advertising marketplace in Telegram channels, featuring verified analytics, a unified deal workflow, on-chain TON escrow (Tact), creative approval, and auto-posting with retention verification.

---

## 0) Final Product: What Should Work in MVP

### Core Entities
- **User** (Telegram user)
- **Role context**: Advertiser / Channel Owner (switchable roles)
- **Channel** (Telegram channel added by the owner)
- **ChannelTeam** (PR manager flow, multiple managers per channel)
- **Listing** (channel offer: price, terms, formats)
- **Campaign** (advertiser request)
- **Deal** (unified deal: negotiation → escrow → approval → autopost → verify → release/refund)
- **Creative** (content for placement + version + statuses)
- **Escrow** (TON on-chain escrow: contract + addresses + transactions)
- **Posting** (publication record, retention verification)
- **Dispute** (this version: auto-rules only, no manual arbitration)

### Communication Channels
- **Mini App**: catalog interface, filters, forms, statuses
- **Text Bot**: deal messages, notifications, confirmations (no in-app chat inside mini-app)

### Language Support
- i18n out of the box: **English + Russian**
- Locale determined by Telegram (language_code) + UI setting

### UI/UX
- Modern iOS-like design
- UI built on **@telegram-tools/ui-kit 0.2.4 (https://www.npmjs.com/package/@telegram-tools/ui-kit)**
- Separate toggles and navigation per role:
  - Advertiser UI
  - Channel Owner UI
- Instant role switching (no logout required)

### Deploy
- Everything runs via **docker compose**

---

## 1) Recommended Technology Stack

### Backend (core)
- **Python 3.12**
- **FastAPI (async)**
- **SQLAlchemy 2.0 async** + Alembic
- **PostgreSQL 16**
- **Redis** (cache, rate-limit, background jobs)
- **Celery** (or arq/RQ) for background tasks
- **Pydantic v2**

### Telegram
- **Bot API**: aiogram v3 (webhook mode)
- Telegram Mini App: frontend in TypeScript

### Frontend (Mini App)
- **TypeScript**
- **Vite**
- **@telegram-tools/ui-kit**
- **i18next** (or equivalent) + JSON dictionaries
- Telegram WebApp SDK

### TON (on-chain escrow)
- TON Connect (frontend)
- Backend: TON library (chosen at implementation stage, e.g. tonpy/pytonlib/tonutils)
- **Escrow smart contract** (FunC/Tact) + deployment
- Transaction indexing: TON API provider (Toncenter/tonapi)

### Observability
- Structured logging (JSON)
- Sentry (error tracking)
- Prometheus + Grafana (metrics)
- Loki (logs) — optional

---

## 2) Architecture (High-Level)

### Components
1. **api** — core backend (FastAPI)
2. **bot** — aiogram webhook service (can be a separate container)
3. **worker** — background tasks (Celery)
4. **db** — PostgreSQL
5. **redis** — broker + cache
6. **frontend** — mini app (static build)
7. **reverse-proxy** — Caddy or Nginx (TLS + routing)

### Core Data Flows
- Mini App → Backend API → DB
- Text Bot → Backend API → DB
- Backend → Telegram API (stats, autopost, verify)
- Backend ↔ TON chain (escrow + transaction verification)

---

## 3) Deal State Machine

> Important: The state machine must be **explicit** (status table + allowed transitions + validator).

### Statuses
- `DRAFT`
- `NEGOTIATION`
- `OWNER_ACCEPTED`
- `AWAITING_ESCROW_PAYMENT`
- `ESCROW_FUNDED`
- `CREATIVE_PENDING_OWNER`
- `CREATIVE_SUBMITTED`
- `CREATIVE_CHANGES_REQUESTED`
- `CREATIVE_APPROVED`
- `SCHEDULED`
- `POSTED`
- `RETENTION_CHECK`
- `RELEASED`
- `REFUNDED`
- `CANCELLED`
- `EXPIRED`

### Transitions (examples)
- NEGOTIATION → OWNER_ACCEPTED
- OWNER_ACCEPTED → AWAITING_ESCROW_PAYMENT
- AWAITING_ESCROW_PAYMENT → ESCROW_FUNDED
- ESCROW_FUNDED → CREATIVE_PENDING_OWNER
- CREATIVE_SUBMITTED → CREATIVE_APPROVED
- CREATIVE_APPROVED → SCHEDULED
- SCHEDULED → POSTED
- POSTED → RETENTION_CHECK
- RETENTION_CHECK → RELEASED
- Any active status → EXPIRED (timeout)
- ESCROW_FUNDED → REFUNDED (if cancelled before publication)

---

## 4) Development Milestones

8 milestones below. Each milestone includes:
- Backend
- UI (Mini App)
- Bot flow
- i18n
- Tests
- Definition of Done

---

# Milestone 1 — Project Foundation (Infrastructure)

## 1.1 Repository and Structure
- Monorepo:
  - `/backend`
  - `/bot`
  - `/frontend`
  - `/infra`
  - `/docs`

## 1.2 Docker Compose (dev + prod)
- Services:
  - postgres
  - redis
  - backend (FastAPI)
  - bot (aiogram webhook)
  - worker (celery)
  - frontend (build + serve)
  - reverse-proxy (Caddy/Nginx)

## 1.3 Secrets and Configuration
- `.env.example`
- Separation:
  - dev
  - prod

## 1.4 Database and Migrations
- Alembic init
- First migration: users, roles, sessions

## 1.5 i18n Framework
- Frontend:
  - i18next
  - `locales/en/*.json`
  - `locales/ru/*.json`
- Backend:
  - locale stored in user profile

### Definition of Done
- `docker compose up` starts all services
- Backend responds to `/health`
- Bot accepts webhooks (stub)
- Frontend opens as a Telegram WebApp (stub)
- Migrations are applied automatically

---

# Milestone 2 — Telegram Auth + Roles + Switching

## 2.1 Authorization via Telegram WebApp initData
- Backend endpoint: `POST /auth/telegram`
- initData signature verification
- User creation/update
- JWT access token issuance

## 2.2 Roles (Advertiser / Owner)
- User has:
  - `active_role`
  - `available_roles` (always both)
- Endpoint:
  - `POST /me/role` (role switch)

## 2.3 UI: Role Switching
- Global role toggle button/switch
- Tabs change dynamically:
  - Advertiser: Campaigns, Deals, Search, Profile
  - Owner: Channels, Listings, Deals, Profile

## 2.4 Bot: Start Menu
- `/start`
- Buttons:
  - Open Mini App
  - My Deals
  - Help

## 2.5 i18n
- All UI and bot message strings go through dictionaries only

### Definition of Done
- User opens the mini app
- Authenticates via Telegram initData
- Can switch roles without re-login
- UI changes navigation based on role

---

# Milestone 3 — Channel Owner Role: Channels, Team, Listings

## 3.1 Backend: Channel Management
### Endpoints
- `POST /owner/channels`
- `GET /owner/channels`
- `GET /owner/channels/{id}`
- `PATCH /owner/channels/{id}`
- `DELETE /owner/channels/{id}`

### Logic
- Channel can only be added if:
  - User is a channel admin
  - Bot is added as admin
- Store:
  - channel_id
  - username
  - title
  - invite_link (optional)
  - verified_stats snapshot

## 3.2 PR Manager Flow (ChannelTeam)
- Entities:
  - ChannelTeamMember(user_id, channel_id, rights)
- Functionality:
  - Owner can add a manager by username/id
  - Bot verifies the manager is actually a channel admin (if required)
- Mandatory permission checks:
  - Before final actions (accept deal, autopost, payout)

## 3.3 Listings (Offers)
- Listing is linked to a channel
- Pricing:
  - MVP: 1 format (post)
  - Prod: free-form formats (JSON)
- Filterable fields:
  - min_price
  - language
  - subscribers
  - avg_views

## 3.4 Owner UI (Mini App)
### Screens
- Channels list
- Add channel wizard:
  - Step 1: select channel
  - Step 2: add bot as admin
  - Step 3: verify stats
- Channel details
- Listings:
  - Create/edit
  - Pricing
  - Availability calendar (can be added later)

## 3.5 Bot Messages (Owner)
- Notifications about new requests
- Deal acceptance confirmation
- Creative upload requests

### Tests
- Unit tests:
  - Channel ownership validator
  - Listing filters
- Integration tests:
  - Create channel → verify

### Definition of Done
- Owner adds a channel
- Bot verifies permissions
- Listing is created
- Listing is visible in search

---

# Milestone 4 — Verified Telegram Analytics (Channels)

## 4.1 Telegram API Integration
- Bot must be able to:
  - Get basic channel info
  - Verify admin permissions
  - Retrieve available metrics

## 4.2 Stored Metrics (minimum)
- Subscribers
- Telegram Premium subscribers
- avg_views / reach (based on previous and new posts over 1h/24h/7d)
- Language charts
- Premium stats (if available)
- Additional:
  - Growth (7/30 days)
  - Post frequency
  - Any other available metrics that may interest advertisers

## 4.3 Snapshot Model
- `ChannelStatsSnapshot`
- Periodic refresh task:
  - Every N hours
- Manual refresh from UI

## 4.4 UI Display
- Charts (simple)
- "Verified by Telegram" badge (if the channel has one)

### Tests
- Telegram API mocks
- Snapshot creation

### Definition of Done
- Stats are pulled automatically
- Used in filters
- Displayed in UI

---

# Milestone 5 — Advertiser Role: Campaigns, Search, Applications

## 5.1 Campaigns (Requests)
### Endpoints
- `POST /advertiser/campaigns`
- `GET /advertiser/campaigns`
- `GET /advertiser/campaigns/{id}`
- `PATCH /advertiser/campaigns/{id}`
- `DELETE /advertiser/campaigns/{id}`

### Campaign Fields
- title
- description / brief
- category
- target language
- budget range
- desired publish window
- links, restrictions

## 5.2 Search Listings
- `GET /market/listings`
- Filters:
  - Price range
  - Subscribers min
  - Avg views min
  - Language
  - Category tags
  - Any other available channel filters

## 5.3 Apply to Campaign / Request Deal
- Advertiser can:
  - Create a deal directly from a listing
  - Or create a campaign and wait for responses

## 5.4 Advertiser UI (Mini App)
### Screens
- Marketplace search
- Listing details
- Create campaign wizard
- Campaign details + applicants
- Deals list

## 5.5 Bot Messages (Advertiser)
- Notifications about new responses
- Escrow payment confirmation
- Approve / request edits

### Tests
- Listing search
- Campaign CRUD

### Definition of Done
- Advertiser creates a campaign
- Finds a listing
- Creates a deal

---

# Milestone 6 — Unified Deal Workflow (Negotiations, Statuses, Notifications)

## 6.1 Deal Model
- Unified model for both scenarios:
  - Listing → deal
  - Campaign → deal

## 6.2 Negotiation
- Negotiations are conducted through the text bot
- Entity:
  - DealMessage(deal_id, sender_user_id, text, created_at)

## 6.3 Status Machine
- `deal_status` table
- Transition validator
- Illegal transition prevention

## 6.4 Timeouts
- Inactivity timeout:
  - No activity for X hours → EXPIRED
- Scheduled publish timeout:
  - If not published on time → REFUND

## 6.5 Deal UI
- Unified deals screen for each role
- Deal card:
  - Status
  - Escrow state
  - Creative state
  - Next action

## 6.6 Bot Notifications
- Every status change → notification to both parties

### Tests
- Status transition tests
- Timeout job tests

### Definition of Done
- Both roles complete negotiations
- Statuses change strictly by rules
- Notifications work

---

# Milestone 7 — TON Escrow (On-Chain) + TON Connect

> Requirement: **Real on-chain escrow via smart contract**.

## 7.1 Escrow Architecture
- For each deal:
  - Escrow contract instance is created
  - Unique address is generated
- Participants:
  - Advertiser wallet
  - Owner payout wallet (TON address)
  - Platform controller (multisig / admin key)

## 7.2 Escrow Smart Contract
### Required Functions
- init(deal_id, advertiser, owner, amount, deadline)
- deposit()
- confirm_delivery() (called by backend after verification)
- release_to_owner()
- refund_to_advertiser()
- auto_refund_on_deadline()

### Important
- Contract must be as simple as possible
- Store minimal data in the contract
- Store deal_id as uint64

## 7.3 Backend TON Module
- Service:
  - `EscrowService`
- Functions:
  - create_escrow_for_deal()
  - get_escrow_state()
  - verify_deposit()
  - trigger_release()
  - trigger_refund()

## 7.4 TON Connect (Frontend)
- Wallet connection
- Sending deposit transaction to escrow address
- TX hash confirmation → backend

## 7.5 Transaction Monitoring
- Worker job:
  - Poll tonapi/toncenter
  - Confirm deposit
  - Confirm release/refund

## 7.6 Security
- Hot wallet only for fees (fee=0 for now)
- Keys:
  - Store in secrets
  - Rotation plan
- Anti-double-spend checks

### Tests
- Unit: escrow state parsing
- Integration: TON sandbox (if possible)
- Fallback: mocked provider

### Definition of Done
- Advertiser pays via TON Connect
- Backend confirms deposit
- Escrow changes state
- Release/refund executed on-chain

---

# Milestone 8 — Creative Approval + Auto-Posting + Verification

## 8.1 Creative Workflow
- Advertiser sets the brief
- Owner submits a draft (text + entities + optional media)
- Advertiser:
  - Approve
  - Request edits
- Versions:
  - CreativeVersion(1..n)

## 8.2 UI
- Owner:
  - Post editor
  - Preview
- Advertiser:
  - Approve/reject UI
  - Edit history

## 8.3 Scheduling
- Owner proposes publication time
- Advertiser confirms
- Schedule job is created

## 8.4 Auto-Posting
- Bot publishes message to the channel
- Store:
  - message_id
  - posted_at
  - raw payload

## 8.5 Verification
- Worker checks:
  - Message exists
  - Text hasn't been modified
  - Media hasn't been deleted
  - Retention time has passed (e.g. 24 hours)

## 8.6 Release
- After retention check:
  - Backend calls escrow release_to_owner()

## 8.7 Refund Rules
- If post is not published by deadline
- If post is deleted before retention period
- If owner loses admin permissions before publication

### Tests
- Posting mocks
- Retention logic tests
- Verification job tests

### Definition of Done
- Full deal cycle:
  - Escrow funded
  - Creative approved
  - Post published
  - Verified
  - Funds released

---

# Milestone 9 — Production Hardening (Security, Load, Support)

## 9.1 Security
- Rate limiting
- initData replay protection
- Strict RBAC by roles
- Audit log:
  - Critical operations (escrow, posting, cancel)

## 9.2 Reliability
- Retry policies (Telegram, TON)
- Idempotency keys for payments and publications
- Dead-letter queue for tasks

## 9.3 Performance
- PostgreSQL indexes
- Listing search cache
- Pagination everywhere

## 9.4 UX Polish
- Skeleton loading
- Empty states
- Clear error messages

## 9.5 Observability
- Structured logs
- Metrics:
  - Deals created
  - Escrow funded
  - Releases/refunds
  - Posting failures

## 9.6 Documentation
- README:
  - Run locally
  - Deploy
  - Env vars
- SECURITY.md
- ARCHITECTURE.md
- API docs (OpenAPI)

### Definition of Done
- Service is resilient to failures
- Can be deployed on a VPS
- Can be maintained without an admin panel

### README:
- Summary
- Key Features
- Technology Stack
- Installation:
  - Prerequisites
  - Setup
  - Verification
- Configuration
  - Configuration guide for deploying the application locally or on a server (include available environment variables with descriptions)
- Usage
  - Available Commands (include make build, make run, etc.)
  - Components:
    - Backend
    - Frontend
- Docker:
  - Container descriptions
- Testing
- Future Plans
- AI Authorship

---

## 5) Repository Structure

```
/backend
  /app
    /api
    /core
    /db
    /models
    /services
    /workers
    /tests
  alembic/
/bot
  /app
  /handlers
  /templates
  /tests
/frontend
  /src
    /ui
    /screens
    /i18n
    /api
/infra
  docker-compose.yml
  docker-compose.prod.yml
  Caddyfile
/docs
  plan.md
  ARCHITECTURE.md
  API.md
```

---

## 6) Checklists (Mandatory)

### 6.1 Checklist: Owner Role
- [x] Adding a channel works
- [x] Admin permission verification works
- [x] Stats are verified
- [x] Listing is created and visible in search
- [x] Manager can be added
- [x] Critical actions trigger permission re-checks

### 6.2 Checklist: Advertiser Role
- [x] Campaign CRUD
- [x] Channel search with filters
- [x] Deal creation
- [x] Escrow payment via TON Connect
- [x] Creative approval

### 6.3 Checklist: Deal Lifecycle
- [x] Statuses are correct
- [x] Timeouts work
- [x] Auto-posting works
- [x] Retention verification works
- [x] Release/refund on-chain

---

## 7) Important Decisions to Document

- Why the specific TON provider was chosen
- How the escrow contract is implemented
- Which Telegram metrics are actually available via API
- Telegram limitations (what cannot be automated)
- Which parts require manual moderation (in the future)

---

## 8) Definition of Production-Ready

The application is considered MVP-ready if:
- Everything runs via docker compose
- Webhook and mini app work on an HTTPS domain
- All critical operations are idempotent
- Error monitoring is in place
- Escrow is confirmed on-chain
- Auto-posting is verified and protected against deletion
- i18n fully covers UI + bot
