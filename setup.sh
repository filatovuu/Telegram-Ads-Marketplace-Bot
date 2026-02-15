#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

ENV_DIR="./config/env"
TEMPLATE_DIR="./config/env_template"

echo -e "${BOLD}Telegram Ads Marketplace Bot — Setup${NC}"
echo ""

# Create env dir
mkdir -p "$ENV_DIR"

# Copy templates if files don't exist yet
for f in "$TEMPLATE_DIR"/.*env; do
    name=$(basename "$f")
    if [ ! -f "$ENV_DIR/$name" ]; then
        cp "$f" "$ENV_DIR/$name"
    fi
done

# ── Helpers ──────────────────────────────────────────────────────

# Prompt for a value; accept default on Enter
# Usage: ask VAR "Description" "default_value" file
ask() {
    local var="$1" desc="$2" default="$3" file="$4"
    local current value

    # Read current value from file (strip quotes)
    current=$(grep "^${var}=" "$file" 2>/dev/null | head -1 | cut -d'=' -f2- | sed 's/^"//;s/"$//')

    # Use current if it's not the template placeholder
    if [ -n "$current" ] && [ "$current" != "$default" ]; then
        default="$current"
    fi

    if [ -n "$default" ]; then
        echo -en "  ${CYAN}${desc}${NC} ${DIM}[${default}]${NC}: "
    else
        echo -en "  ${CYAN}${desc}${NC}: "
    fi

    read -r value
    value="${value:-$default}"

    # Update the file: replace existing line or append
    if grep -q "^${var}=" "$file" 2>/dev/null; then
        # Use | as sed delimiter to avoid conflicts with URLs
        sed -i "s|^${var}=.*|${var}=${value}|" "$file"
    else
        echo "${var}=${value}" >> "$file"
    fi
}

# Generate a random hex string
generate_secret() {
    openssl rand -hex 32 2>/dev/null || LC_ALL=C tr -dc 'a-f0-9' < /dev/urandom | head -c 64
}

# Ask yes/no, default yes
confirm() {
    local prompt="$1"
    echo -en "  ${prompt} ${DIM}[Y/n]${NC}: "
    read -r yn
    case "$yn" in
        [Nn]*) return 1 ;;
        *) return 0 ;;
    esac
}

CORE="$ENV_DIR/.core.env"
BACKEND="$ENV_DIR/.backend.env"
BOT="$ENV_DIR/.bot.env"

# ── 1. Core ──────────────────────────────────────────────────────

echo -e "${BOLD}${GREEN}1/3${NC} ${BOLD}Core settings${NC} ${DIM}(config/env/.core.env)${NC}"
echo ""

ask "DOMAIN"            "Domain"                               "localhost"   "$CORE"
echo ""

echo -e "  ${YELLOW}PostgreSQL${NC}"
ask "POSTGRES_USER"     "  User"                               "postgres"    "$CORE"
ask "POSTGRES_PASSWORD" "  Password"                           "postgres"    "$CORE"
ask "POSTGRES_DB"       "  Database"                           "marketplace" "$CORE"
echo ""

echo -e "  ${YELLOW}Redis${NC}"
ask "REDIS_PASSWORD"    "  Password"                           "redis"       "$CORE"
echo ""

echo -e "  ${YELLOW}TON Network${NC}"
ask "APP_TON_NETWORK"      "  Network (testnet/mainnet)"       "testnet"                        "$CORE"
ask "APP_TON_API_KEY"      "  Toncenter API key"               ""                               "$CORE"
ask "APP_TON_API_BASE_URL" "  Toncenter API URL"               "https://toncenter.com/api/v3"   "$CORE"
echo ""

# ── 2. Bot ───────────────────────────────────────────────────────

echo -e "${BOLD}${GREEN}2/3${NC} ${BOLD}Bot settings${NC} ${DIM}(config/env/.bot.env)${NC}"
echo ""

ask "BOT_TOKEN"         "Bot token (from @BotFather)"          ""            "$BOT"
ask "BOT_USERNAME"      "Bot username (without @)"             ""            "$BOT"

# Show computed URLs (set from DOMAIN in docker-compose.yml)
DOMAIN=$(grep "^DOMAIN=" "$CORE" | cut -d'=' -f2-)
echo -e "  ${DIM}Webhook URL:  https://${DOMAIN}/bot/webhook  (auto from DOMAIN)${NC}"
echo -e "  ${DIM}Mini App URL: https://${DOMAIN}              (auto from DOMAIN)${NC}"

# Auto-generate webhook secret
CURRENT_WH_SECRET=$(grep "^BOT_WEBHOOK_SECRET=" "$BOT" 2>/dev/null | cut -d'=' -f2-)
if [ -z "$CURRENT_WH_SECRET" ] || [ "$CURRENT_WH_SECRET" = "random-webhook-secret" ]; then
    if confirm "Generate random webhook secret?"; then
        WH_SECRET=$(generate_secret)
        sed -i "s|^BOT_WEBHOOK_SECRET=.*|BOT_WEBHOOK_SECRET=${WH_SECRET}|" "$BOT"
        echo -e "  ${DIM}Generated: ${WH_SECRET:0:16}...${NC}"
    else
        ask "BOT_WEBHOOK_SECRET" "Webhook secret" "" "$BOT"
    fi
else
    echo -e "  ${DIM}Webhook secret already set, keeping.${NC}"
fi
echo ""

# ── 3. Backend ───────────────────────────────────────────────────

echo -e "${BOLD}${GREEN}3/3${NC} ${BOLD}Backend settings${NC} ${DIM}(config/env/.backend.env)${NC}"
echo ""

# Auto-generate JWT secret
CURRENT_JWT=$(grep "^APP_JWT_SECRET=" "$BACKEND" 2>/dev/null | cut -d'=' -f2-)
if [ -z "$CURRENT_JWT" ] || [ "$CURRENT_JWT" = "change-me-in-production" ]; then
    if confirm "Generate random JWT secret?"; then
        JWT_SECRET=$(generate_secret)
        sed -i "s|^APP_JWT_SECRET=.*|APP_JWT_SECRET=${JWT_SECRET}|" "$BACKEND"
        echo -e "  ${DIM}Generated: ${JWT_SECRET:0:16}...${NC}"
    else
        ask "APP_JWT_SECRET" "JWT secret" "" "$BACKEND"
    fi
else
    echo -e "  ${DIM}JWT secret already set, keeping.${NC}"
fi

ask "APP_DEBUG"                    "Debug mode (true/false)"            "true"  "$BACKEND"
ask "APP_TON_PLATFORM_MNEMONIC"   "Platform wallet mnemonic (24 words)" ""     "$BACKEND"
ask "APP_TON_ESCROW_DEADLINE_HOURS" "Escrow deadline (hours)"           "72"   "$BACKEND"
ask "APP_PLATFORM_FEE_PERCENT"    "Platform fee (%)"                    "10"   "$BACKEND"
echo ""

echo -e "  ${YELLOW}MTProto (optional — press Enter to skip)${NC}"
ask "MTPROTO_API_ID"           "  API ID"             "" "$BACKEND"
ask "MTPROTO_API_HASH"         "  API hash"           "" "$BACKEND"
ask "MTPROTO_SESSION_STRING"   "  Session string"     "" "$BACKEND"
echo ""

# ── Done ─────────────────────────────────────────────────────────

echo -e "${GREEN}${BOLD}Setup complete!${NC}"
echo ""
echo "  Config files:"
echo "    $CORE"
echo "    $BOT"
echo "    $BACKEND"
echo ""
echo "  Next steps:"
echo "    make build    # Build Docker images"
echo "    make run      # Start all services"
echo ""
