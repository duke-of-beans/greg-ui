**Status:** active
**Phase:** Phase 0 complete, Phase 1a-1c in progress
**Last Sprint:** 2026-08-28 — cortex_pipe v3.1 (two critical chat quality bugs fixed)
**Last Updated:** 2026-08-28

## Current State

Gregore (Open WebUI fork) deployed on Sentinel as Docker container.
Phase 0 complete: CORTEX pipe function, depth models, channels, brain.db recall,
ROSETTA capture, daily brief automation, cptr agents on 3 machines.

CI pipeline: build.yml (Docker + GHCR push) active. docker.yaml and backend.yaml
(upstream workflows) disabled — were firing on push despite workflow_dispatch-only
config, generating false failure notifications.

### Session 2026-08-28 — Chat Quality Fixes

**cortex_pipe.py v3.1 committed (b7b0f30):**

Two bugs found and fixed that explain why Greg chat quality was unacceptable:

1. **Crash bug:** `_claude_draft()` referenced `depth` from caller's scope — NameError
   on execution. `--max-turns 1` for /quick NEVER fired. Fixed: `depth_label` passed
   as explicit parameter.

2. **Quality bug:** Claude Code subprocess only received last user message as flat string.
   No conversation history passed. Greg could not maintain context across turns — every
   message was a cold start. Fixed: builds full David/Greg transcript from message history.

Also: subprocess timeout raised to 120s (was 90s) for deeper depths.

**Verified still correct from v3.0:**
- Truncation fix committed: Stage 3 only calls affect() for metadata, doesn't rewrite draft
- Valve env vars persist via docker-compose.greg.yaml env section
- Node.js 22 + @anthropic-ai/claude-code installed in Dockerfile

**CI workflows cleaned up:**
- docker.yaml: disabled (upstream, was spamming failure notifications)
- backend.yaml: disabled (upstream, same issue)
- build.yml: active, triggered by commit, building GHCR image now

### Blocker: Sprint Channel Posting (SS-02)

Railway (Home) cannot reach Sentinel (Gregore) — Tailscale URL not resolvable from
Railway's network. The 3 env vars (GREGORE_BOT_TOKEN, GREGORE_URL, SPRINT_CHANNEL_ID)
cannot be set until a network path exists. Options:
- Tailscale Funnel on Sentinel (exposes port 3000 publicly)
- Cloudflare tunnel
- Supabase intermediary (SS-04 — write events to Supabase, Gregore polls/subscribes)

Webhook secrets exist in Supabase (owui-webhook-sprint-service) but same connectivity issue.

### Pending David Action (Sentinel)

- `docker pull ghcr.io/duke-of-beans/greg-ui:latest`
- `docker compose -f docker-compose.greg.yaml up -d`
- Test Greg /auto and /deep to verify conversation continuity works

### Phase 1 Progress (2026-08-26)

Sprint channel infrastructure (SS-02) built in Home (duke-of-beans/home):
- Phase persistence, channel posting helper, wiring — all deployed
- sprint_tool.py fixed (fa55fb0): schema, columns, key type corrected
- Blocked on Railway→Sentinel network path for activation

### Branding (2026-08-23)
- Favicon: canonical Schauberger vortex g from design-system/assets/logo/
- Two custom themes: Gregore Dark (Walnut) + Gregore Light (Linen)
- WEBUI_NAME=Gregore, title=Gregore, Greg purple accents

## Recent Commits
- b7b0f30 fix(pipe): v3.1 — depth scope crash + conversation history for Claude Code
- fa55fb0 fix(sprint_tool): correct schema access, column names, key type
- 8142ffc4 theme: Gregore Dark + Gregore Light in theme selector
- 74acb993 brand: canonical design system assets
