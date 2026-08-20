# Sprint: Capacity Governor + Sprint Control Surface
# Covers: HEARTH Blueprint §7 (Capacity Governor), EXEC-09, EXEC-10, EXEC-12
# Repos: duke-of-beans/home (backend), duke-of-beans/greg-ui (frontend)

## Context
Greg runs Claude Code sprints via MAX subscription ($200/mo). The MAX pool
is shared between David's interactive claude.ai/desktop usage and Greg's
autonomous sprint execution. A capacity governor prevents Greg from eating
David's interactive headroom.

The Harvester design pattern (built July 2026 for Tranche's surplus_harvester.py)
applies here: continuous curve (conservative early, aggressive tail), never
eat interactive headroom.

MAX resets weekly (Thursday-Thursday).

## Task

### 1. Capacity Tracking (Home Backend)
Create src/capacity.ts in the Home codebase:

```typescript
interface CapacityState {
  cycle_start: string;      // ISO date of current cycle start (Thursday)
  cycle_end: string;        // ISO date of current cycle end (next Thursday)  
  estimated_remaining_pct: number;  // 0-100
  tokens_used_by_greg: number;      // this cycle
  tokens_used_by_david: number;     // estimated (total - greg)
  mode: 'abundant' | 'moderate' | 'scarce' | 'reserve';
  claude_code_enabled: boolean;     // false when in reserve mode
}
```

Mode thresholds (as % remaining):
- abundant (>60%): Claude Code sprints run freely
- moderate (30-60%): Claude Code for P0/P1 only
- scarce (10-30%): AI Gateway only, Claude Code paused
- reserve (<10%): INVIOLATE — reserved for David's interactive use

Track Greg's Claude Code token usage by logging each sprint's token count
to Supabase portfolio.max_capacity (create this table if it doesn't exist):
```sql
CREATE TABLE portfolio.max_capacity (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  cycle_start date NOT NULL,
  tokens_used bigint DEFAULT 0,
  source text NOT NULL, -- 'greg_sprint', 'greg_dmn', 'david_interactive'
  sprint_id text,
  created_at timestamptz DEFAULT now()
);
```

### 2. Harvester Curve
In the sprint poller (src/index.ts pollQueue()), before dispatching a sprint:
- Check capacity state
- If mode='scarce' or 'reserve', skip Claude Code dispatch
- If mode='moderate', only dispatch P0/P1 sprints to Claude Code
- All skipped sprints route to AI Gateway (free tier) instead

Early in the cycle: conservative (save capacity for David).
Late in the cycle: aggressive (use surplus before reset).

### 3. Capacity UI on /home
On the hearth page's top bar (from Sprint 02 Layout D), show:
- Capacity bar: thin horizontal bar, green→amber→red gradient
- Current mode label: "abundant" / "moderate" / "scarce" / "reserve"
- "73% remaining · 4 days left" text
- If in reserve mode: "Claude Code paused — AI Gateway only"

Pull from Home API: GET /api/home/desk already has budget info.
Add capacity_state to the desk response.

### 4. Sprint Control Surface (EXEC-09 partial)
On /home, add a "Sprints" section to the main content:
- Show last 5 sprints with status (completed/running/failed/pending)
- For running sprints: show elapsed time, model, project
- For pending: show queue position, priority, lane
- "Hold" button on pending sprints (calls PATCH /api/home/action with
  action='defer')
- "Cancel" button on running sprints (if possible)

Data source: Supabase portfolio.sprint_queue via the sprint_tool.py
or via Home API endpoint.

### 5. Cost Dashboard (EXEC-10 partial)
Add to /home's desk metrics:
- Today's spend: $X.XX (Greg sprints only)
- This cycle: $X.XX / $200 limit
- Per-project breakdown (top 3 projects by spend)

Store per-sprint cost in sprint_queue metadata (the AI Gateway response
includes cost in usage.cost field — capture this after each completion).

## Constraints
- Capacity tracking is best-effort — we can't query MAX remaining directly
  from Anthropic's API. Track what Greg uses and estimate David's from
  observable MAX throttling/errors.
- Harvester curve is simple v1: linear interpolation between thresholds,
  not the full sigmoid from surplus_harvester.py
- Home backend: TypeScript, Railway, commit to duke-of-beans/home
- greg-ui frontend: Svelte, commit to duke-of-beans/greg-ui
- Create the portfolio.max_capacity table in Consonance Supabase
