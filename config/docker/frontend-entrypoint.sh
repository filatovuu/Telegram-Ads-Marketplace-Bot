#!/bin/sh
# Generate TON Connect manifest at container startup from runtime DOMAIN.

DOMAIN="${DOMAIN:-localhost}"

if [ "$DOMAIN" = "localhost" ] || [ "$DOMAIN" = "127.0.0.1" ]; then
  PROTOCOL="http"
else
  PROTOCOL="https"
fi

APP_URL="${PROTOCOL}://${DOMAIN}"

mkdir -p /usr/share/nginx/html/tc
cat > /usr/share/nginx/html/tc/manifest.json <<EOF
{
  "url": "$APP_URL",
  "name": "Ads Marketplace",
  "iconUrl": "$APP_URL/tc/icon.png"
}
EOF

echo "tonconnect-manifest: generated for $APP_URL at /tc/manifest.json"
