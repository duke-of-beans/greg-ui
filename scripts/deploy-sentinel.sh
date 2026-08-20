#!/usr/bin/env bash
# Greg UI deploy script for Sentinel
# Usage: ./scripts/deploy-sentinel.sh
#
# Pulls latest from github, rebuilds Docker image, restarts container.
# Data volume persists across rebuilds — no conversation loss.
# Run from the greg-ui repo root on Sentinel.

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
REPO_DIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_DIR"

echo "=== Greg UI Deploy ==="
echo "Repo: $(pwd)"
echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Pull latest
echo ""
echo "--- Pulling latest ---"
git fetch origin main
git reset --hard origin/main

# Build and restart
echo ""
echo "--- Building Docker image ---"
docker compose -f docker-compose.greg.yaml build --no-cache

echo ""
echo "--- Restarting container ---"
docker compose -f docker-compose.greg.yaml down
docker compose -f docker-compose.greg.yaml up -d

echo ""
echo "--- Waiting for health ---"
sleep 5
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
