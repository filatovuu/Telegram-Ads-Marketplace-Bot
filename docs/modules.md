# modules.md — Module Map

## Backend Modules (`/backend/app/`)

### `api/` — FastAPI Routers
| Module | Responsibility |
|--------|---------------|
| `auth.py` | `POST /auth/telegram` — initData verification → JWT |
| `me.py` | `GET /me`, `POST /me/role`, `PATCH /me/wallet` — profile, role switching, wallet |
| `owner_channels.py` | CRUD `/owner/channels` — channel management, team CRUD (add/update/remove members) |
| `owner_listings.py` | CRUD `/owner/listings` — listing management |
| `advertiser_campaigns.py` | CRUD `/advertiser/campaigns` — campaign management |
| `market.py` | `GET /market/listings` — public search with filters |
| `deals.py` | Deal lifecycle endpoints (both roles) |
| `escrow.py` | `POST /escrow/deals/{id}/create`, `GET /escrow/deals/{id}`, `POST /escrow/deals/{id}/confirm-deposit` |
| `creative.py` | Creative submission, approval, version history |
| `health.py` | `GET /health` — liveness/readiness probe |

### `core/` — Configuration & Cross-cutting
| Module | Responsibility |
|--------|---------------|
| `config.py` | `Settings(BaseSettings)` — env-based config |
| `security.py` | initData verification, JWT encode/decode, RBAC deps |
| `deps.py` | Common FastAPI dependencies (db session, current user, role check) |
| `exceptions.py` | Custom exception classes + handlers |

### `db/` — Database Layer
| Module | Responsibility |
|--------|---------------|
| `session.py` | Async engine & session factory |
| `base.py` | `DeclarativeBase`, common mixins (timestamps, soft delete) |

### `models/` — SQLAlchemy ORM Models
| Model | Key Fields |
|-------|-----------|
| `User` | telegram_id, username, locale, active_role, wallet_address, created_at |
| `Channel` | channel_id, owner_id, username, title, is_verified |
| `ChannelTeamMember` | user_id, channel_id, role (manager/viewer), can_accept_deals, can_post, can_payout |
| `ChannelStatsSnapshot` | channel_id, subscribers, avg_views, captured_at |
| `Listing` | channel_id, price, currency, format, language, is_active |
| `Campaign` | advertiser_id, title, brief, budget_min, budget_max, target_language |
| `Deal` | listing_id, campaign_id, advertiser_id, owner_id, status, escrow_address |
| `DealMessage` | deal_id, sender_id, text, created_at |
| `Creative` | deal_id, version, text, media_url, status |
| `Escrow` | deal_id, contract_address, advertiser_address, owner_address, platform_address, amount, deadline, on_chain_state, tx hashes, funded/released/refunded_at |
| `Posting` | deal_id, channel_id, message_id, posted_at, verified_at, retained |
| `AuditLog` | user_id, action, entity_type, entity_id, details, created_at |

### `services/` — Business Logic
| Service | Responsibility |
|---------|---------------|
| `auth_service.py` | initData validation, user upsert, JWT issuance |
| `channel_service.py` | Channel CRUD, admin verification via Bot API, team member management (add/update/remove) |
| `listing_service.py` | Listing CRUD, search with filters |
| `campaign_service.py` | Campaign CRUD |
| `deal_service.py` | Deal creation, status transitions (delegates to state machine), team-aware access control |
| `deal_state_machine.py` | Transition table, guards, validator |
| `ton/escrow_service.py` | EscrowService: create_escrow_for_deal, get_escrow_for_deal, verify_deposit, trigger_release, trigger_refund |
| `ton/client.py` | TonClient: async httpx wrapper for Toncenter API v3 (get_account_state, get_transactions, run_get_method, send_boc) |
| `ton/wallet.py` | PlatformWallet: mnemonic → keypair → create signed transfer BOC |
| `ton/contract_code.py` | Compiled Tact escrow BOC hex constant |
| `creative_service.py` | Creative versioning, approval flow |
| `posting_service.py` | Auto-posting via Bot API, retention check |
| `stats_service.py` | Channel stats fetching & snapshot storage |
| `team_permissions.py` | RBAC: get_user_role_for_channel, has_permission, check_telegram_admin_cached (Redis-cached) |
| `notification_service.py` | Send bot messages on events (including team member notifications) |

### `workers/` — Celery Tasks
| Task | Responsibility |
|------|---------------|
| `refresh_stats.py` | Periodic channel stats refresh |
| `deal_timeouts.py` | Expire inactive deals |
| `monitor_escrow.py` | monitor_escrow_deposits (30s) — poll init escrows, verify deposit; monitor_escrow_completions (60s) — poll funded escrows, detect release/refund |
| `verify_posting.py` | Check post retention after deadline |
| `schedule_posting.py` | Auto-post creative at scheduled time |

---

## Bot Modules (`/bot/`)

### `handlers/`
| Handler | Triggers |
|---------|----------|
| `start.py` | `/start` command — welcome + inline keyboard (Open Mini App, My Deals, Help) |
| `deals.py` | Deal negotiation messages, status change confirmations |
| `notifications.py` | Outgoing notifications (called by backend notification_service) |
| `creative.py` | Creative submission/review via bot (fallback if not using mini app) |

### `middleware/`
| Middleware | Responsibility |
|-----------|---------------|
| `auth.py` | Extract user from update, ensure registered |
| `i18n.py` | Set locale from user profile for message templates |

### `templates/`
| File | Content |
|------|---------|
| `messages_en.py` | English message templates |
| `messages_ru.py` | Russian message templates |

---

## Frontend Modules (`/frontend/src/`)

### `screens/` — Pages by Role
| Screen | Role | Description |
|--------|------|-------------|
| `Auth.tsx` | all | Splash + Telegram auth |
| `OwnerChannels.tsx` | owner | Channel list |
| `OwnerAddChannel.tsx` | owner | Add channel wizard (3 steps) |
| `OwnerChannelDetail.tsx` | owner | Channel detail + stats |
| `OwnerListings.tsx` | owner | Listings management |
| `OwnerListingEdit.tsx` | owner | Create/edit listing |
| `AdvSearch.tsx` | advertiser | Marketplace search with filters |
| `AdvListingDetail.tsx` | advertiser | Listing detail + "Create Deal" |
| `AdvCampaigns.tsx` | advertiser | Campaign list |
| `AdvCampaignEdit.tsx` | advertiser | Create/edit campaign |
| `Deals.tsx` | both | Deal list (filtered by role) |
| `DealDetail.tsx` | both | Deal card: status, escrow, creative, actions |
| `Profile.tsx` | both | User profile, locale, wallet |

### `ui/` — Reusable Components
| Component | Description |
|-----------|-------------|
| `RoleSwitcher` | Toggle between Owner / Advertiser |
| `NavBar` | Bottom navigation (dynamic by role) |
| `DealCard` | Compact deal summary |
| `StatsBadge` | Channel stats display |
| `PriceTag` | TON amount display |
| `StatusChip` | Colored status indicator |
| `FilterPanel` | Expandable search filters |
| `WalletButton` | TON Connect wallet connect/disconnect |

### `api/` — HTTP Client
| Module | Description |
|--------|-------------|
| `client.ts` | Axios/fetch wrapper with JWT auth header |
| `types.ts` | TypeScript interfaces matching backend schemas |
| `endpoints.ts` | Typed API call functions |

### `i18n/`
| Path | Description |
|------|-------------|
| `locales/en/common.json` | English common strings |
| `locales/en/deals.json` | English deal-related strings |
| `locales/ru/common.json` | Russian common strings |
| `locales/ru/deals.json` | Russian deal-related strings |
| `index.ts` | i18next initialization |

---

## Deal State Machine

### Status Table

| Status | Description |
|--------|-------------|
| `DRAFT` | Deal created, not yet sent |
| `NEGOTIATION` | Both parties discussing terms |
| `OWNER_ACCEPTED` | Owner agreed to terms |
| `AWAITING_ESCROW_PAYMENT` | Waiting for advertiser deposit |
| `ESCROW_FUNDED` | Deposit confirmed on-chain |
| `CREATIVE_PENDING_OWNER` | Waiting for owner to submit creative |
| `CREATIVE_SUBMITTED` | Owner submitted, awaiting advertiser review |
| `CREATIVE_CHANGES_REQUESTED` | Advertiser requested edits |
| `CREATIVE_APPROVED` | Advertiser approved creative |
| `SCHEDULED` | Publication time agreed & scheduled |
| `POSTED` | Message published in channel |
| `RETENTION_CHECK` | Verification period in progress |
| `RELEASED` | Funds released to owner (terminal) |
| `REFUNDED` | Funds returned to advertiser (terminal) |
| `CANCELLED` | Deal cancelled before escrow (terminal) |
| `EXPIRED` | Deal timed out (terminal) |

### Transition Table

```
DRAFT               → NEGOTIATION, CANCELLED
NEGOTIATION         → OWNER_ACCEPTED, CANCELLED, EXPIRED
OWNER_ACCEPTED      → AWAITING_ESCROW_PAYMENT, CANCELLED, EXPIRED
AWAITING_ESCROW_PAYMENT → ESCROW_FUNDED, CANCELLED, EXPIRED
ESCROW_FUNDED       → CREATIVE_PENDING_OWNER, REFUNDED
CREATIVE_PENDING_OWNER  → CREATIVE_SUBMITTED, REFUNDED, EXPIRED
CREATIVE_SUBMITTED  → CREATIVE_APPROVED, CREATIVE_CHANGES_REQUESTED, REFUNDED
CREATIVE_CHANGES_REQUESTED → CREATIVE_SUBMITTED, REFUNDED, EXPIRED
CREATIVE_APPROVED   → SCHEDULED, REFUNDED
SCHEDULED           → POSTED, REFUNDED, EXPIRED
POSTED              → RETENTION_CHECK
RETENTION_CHECK     → RELEASED, REFUNDED
```

Terminal states: `RELEASED`, `REFUNDED`, `CANCELLED`, `EXPIRED` — no outgoing transitions.

### Guards (preconditions)

| Transition | Guard |
|-----------|-------|
| → ESCROW_FUNDED | on-chain deposit verified |
| → CREATIVE_APPROVED | advertiser explicitly approved |
| → POSTED | bot successfully published message |
| → RELEASED | retention check passed |
| → REFUNDED | escrow refund tx confirmed |

---

## Escrow Contract Interface (Tact)

```
contract Escrow {
    // Storage
    dealId: Int as uint64
    advertiser: Address
    owner: Address
    platform: Address
    amount: Int as coins
    deadline: Int as uint32
    state: Int as uint8  // 0=init, 1=funded, 2=released, 3=refunded

    // Receive
    receive("deposit")          // advertiser sends TON
    receive("release")          // platform confirms delivery → send to owner
    receive("refund")           // platform triggers refund → send to advertiser
    receive("auto_refund")      // anyone can call after deadline if still funded
}
```

---

## External Dependencies

| Dependency | Usage | Module |
|-----------|-------|--------|
| Telegram Bot API | getChat, getChatMemberCount, getChatAdministrators, sendMessage, copyMessage | stats_service, posting_service, bot handlers |
| TON API (Toncenter/tonapi) | getAccountState, getTransactions — escrow monitoring | monitor_escrow worker, escrow_service |
| TON Connect | Wallet connection, transaction signing (frontend) | WalletButton, DealDetail screen |
| Redis | Celery broker, rate limiting, caching | workers, security middleware |
| PostgreSQL | Primary data store | all backend services |
