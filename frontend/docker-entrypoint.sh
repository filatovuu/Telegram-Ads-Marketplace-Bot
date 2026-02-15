#!/bin/sh
set -e

# Always install dependencies inside the container to ensure
# native binaries match the container platform (linux-musl)
if [ ! -f "node_modules/.package-lock.json" ] || [ "$(uname -m)" != "$(cat node_modules/.platform 2>/dev/null)" ]; then
  echo "Installing dependencies for $(uname -m)..."
  npm install
  uname -m > node_modules/.platform
fi

exec "$@"
