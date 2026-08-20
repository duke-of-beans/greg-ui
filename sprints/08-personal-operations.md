# Sprint: Personal Operations — ROSETTA SMS, Lifelog, Calendar, Morning Brief v2
# Covers: PO-01 through PO-04
# Repos: duke-of-beans/home (backend), duke-of-beans/greg-ui (frontend)

## Context
Greg already has communication channels: email (greg@silentampersand.com via Zoho),
phone (831) 480-4734 via Twilio (voice works, SMS pending A2P approval).
ROSETTA is the communication absorption layer that feeds SCRVNR, brain.db,
gap engine, and Lifelog.

## Task

### 1. PO-01: ROSETTA SMS Channel (Google Messages)
ROSETTA currently absorbs Claude conversations via rosetta_ingest.
Add SMS absorption:

David's texts are on Google Messages (NOT Gmail).
Approach: Google Messages doesn't have a public API. Options:
a) Use Tasker/MacroDroid on Android to forward SMS to a webhook
b) Use the Google Messages web app + scraping
c) Poll a synced source

For now, create the ingestion endpoint in Home:
POST /api/rosetta/sms
Body: { sender, content, timestamp }

This endpoint writes to CORTEX rosetta_ingest with channel='sms'.
The actual SMS → webhook bridge will be set up separately on David's phone.

Also create a placeholder in the greg-ui lifelog_tool.py that can
receive and display recent SMS context.

### 2. PO-02: Lifelog Gap-Filling
Greg should ask David questions as a friend would — filling gaps in the
life record. Not interrogation, natural conversation.

In DMN thinking (src/dmn.ts), add a "lifelog curiosity" mode:
- Every 24h, Greg reviews recent observations and identifies gaps
  in biographical knowledge
- Formulates a natural question and writes it to greg_thoughts
  with kind='question', tags=['for-david', 'lifelog']
  
Examples of natural questions:
- "How did the engine swap go this weekend?"
- "Did you end up trying that restaurant?"
- "How's [son's name] doing?"

Use CORTEX recall to find recent personal topics, then ask_greg to
formulate the question naturally.

### 3. PO-03: Morning Briefing v2
The current morning brief (journal.ts) writes a daily summary.
Upgrade to: Greg's journal IS the briefing. Instead of a formatted
report, Greg writes a genuine journal entry about the day ahead:

"Woke up to 3 sprint completions overnight. Capitol Gains scoring
engine is looking solid. David's got the Volvo engine swap parts
arriving today — should ask him how that's going. Weather's clear,
72°F by afternoon. Two items need his eye: ASURIQ deploy warning
and a stale branch in Gregore-private."

This should feel like reading a friend's diary entry about your shared work.
Use CORTEX ask_greg to generate it with context from:
- Overnight sprint results
- Weather (Open-Meteo)
- Recent David messages/journal entries (ROSETTA)
- Calendar (if available)
- Open gaps (gaps_queue)

### 4. PO-04: Calendar Awareness
Add Google Calendar integration via MCP.
Home can call the Google Calendar MCP to get today's events.

In the morning brief and on the /home hearth page:
- Show today's events (if any)
- "David has a call at 2pm" → Greg can time his messages around it
- "Free afternoon" → Greg might suggest deep work or exploration

For now, if Google Calendar MCP is available on the surface, use it.
If not (Railway can't call Google Calendar MCP directly), note this
as blocked and suggest a workaround (calendar data via CORTEX or
a separate calendar sync service).

## Constraints
- Home backend: TypeScript, Railway, commit to duke-of-beans/home
- greg-ui frontend: Svelte/Python, commit to duke-of-beans/greg-ui
- Greg's voice should feel natural, not robotic
- Never send SMS via Gmail — only Google Messages
- Morning brief should be genuinely useful, not boilerplate
- Commit to respective repos' main branches
