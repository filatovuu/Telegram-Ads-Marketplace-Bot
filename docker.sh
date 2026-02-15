#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper — always uses dev overlay.
# For production use: make prod / make prod-d
docker compose \
    --env-file ./config/env/.core.env \
    --env-file ./config/env/.backend.env \
    --env-file ./config/env/.bot.env \
    -f docker-compose.yml \
    -f docker-compose.dev.yml \
    "$@"
