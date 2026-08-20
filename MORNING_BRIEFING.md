# MORNING BRIEFING — greg-ui (HEARTH Chat)
**Sprint:** 06 — Thinking Display + Depth Controls + Personality
**Date:** 2026-08-20
**Session Duration:** ~30 min

## SHIPPED
- Depth override via message prefix (`/quick /auto /deep /deliberate`) added to `cortex_pipe.py` — lets David switch depth mid-chat without touching the model picker
- Personality metadata footer added to every Greg reply in `cortex_pipe.py` — muted line: `Greg · {affect} · {role} · N memories · {provider} · {ms}ms total`
- Fixed ROSETTA double-capture bug in `brain_context_filter.py` outlet — it was ingesting David's message a second time for every HEARTH pipe-model turn, on top of `cortex_pipe.py`'s own capture; outlet now skips `cortex_pipe.*` / `greg-*` models

## QUALITY GATES
| Gate | Result |
|------|--------|
| Python compile (`py_compile`) — cortex_pipe.py, brain_context_filter.py | PASS |
| Git pull before starting | PASS — already up to date with origin/main |
| Frontend build (Svelte/tsc) | N/A — no frontend files touched this session (see Decisions) |
| Git status pre-commit | Clean except intended changes |

## DECISIONS MADE BY AGENT
- **Skipped building a new Svelte "thinking display" component (Task 1).** Read `StatusHistory.svelte` + `StatusItem.svelte` — the fork already renders `event_emitter` status updates as a shimmering, timeline-dot, collapsible history natively, and `cortex_pipe.py` already emits the exact "Recalled N memories (Xms)" / "Drafted via {provider} (Xms)" / "{affect} · {role} (Xms)" text this task asked for (shipped in last night's sprint-01 commit, 94be8182). Building a second component would duplicate working, polished upstream UI for no gain. Alternative was: build a redundant component anyway to "complete the task on paper."
- **Skipped a custom depth-selector UI (Task 2).** `cortex_pipe.py.pipes()` already exposes Quick/Auto/Deep/Deliberate as four separate selectable models in Open WebUI's native model picker — that *is* a depth selector. Added the `/quick /deep /deliberate` message-prefix override from the spec's alternate suggestion as a low-risk backend-only complement instead of a second, possibly-conflicting frontend control.
- **Personality footer is a single muted line, not a true collapsible (Task 3).** Traced the fork's `<details>` handling: `ConsecutiveDetailsGroup.svelte` is hardcoded to `tool_calls` / `reasoning` / `code_interpreter` token attributes and ignores arbitrary `<summary>` text — a plain `<details><summary>Greg · ...</summary></details>` from the pipe would silently render as "Explored" with none of the intended content. Wiring a real new token type through the marked pipeline is genuine untested frontend surgery. Shipped the reliable single-line version; the real collapsible is a good follow-up sprint if David wants it.

## UNEXPECTED FINDINGS
- Sprint 06's Task 1 and most of Task 4 (ROSETTA capture) were already substantially implemented in commit 94be8182 ("sprint 01 + layout D merge", pushed last night) — `cortex_pipe.py`'s docstring even says "Updated 2026-08-20: AI Gateway architecture, enhanced thinking display." Worth checking whether sprint 06 was partially executed before this session, or whether sprint 01's scope quietly absorbed it.
- The ROSETTA double-capture bug (fixed above) would have been silently duplicating every HEARTH message in `rosetta_inbox` since that commit landed — not caught by any test, only found by tracing inlet/outlet logic against `cortex_pipe.py`'s own capture.
- No `CLAUDE_INSTRUCTIONS.md`, `BACKLOG.md`, or `STATUS.md` exist at this repo's root (it's an upstream OSS fork, not a portfolio-scaffolded project) — pre-flight items (production URL, deploy flow) weren't verifiable from repo docs. Deploy appears to be Docker-based (`docker-compose.greg.yaml`) rather than Vercel; recommend confirming the actual deploy target before the next sprint touches anything deploy-related.

## FRICTION LOG
| # | Category | Description | Resolution |
|---|----------|--------------|------------|
| 1 | TOOL | Environment notes warned Desktop Commander writes may silently land in a sandboxed copy instead of David's real D:\ drive (a documented past incident) | Fixed — verified empirically via an independent device-bridge listing before any real edit; confirmed writes are real in this session |
| 2 | ENV | `python` / `uv` not on PATH in the MCP-launched cmd shell | Fixed — located real interpreter at `D:\Programs\Python312\python.exe`, used full path for compile verification |

Fixed This Session: 2
Backlogged: 0
Logged: 0

## NEXT QUEUE
- Sprint 07 — Variable Reward / Info Scent — next in the numbered queue
- Consider a real follow-up: wire a `greg_meta` token type through the marked pipeline + `ConsecutiveDetailsGroup.svelte` if David wants the personality footer to be genuinely click-to-expand rather than a single muted line
- Confirm greg-ui's actual production deploy target (Docker/Railway/other) and add a Pre-Flight section to a new `CLAUDE_INSTRUCTIONS.md` so future sprints don't have to re-derive it
