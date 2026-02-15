# Security

This document describes the security measures implemented in the Telegram Ads Marketplace Bot.

## Authentication

- **Telegram initData HMAC verification**: All user authentication goes through Telegram's cryptographic initData mechanism. The backend verifies the HMAC-SHA256 signature using the bot token as the secret key.
- **Replay protection**: initData is rejected if `auth_date` is older than 5 minutes (configurable via `APP_INIT_DATA_MAX_AGE_SECONDS`).
- **JWT tokens**: After verification, the backend issues short-lived JWT access tokens (default: 24h). Tokens are signed with `APP_JWT_SECRET`.

## Role-Based Access Control (RBAC)

- Users have an `active_role` field (`owner` or `advertiser`).
- API routers enforce role boundaries: owner endpoints reject advertisers and vice versa.
- Deal access is checked per-participant: only the advertiser and channel owner of a deal can view or modify it.
- Channel operations verify ownership via `Channel.owner_id`.

## Rate Limiting

- Redis-backed rate limiting via `slowapi` with fixed-window strategy.
- Default: 60 requests/minute per IP.
- Auth endpoints: 10 requests/minute per IP.
- Escrow endpoints: 5 requests/minute per IP.
- Configurable via `APP_RATE_LIMIT_DEFAULT`, `APP_RATE_LIMIT_AUTH`, `APP_RATE_LIMIT_ESCROW`.

## Data Protection

- All database queries use parameterized SQLAlchemy ORM — no raw SQL, preventing SQL injection.
- Pydantic v2 validates all API inputs with strict type checking.
- Passwords and secrets are never stored in code — all sensitive values come from environment variables with the `APP_` prefix.
- CORS origins are configurable via `APP_CORS_ORIGINS` (defaults to `["*"]` in development).

## Escrow Security

- Each deal gets a dedicated on-chain TON smart contract (Tact language).
- Only the platform wallet (controlled by `APP_TON_PLATFORM_MNEMONIC`) can call `release` and `refund`.
- `auto_refund` is permissionless but requires the deadline to have passed and the contract to be in `FUNDED` state.
- The backend verifies on-chain state before updating the database — never trusts client-submitted state.
- Escrow creation is guarded by idempotency keys to prevent double-deployment.

## Audit Logging

- Significant actions are recorded in the `audit_logs` table: deal cancellations, releases, refunds, escrow creation, auto-posting, and retention verification.
- Each audit entry includes: `user_id`, `action`, `entity_type`, `entity_id`, `details` (JSON), `ip_address`, and `timestamp`.

## Infrastructure Isolation

- All services run in Docker containers on an isolated network.
- PostgreSQL and Redis are not exposed to the host in production.
- Nginx handles TLS termination with Let's Encrypt certificates.
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Strict-Transport-Security`.
- Gzip compression enabled at the reverse proxy level.

## Request Tracing

- Every request gets a unique `X-Request-ID` header for tracing.
- Structured JSON logging includes request method, path, status code, and duration for all API calls.

## Worker Reliability

- Celery tasks use `task_acks_late=True` and `task_reject_on_worker_lost=True` to prevent message loss.
- All worker tasks have retry policies with exponential backoff (max 3 retries).
- External API calls (Telegram Bot API, TON RPC) use tenacity retry with exponential backoff.

## Vulnerability Reporting

If you discover a security vulnerability, please report it privately by opening a GitHub issue with the `security` label or contacting the repository maintainers directly. Do not disclose security issues publicly.
