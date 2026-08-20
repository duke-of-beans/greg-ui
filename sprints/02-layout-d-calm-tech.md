# Sprint: HEARTH /home — Layout D + Calm Technology + Hotel Lobby Zones
# Covers: DES-18 through DES-21, DES-25 through DES-29, DES-38 through DES-44
# Repo: duke-of-beans/greg-ui
# File: src/routes/(app)/home/+page.svelte (rewrite)

## Context
The /home route currently has a single-column centered layout with:
breathing dot, greeting, weather, journal input, Greg's thought, portals.
This sprint transforms it into Layout D — the full ambient dashboard.

## Task

### 1. Layout D Structure (DES-38 through DES-44)
Restructure the page into three zones:

**Top bar** (fixed, ~48px):
- Left: Greg presence dot (breathing animation) + "Greg" label
- Center: desk metrics — current thinking topic, mood emoji, budget %
  (fetch from CORTEX MCP ask_greg or fall back to static)
- Right: nav links to /chat and Consonance + dark/light mode toggle

**Left sidebar** (fixed width ~280px, scrollable):
Sections in FIXED order (DES-20 — never reorder):
1. While Away — items from overnight/since-last-visit
2. From Your Past — Throwbak "on this day" (placeholder card for now)
3. Connections — cross-portfolio links Greg noticed
4. Trust Ramp — colored dots per category, glanceable tiers
5. Murmuring — Greg's ambient thoughts (from greg_thoughts)

Each section: heading + 2-3 items max. Collapsed by default, expandable.

**Right main** (fluid):
1. Contextual greeting (from Sprint 01)
2. Needs Attention — urgent items (sprint failures, deploy issues)
3. Prometheus — cross-portfolio insights
4. Modules — expandable deep-dive panels
5. Conversation journal — at bottom, always visible

**Bottom journal bar** (DES-42):
Full-width, pinned to bottom. Text input + send button.
Same journal functionality as current implementation.

**Mobile** (DES-44): At < 768px, sidebar collapses to horizontal strip above main.

### 2. Calm Technology (DES-18 through DES-21)
- New items get a green `border-left: 3px solid #6b8f71` that auto-fades
  after 2 hours (use item timestamp, compute in reactive block)
- No persistent badges — items appear and naturally age out
- Section order is FIXED in code (not sortable, not dynamic)
- Subtle transitions: 300ms on border-color changes

### 3. Hotel Lobby Zones (DES-26 through DES-29)
- Journal at bottom = conversation continuation, not a form.
  Show last exchange (user entry + Greg's response) above the input.
- Urgent items (needs-attention) feel visually heavier — slightly elevated
  card with subtle shadow, border-left red/amber
- Ambient content (murmuring, from-past) feels lighter — transparent bg,
  lower opacity text
- Visual weight progression: front desk (top bar) → concierge (needs-attention)
  → seating (main content) → bar (journal)

### 4. Biophilic Touches (DES-22 through DES-25)
- Verify breathing dot is 4s cycle (it is — don't change)
- Card backgrounds: subtle differentiation between card types
  (opaque cards for actionable items, transparent for ambient)
- Border-left accents as consistent design language across all sections

### 5. Dark/Light Mode (DES-43)
- Default: dark (current warm black palette)
- Light mode: GregLite warm palette — cream/sand backgrounds,
  dark brown text, same green accent (#6b8f71)
- Toggle in top bar. Store preference in localStorage.
- CSS custom properties for all colors, swap via class on root

## Data Sources
Sidebar sections pull from CORTEX MCP:
- While Away: `recall` query "recent observations since {lastVisit}"
- Murmuring: `gaps_queue` with person_id='david'
- Trust: hardcoded placeholder for now (trust_categories table exists in Supabase)
- Others: placeholder cards with "coming soon" text

## Constraints
- Svelte, not React. This is an Open WebUI fork.
- No new npm dependencies
- Keep all existing functionality (weather, journal, breathing dot)
- Commit to duke-of-beans/greg-ui main branch
- The greg/ Python backend files handle the pipe/filter/tools — this sprint is frontend only
