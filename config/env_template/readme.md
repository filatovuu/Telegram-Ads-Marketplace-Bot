# Environment Variables

Run `make setup` to copy these templates to `config/env/` and fill in your values.

## File Structure

| File | Loaded by | Description |
|------|-----------|-------------|
| `.core.env` | All services | Shared infrastructure: Postgres, Redis, domain, TON network |
| `.backend.env` | backend, worker, beat | JWT secret, TON mnemonic, MTProto credentials |
| `.bot.env` | bot, backend (for `BOT_TOKEN`) | Bot token, webhook URL, Mini App URL |

## Variables

### `.core.env` — Shared Infrastructure

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `POSTGRES_USER` | `postgres` | Yes | PostgreSQL username |
| `POSTGRES_PASSWORD` | `postgres` | Yes | PostgreSQL password (**change in production**) |
| `POSTGRES_DB` | `marketplace` | Yes | PostgreSQL database name |
| `REDIS_PASSWORD` | `redis` | Yes | Redis password (**change in production**) |
| `DOMAIN` | `localhost` | Yes (prod) | Domain for nginx SSL and Telegram webhook |
| `APP_TON_NETWORK` | `testnet` | No | `testnet` or `mainnet` |
| `APP_TON_API_KEY` | — | Yes | Toncenter API key |
| `APP_TON_API_BASE_URL` | `https://toncenter.com/api/v3` | No | Toncenter API base URL |

### `.backend.env` — Backend / Worker / Beat

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `APP_JWT_SECRET` | `change-me-in-production` | Yes (prod) | JWT signing secret |
| `APP_DEBUG` | `true` | No | Enable debug mode |
| `APP_TON_PLATFORM_MNEMONIC` | — | Yes | 24-word mnemonic for platform wallet |
| `APP_DEAL_EXPIRE_HOURS` | `72` | No | Inactivity timeout for deals in negotiation/escrow stages (hours) |
| `APP_DEAL_REFUND_HOURS` | `48` | No | Post-escrow inactivity timeout before auto-refund (hours) |
| `APP_PLATFORM_FEE_PERCENT` | `10` | No | Platform fee percentage (0-100) |
| `MTPROTO_API_ID` | — | No | Telegram MTProto API ID (for enhanced analytics) |
| `MTPROTO_API_HASH` | — | No | Telegram MTProto API hash |
| `MTPROTO_SESSION_STRING` | — | No | MTProto session string (see [Generating MTProto session](#generating-mtproto-session)) |

### `.bot.env` — Bot Service

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `BOT_TOKEN` | — | Yes | Telegram Bot API token |
| `BOT_USERNAME` | — | Yes | Bot username (without @) |
| `BOT_WEBHOOK_SECRET` | — | Yes | Random string for webhook verification |

## Computed Variables (set in docker-compose.yml)

These are constructed from env file values and set in the compose `environment:` block:

| Variable | Value | Used by |
|----------|-------|---------|
| `APP_DATABASE_URL` | `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}` | backend, worker, beat |
| `APP_REDIS_URL` | `redis://:${REDIS_PASSWORD}@redis:6379/0` | backend, worker, beat |
| `BOT_BACKEND_URL` | `http://backend:8000` | bot |
| `BOT_WEBHOOK_URL` | `https://${DOMAIN}/bot/webhook` | bot |
| `BOT_MINI_APP_URL` | `https://${DOMAIN}` | bot |

## Generating MTProto Session

MTProto is optional but enables enhanced channel analytics (post views, reactions, forwards, retention verification). To generate a session string:

1. Get `api_id` and `api_hash` at https://my.telegram.org
2. Run the generator script:

```bash
cd backend
pip install pyrogram tgcrypto
python -m scripts.generate_session
```

3. Enter your `api_id` and `api_hash` when prompted
4. Log in with your Telegram account (phone number + code)
5. Copy the output session string into `.backend.env`:

```
MTPROTO_API_ID=12345678
MTPROTO_API_HASH=abcdef1234567890abcdef1234567890
MTPROTO_SESSION_STRING=<paste here>
```

The session string is tied to your Telegram account. Generate it once — it does not expire.

## Security Notes

- **Never commit** `config/env/` to version control (it's in `.gitignore`).
- **Change all default passwords** before deploying to production.
- `APP_JWT_SECRET` must be a strong random string in production.
- `APP_TON_PLATFORM_MNEMONIC` controls the platform wallet — keep it secret.
- `BOT_WEBHOOK_SECRET` should be a random string (use `openssl rand -hex 32`).
