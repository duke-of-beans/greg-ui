# CLAUDE_INSTRUCTIONS.md — Gregore (Open WebUI fork)

## Pre-Flight Checklist
- **Production URL:** https://sentinel.tail3f6996.ts.net (Tailscale tailnet-only; Funnel at :8443 for CORTEX brain proxy)
- **Package Manager:** npm (lockfile: package-lock.json)
- **Deploy Flow:** git push to main → GHCR image built by GitHub Actions → pull and restart on Sentinel via `docker compose -f docker-compose.greg.yaml pull && docker compose -f docker-compose.greg.yaml up -d`
- **Repo URL:** https://github.com/duke-of-beans/greg-ui
- **GHCR Image:** ghcr.io/duke-of-beans/greg-ui:latest
- **Host:** Sentinel (Ubuntu, always-on, Tailscale IP 100.82.64.110, LAN 192.168.2.39)

## What This Is

Gregore is David Kirsch's fork of Open WebUI (v0.11.0 base), serving as Greg's primary
workspace interface. It runs on Sentinel as a Docker container and is Greg's face for
daily interaction with David. Three routes:

- **/chat** — workspace. Channels (#sprint-activity, #daily-brief, #portfolio-signals), tools, sprint management
- **/home** — GregLite living room. Ambient, personal, Throwbak, lifelog, Greg's thoughts, portal doors
- **/face** — kiosk presence. SVG face with affect state, eye tracking. For Wall Greg and M3

## Architecture

All LLM calls route through CORTEX (Railway) via a Pipe Function (id: cortex_pipe).
Zero direct provider connections. Four depth models: Quick, Auto, Deep, Deliberate.

CORTEX pipe function handles: brain.db recall injection, ROSETTA conversation capture,
depth routing, capacity governor checks, SCRVNR voice enforcement.

cptr (Open WebUI Computer) agents on Sentinel, M3, and Pixel 10 provide local
filesystem/terminal access through the chat interface.

Chatterbox TTS on Sentinel (port 8004) provides Greg's voice (Josh Groban clone).

## Tech Stack

- **Frontend:** SvelteKit + Tailwind CSS (Vite build)
- **Backend:** Python 3.11 (FastAPI)
- **Container:** Docker with docker-compose.greg.yaml
- **CI:** GitHub Actions → GHCR
- **Infra:** Sentinel (Docker host), Tailscale (networking)

## Key Files (Greg-specific, not upstream)

- `src/routes/(app)/home/+page.svelte` — GregLite living room
- `src/routes/(app)/face/+page.svelte` — kiosk face
- `docker-compose.greg.yaml` — Sentinel deployment config
- `.github/workflows/build.yml` — GHCR build pipeline
- `sprints/` — 10 sprint specs for HEARTH features

## Build Notes

The Vite build requires >4GB heap. NODE_OPTIONS is set to 8192MB in the Dockerfile.
GHA ubuntu-latest runners have 7GB RAM; Docker Buildx uses swap when needed. If builds
OOM, the heap limit in the Dockerfile (line ~31) is the first thing to check.

## Environment Variables (Sentinel .env)

- WEBUI_SECRET_KEY — session encryption
- CORTEX_URL — CORTEX MCP endpoint (Railway)
- CORTEX_KEY — CORTEX auth bearer token
- GREG_HOME_API_URL — Home/Sprint Service on Railway
- GREG_HOME_API_KEY — Home API auth

## Development

For Svelte UI iteration, clone to local (D:\Dev\greg-ui) and work there.
For backend/pipe function changes, edit via Open WebUI admin panel on Sentinel.
For Docker/infra changes, commit to GitHub and rebuild on Sentinel.

## Naming

- **Gregore** = this project. Open WebUI on Sentinel. The workspace.
- **GregLite** = browser homepage surface. Lives at /home route AND as the Home Railway service.
- **Sprint Service** = headless executor on Railway (duke-of-beans/home, extracting to standalone).
- **HEARTH** = retired design codename. Not a product name.
