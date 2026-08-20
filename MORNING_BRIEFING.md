# MORNING BRIEFING — greg-ui (HEARTH Chat)
**Sprint:** 10 — Capacity Governor + Sprint Control Surface
**Date:** 2026-08-20
**Session Duration:** ~1h

## SHIPPED
- **greg-ui frontend, applied to working tree (not yet committed — see FRICTION LOG #1):**
  - Capacity governor strip under the top bar in `(app)/home/+page.svelte`: gradient bar,
    mode label, "N% remaining · N days left", and a reserve-mode "Claude Code paused" warning.
  - Sprint Control Surface module: last 5 sprints with status/project/priority/lane, elapsed
    time + model for running sprints, Hold button on pending sprints, Cancel button on running
    sprints.
  - Cost Dashboard chips: today's spend, this-cycle spend vs $200, top-3-projects breakdown —
    derived client-side from the same 5-sprint list (see NEXT QUEUE — this is a last-5 sample,
    not a real cycle aggregate).
  - New backend proxy routes in `routers/greg_home.py`: `GET /home/capacity`,
    `GET /home/sprints`, `PATCH /home/sprints/action` — mirror the existing CORTEX-proxy
    pattern (credentials stay server-side, browser never talks to Home directly).
  - New `greg_home_api_client.py`, mirrors `greg_cortex_client.py`'s shape exactly.
  - `.env.example` and `docker-compose.greg.yaml`: added `GREG_HOME_API_URL` (defaulted to
    Home's real Railway domain, looked up via the Railway API — see UNEXPECTED FINDINGS) and
    `GREG_HOME_API_KEY` (blank — Home doesn't check it yet, see FRICTION LOG #3).
- **portfolio.max_capacity table** created in Consonance Supabase (migration
  `create_max_capacity_table`), plus a `metadata jsonb` column added to `portfolio.sprint_queue`
  (it had none — needed for per-sprint cost capture).
- **Home backend, drafted only — NOT applied** (Sprint 05 was running in
  `D:\Projects\Home` all session; David asked me not to touch it): `src/capacity.ts` (full
  file) and `HOME_CAPACITY_INTEGRATION.md` (exact snippets for `index.ts`, `home-api.ts`,
  `server.ts`) delivered to David as files. Apply after Sprint 05 lands and `git pull` is clean.

## QUALITY GATES
| Gate | Result |
|------|--------|
| Svelte `<script>` block — extracted + `tsc --noEmit` syntax pass | PASS (only pre-existing `$:`-implicit-declaration false positives, same pattern the file already had for `showSection`/`warmth`; no new error categories) |
| `greg_home_api_client.py`, `greg_home.py` — `python3 -m py_compile` | PASS |
| `capacity.ts` (drafted, not applied) — `tsc --noEmit` syntax pass | PASS (only missing-`@types/node` noise, expected outside the real project) |
| Brace/tag balance sweep on the edited `.svelte` file | PASS (24/24 `{#if}`, 7/7 `{#each}`, 0 net brace depth) |
| **Real Svelte build (`svelte-check` / `vite build`)** | **NOT RUN** — see FRICTION LOG #1 |
| Git pull before starting | Not applicable to greg-ui this session (no prior local diff); **git commit/push not done** — see FRICTION LOG #1 |

## DECISIONS MADE BY AGENT
- **Did not touch `D:\Projects\Home` at all**, per David's explicit instruction (Sprint 05 running
  there). Everything Home-side is a drafted handoff, not applied.
- **Chose a new `PATCH /api/home/sprints/action` route instead of overloading the existing
  `PATCH /api/home/action`.** The existing route's `handleActionItem()` operates on
  `greg_thoughts` UUIDs; `sprint_queue.sprint_id` is a different ID shape (text, e.g.
  `AUT-...`) with different semantics (hold/cancel vs approve/dismiss/defer). Overloading one
  endpoint with two unrelated ID types seemed like the wrong call to make unilaterally —
  flagged as a new route instead, documented in `HOME_CAPACITY_INTEGRATION.md`.
- **Did not fabricate real Claude Code token telemetry.** The Claude Code subprocess path in
  `index.ts` hardcodes `tokens: {input:0, output:0}` (MAX is flat-rate, not metered per-call).
  Rather than inventing a precise-looking number, `capacity.ts`'s usage-logging call is a
  clearly-labeled duration-based estimate with a TODO pointing at `claude --print
  --output-format json` as the real fix.
- **Looked up Home's real Railway domain via a read-only Railway API call** (`domains` query,
  no deploy/env mutation) rather than leaving a placeholder — safe against Sprint 05 since it
  doesn't touch the running deployment.
- **Did not set `HOME_API_KEY` / `GREG_HOME_API_KEY` on Railway myself**, even though I have a
  Railway API token that could do it. Setting a Railway env var typically triggers a redeploy,
  which would have restarted Home mid-Sprint-05. Documented as a manual follow-up instead.

## UNEXPECTED FINDINGS
- **greg-ui's `/home` page had zero connection to the Home backend before this sprint.**
  Sprint 10's spec assumed "Pull from Home API: GET /api/home/desk already has budget info" as
  if the frontend already called it — it didn't. The `/home` hearth page only ever called
  CORTEX MCP (`/greg/mcp`, `/greg/greeting`). This sprint had to build the entire bridge
  (Python client + proxy routes + env wiring), not just consume an existing one.
- **There is no standalone `GET /api/home/desk` route on Home.** `handleGetDesk()` is nested
  inside `GET /api/home`'s aggregate response under `.desk`. Wired the proxy and
  `capacity_state` placement to match that, not the spec's assumed route shape.
- **Home's `/api/home/*` HTTP surface has no inbound authentication at all**, and is reachable
  at a public Railway domain (`executor-production-f8aa.up.railway.app`). This predates Sprint
  10, but Sprint 10 adds a new state-mutating endpoint (hold/cancel a sprint) to that
  unauthenticated surface, which is enough that I flagged it rather than quietly building on
  top of it. See `HOME_CAPACITY_INTEGRATION.md` §6b.
- **Cancelling a running Claude Code sprint isn't really possible with the current dispatch
  code.** It uses `execSync()`, which blocks synchronously — no subprocess handle survives to
  kill mid-flight. The drafted `handleSprintAction('cancel')` only flips `sprint_queue.status`;
  it doesn't interrupt the process. Real cancellation needs `execSync` → `spawn()` + a PID map,
  which is a separate refactor, not scoped into this sprint.
- **`portfolio.sprint_queue` had no `metadata` column** despite the spec assuming
  "Store per-sprint cost in sprint_queue metadata" — added it as part of the same migration
  that created `max_capacity`.

## FRICTION LOG
| # | Category | Description | Resolution |
|---|----------|--------------|------------|
| 1 | TOOL | `device_bash` (the isolated Linux environment on David's machine) was unavailable for the entire session ("Workspace unavailable... failed to start"), on every retry. That blocked running the real Svelte build/`svelte-check`, and blocked `git add/commit/push` for greg-ui entirely. | Not fixed this session — did the best static verification available (extracted-script `tsc --noEmit`, `py_compile`, brace/tag balance) and left the working-tree changes applied via the file bridge, uncommitted. **David needs to `git status`, review, and commit/push greg-ui himself, or ask me to retry once `device_bash` recovers.** |
| 2 | TOOL | This session's GitHub API access is not attached to either `duke-of-beans/home` or `duke-of-beans/greg-ui` (`api.github.com` calls return "GitHub access to this repository is not enabled for this session... Use add_repo") — and I don't have an `add_repo` tool. | Worked entirely through the device bridge (file read/write) plus Supabase/Railway MCP tools instead. |
| 3 | SCOPE | Home's `/api/home/*` routes have no inbound auth — adding one means a Railway env var (redeploy risk mid-Sprint-05) plus a `server.ts` code change I couldn't make. | Documented as a required follow-up in `HOME_CAPACITY_INTEGRATION.md` §6b; not fixed this session by design. |

Fixed This Session: 0
Backlogged: 3 (device_bash recovery + commit, Home auth gap, real token telemetry for capacity)
Logged: 0

## NEXT QUEUE
- **Apply `HOME_CAPACITY_INTEGRATION.md` to `D:\Projects\Home`** once Sprint 05 is clear:
  `git pull`, drop in `capacity.ts`, apply the `index.ts`/`home-api.ts`/`server.ts` snippets,
  `npm run build` (or whatever the real build command is — I didn't have a way to check),
  then commit/push.
- **Add `HOME_API_KEY` auth** to Home's `/api/home/*` routes (§6b) before this surface sees any
  real traffic — right now `PATCH /api/home/sprints/action` is an unauthenticated way to cancel
  Greg's work from anyone who has the Railway domain.
- **Commit + push greg-ui** — the working tree has this sprint's changes but nothing is
  committed. Either retry with me once `device_bash` is back, or handle it directly.
- **Real token telemetry for the Claude Code lane**: switch `claude --print` to
  `--output-format json` in `index.ts` so `logCapacityUsage()` can log real counts instead of a
  duration-based estimate.
- **Cost Dashboard is currently last-5-sprints-only**, not a real cycle aggregate — if David
  wants an accurate "$X.XX this cycle" figure, `handleListSprints()`/the frontend need a
  dedicated cost-aggregate query against `max_capacity`/`sprint_queue` scoped to
  `cycle_start`, not just the 5 most recent rows.
- Sprint 11 — next in the numbered queue.
