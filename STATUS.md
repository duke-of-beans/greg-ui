**Status:** active
**Phase:** Phase 0 complete, CI pipeline fix in progress
**Last Sprint:** 2026-08-23 — CI fix, CLAUDE_INSTRUCTIONS.md
**Last Updated:** 2026-08-23

## Current State

Gregore (Open WebUI fork) deployed on Sentinel as Docker container.
Phase 0 complete: CORTEX pipe function, depth models, channels, brain.db recall,
ROSETTA capture, daily brief automation, cptr agents on 3 machines.

Custom routes /home (GregLite living room) and /face (kiosk presence) committed.
Sprints 01, 02, 06, 08+10, 09 executed. Sprints 03-05, 07 pending.

CI pipeline was broken (Vite build OOM at 4GB heap limit). Fixed to 8GB.
Upstream Docker workflow and Python CI need to be disabled (requires workflow PAT scope).

Container on Sentinel returning 503 via Tailscale Funnel — needs health check.

## Blockers

- CI: upstream docker.yaml and backend.yaml workflows still trigger (need PAT with workflow scope to disable)
- Container: Sentinel Docker container may be stopped — 503 on Funnel endpoint
- Tool passthrough: CORTEX OpenAI-compat endpoint can't handle tool calls through cascade models
