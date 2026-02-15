.PHONY: setup build dev dev-d build-prod prod prod-d prod-down prod-restart prod-logs stop down restart logs test-backend test-frontend test lint format migrate generate-migration health

ENV_FILES = --env-file ./config/env/.core.env --env-file ./config/env/.backend.env --env-file ./config/env/.bot.env
DC_DEV = docker compose $(ENV_FILES) -f docker-compose.yml -f docker-compose.dev.yml
DC_PROD = docker compose $(ENV_FILES) -f docker-compose.yml -f docker-compose.prod.yml

# ── Setup ────────────────────────────────────────────────────────
setup:
	@./setup.sh

# ── Development ──────────────────────────────────────────────────
build:
	$(DC_DEV) build

dev:
	$(DC_DEV) up

dev-d:
	$(DC_DEV) up -d

dev-down:
	$(DC_DEV) down

dev-logs:
	$(DC_DEV) logs -f

# ── Production ───────────────────────────────────────────────────
build-prod:
	$(DC_PROD) build

prod:
	$(DC_PROD) up

prod-d:
	$(DC_PROD) up -d

prod-down:
	$(DC_PROD) down

prod-restart:
	$(DC_PROD) restart

prod-logs:
	$(DC_PROD) logs -f

# ── Shortcuts (dev by default) ───────────────────────────────────
stop:
	$(DC_DEV) stop

down:
	$(DC_DEV) down

restart:
	$(DC_DEV) restart

logs:
	$(DC_DEV) logs -f

# ── Testing ──────────────────────────────────────────────────────
test-backend:
	$(DC_DEV) run --rm backend pytest -v; s=$$?; $(DC_DEV) down; exit $$s

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

# ── Code quality ─────────────────────────────────────────────────
lint:
	cd backend && ruff check .

format:
	cd backend && ruff format .

# ── Database ─────────────────────────────────────────────────────
migrate:
	$(DC_DEV) exec backend alembic upgrade head

generate-migration:
	$(DC_DEV) run --rm backend alembic revision --autogenerate -m "$(msg)"

# ── Health check ─────────────────────────────────────────────────
health:
	@$(DC_PROD) exec -T postgres pg_isready -U postgres 2>/dev/null && echo " Postgres OK" || echo " Postgres FAIL"
	@$(DC_PROD) exec -T backend python -c "import socket; s=socket.create_connection(('redis',6379),2); s.close()" 2>/dev/null && echo " Redis OK" || echo " Redis FAIL"
	@$(DC_PROD) exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" 2>/dev/null && echo " Backend OK" || echo " Backend FAIL"
	@$(DC_PROD) exec -T bot python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/bot/health')" 2>/dev/null && echo " Bot OK" || echo " Bot FAIL"
	@$(DC_PROD) exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://frontend:80/')" 2>/dev/null && echo " Frontend OK" || echo " Frontend FAIL"
	@$(DC_PROD) exec -T backend python -c "import http.client; c=http.client.HTTPConnection('nginx',80,timeout=2); c.request('HEAD','/'); exit(0 if c.getresponse().status else 1)" 2>/dev/null && echo " Nginx OK" || echo " Nginx FAIL"
