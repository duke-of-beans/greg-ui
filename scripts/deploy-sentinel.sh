#!/usr/bin/env bash
# Greg UI deploy script for Sentinel
# Usage: ./scripts/deploy-sentinel.sh
#
# Pulls latest pre-built image from GHCR (built by GitHub Actions),
# restarts container. Data volume persists — no conversation loss.
# Run from the greg-ui repo root on Sentinel.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "=== Greg UI Deploy ==="
echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Pull latest compose config
echo ""
echo "--- Pulling repo ---"
git fetch origin main
git reset --hard origin/main

# Pull pre-built image from GHCR
echo ""
echo "--- Pulling image from GHCR ---"
docker pull ghcr.io/duke-of-beans/greg-ui:latest

# Restart
echo ""
echo "--- Restarting container ---"
docker compose -f docker-compose.greg.yaml down 2>/dev/null || true
docker compose -f docker-compose.greg.yaml up -d

echo ""
echo "--- Waiting for health ---"
for i in $(seq 1 12); do
    if curl -sf http://localhost:3000/health > /dev/null 2>&1; then
        echo "Greg UI is healthy."
        echo ""
        echo "=== Deploy complete ==="
        echo "Access: https://sentinel.tail3f6996.ts.net"
        exit 0
    fi
    echo "Waiting for startup... ($i/12)"
    sleep 5
done

echo "WARNING: Health check failed after 60s. Check logs:"
echo "  docker compose -f docker-compose.greg.yaml logs -f greg-ui"
exit 1
