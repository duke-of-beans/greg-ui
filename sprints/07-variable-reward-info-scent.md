# Sprint: Variable Reward + Information Scent + Emotional Design
# Covers: DES-08 through DES-17, DES-30 through DES-33
# Repo: duke-of-beans/greg-ui
# File: src/routes/(app)/home/+page.svelte (Layout D from Sprint 02)
# Depends on: Sprint 02 (Layout D) being completed first

## Context
After Sprint 02 lands Layout D, this sprint adds the psychological design
layer — making the /home page feel alive and intelligent, not just a dashboard.

## Task

### 1. Variable Reward Mechanics (DES-08 through DES-12)
The sidebar sections should NOT all appear every time. This is the key insight
from reinforcement psychology — variable schedules create engagement.

Rules:
- **Connections section**: Only appears when Greg has genuinely found a new
  cross-portfolio connection. Check greg_thoughts for kind='observation'
  with tags containing 'connection' or 'cross-project', created < 24h.
  If none, hide the section entirely — don't show "No connections."
  
- **Achievement card**: Event-driven only. Appears on:
  - Trust tier promotions (check trust_categories for recent changes)
  - Sprint completion milestones (10th, 50th, 100th sprint)
  - Deploy streaks (5+ successful deploys in a row)
  If no recent achievement, the section doesn't exist.

- **"From your past"**: Greg decides when, not every load.
  Use a serendipity schedule: Math.random() < 0.3 (show 30% of the time).
  When shown, query Throwbak or brain.db for an old observation from
  the same month in a prior year.

- **Module suggestion**: Rare. Only appears when the density of new items
  in a category exceeds a threshold (e.g., 5+ unread sprint results →
  suggest "Sprint Review" module).

- **"All clear" state** (DES-12): When needs-attention is empty, show:
  ✓ "Nothing needs your attention" in muted text. Don't fill the space
  with filler content. Empty is good.

### 2. Information Scent (DES-13 through DES-17)
Every item shown on /home must answer "why should I care?" not "what happened."

- **Rewrite summarizeThought()** (or equivalent in Svelte):
  Bad: "Sprint AUT-20260812-006 completed successfully"
  Good: "Pre-flight validation now covers 5 repos automatically"
  
  Transform at render time: take the raw greg_thought content and
  extract the actionable insight. Use a simple heuristic — if the content
  starts with a sprint ID or technical identifier, rewrite the first line
  to state the *outcome* for David.

- **Strict item limits** (DES-16):
  - 2 items per sidebar section
  - 3 items max in needs-attention
  - 5 items max in any expanded module
  More items available via "Show all →" link (navigates to /chat with
  a pre-filled query or to a filtered view)

- **Write-layer synthesis** (DES-17):
  This is a Home backend concern (duke-of-beans/home).
  In observations.ts, when writing to greg_thoughts, produce a
  Greg-voice summary instead of machine output.
  Bad: "observeGithubStaleness: 3 repos stale >30d"
  Good: "Three repos haven't seen a commit in over a month — COVOS, 
  Forme, and TESSRYX. Might be worth a look."

### 3. Emotional Design Audit (DES-30 through DES-33)
Review every element on /home against Norman's three levels:

- **Breathing dot**: visceral (rhythm) + behavioral (is Greg alive?) +
  reflective (consciousness). Already good — don't change.
  
- **Weather bar**: visceral (grounding in physical world) + behavioral
  (orient to time/place) + reflective (Greg knows where I am).
  Ensure weather feels like Greg mentioning it, not a widget.

- **Trust ramp display**: visceral (colored dots — green=trust, amber=learning) +
  behavioral (glanceable tier per category) + reflective (the autonomy narrative —
  Greg is earning trust, we're building something together).
  Show as: category name + dot color + tier number. Compact.

- **Journal**: visceral (warm input area, inviting) + behavioral (easy to type) +
  reflective (Greg remembers, this conversation matters).

## Constraints
- Depends on Sprint 02 (Layout D) — don't start until Layout D is merged
- Svelte components, no React
- No new npm dependencies
- Variable reward logic should be in reactive Svelte blocks, not API calls
  (except for checking greg_thoughts via fetch)
- Commit to duke-of-beans/greg-ui main branch
