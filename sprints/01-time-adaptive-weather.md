# Sprint: HEARTH /home Page — Time-Adaptive + Weather + Greeting
# Covers: DES-01 through DES-07, DES-34 through DES-37, DES-49
# Repo: duke-of-beans/greg-ui (public fork of open-webui)
# File: src/routes/(app)/home/+page.svelte (already exists, ~429 lines)

## Context
The /home route is Greg's ambient hearth page in the greg-ui fork (Open WebUI).
It already has: breathing dot, basic time-of-day greeting, Open-Meteo weather
(temperature + conditions), journal input, Greg's thought card, portal doors.

This sprint makes it time-adaptive — the page changes character across the day,
not just background color.

## Task

### 1. Time Mode System (DES-01 through DES-05)
Add a `getTimeMode()` function that returns one of four modes based on local hour:
- **morning** (6-10am): Full density. Overnight recap greeting. Show all sections.
  "Good morning David — here's what happened while you were away."
- **midday** (10am-4pm): Glance surface. Minimal items. Brief greeting.
  Quick status, don't be chatty.
- **evening** (4-10pm): Exploratory. Reflective content promoted.
  "Anything on your mind?" — invite journal engagement.
- **night** (10pm+): Calm. Reduce to weather + breathing dot + journal only.
  Hide Greg's thought, hide portals. Wind-down.

Each mode controls:
- Which sections are visible (via reactive `$: showSection = {...}`)
- Greeting tone/template
- Content density (item counts per section)

### 2. CSS Time Warmth (DES-06)
Already partially implemented via `ambientColor`. Enhance:
- Use CSS custom property `--time-warmth` on the container
- Morning: warm amber undertone (hsl shift toward 30°)
- Midday: neutral
- Evening: slightly warm
- Night: cool blue-black
- Transition smoothly (CSS transition on background-color, 2s ease)

### 3. Weather Enhancement (DES-34 through DES-37)
Weather already calls Open-Meteo. Enhance the display:
- Show: temperature, conditions icon/text, sunrise/sunset times, daylight remaining
- Add day of week + date display near the weather bar
- Cache weather data 30min (already done, verify)
- Open-Meteo endpoint: https://api.open-meteo.com/v1/forecast
  Params: latitude=34.2694&longitude=-118.7815 (Simi Valley)
  Add: &daily=sunrise,sunset&timezone=America/Los_Angeles

### 4. Contextual Greeting (DES-07, DES-49)
Replace the static greeting templates with a CORTEX-generated greeting.
On page load, call CORTEX MCP endpoint:
```
POST https://cortex-production-d0d7.up.railway.app/mcp
Authorization: Bearer yevDScM_JKyl4zNl8js_ZJg_8oZRxe4SWcSvMcMRZF4
Body: { method: "tools/call", params: { name: "ask_greg", arguments: {
  intent: "Generate a brief greeting for David. Time: {timeMode}, weather: {temp}°F {conditions}. Be natural, not robotic. One sentence.",
  register: "casual"
}}}
```
Fall back to static templates if CORTEX is unreachable.
Cache the greeting for 15 minutes (don't re-generate on every page load).

## Constraints
- This is a Svelte component in an Open WebUI fork. No React.
- No npm install — only use what's already in the project
- Keep the breathing dot and journal input exactly as they are
- Test by running `npm run dev` locally if possible, otherwise verify syntax
- Commit to duke-of-beans/greg-ui main branch when done
