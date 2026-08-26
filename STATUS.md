**Status:** active
**Phase:** Phase 0 complete, Phase 1a-1c in progress
**Last Sprint:** 2026-08-26 — sprint_tool.py fixed, SS-02 channel posting built in Home
**Last Updated:** 2026-08-26

## Current State

Gregore (Open WebUI fork) deployed on Sentinel as Docker container.
Phase 0 complete: CORTEX pipe function, depth models, channels, brain.db recall,
ROSETTA capture, daily brief automation, cptr agents on 3 machines.

CI pipeline fixed. Container live on Sentinel. Branding complete.

### Phase 1 Progress (2026-08-26)

**Sprint channel infrastructure (SS-02) built in Home (duke-of-beans/home):**
- Phase persistence: phased-executor.ts writes phase_history to sprint_queue.metadata
- Channel posting helper: sprint-channel.ts POSTs events to Gregore's channel API
- Wiring: claimed + completed/failed events fire-and-forget to Gregore
- v_sprint_queue view fixed (was missing metadata column — writes silently dropped)
- All verified end-to-end: metadata populates, Railway deployed

**sprint_tool.py fixed (fa55fb0):**
- Corrected Supabase schema (Accept-Profile: portfolio header added)
- Changed from anon key to service_role key (anon lacks portfolio grants)
- Fixed column names (sprint_id not id)
- Added cancel_sprint method
- Proper sprint_id generation, all required fields

**Pending David action (Sentinel):**
-  (for sprint_tool fix)
- Set SUPABASE_SERVICE_KEY in sprint_tool Valves via admin panel
- Set GREGORE_BOT_TOKEN, GREGORE_URL, SPRINT_CHANNEL_ID on Home Railway env vars
  (enables live channel posting — code is deployed, just needs credentials)

### Branding (2026-08-23)
- Favicon: canonical Schauberger vortex g from design-system/assets/logo/
- Two custom themes: Gregore Dark (Walnut) + Gregore Light (Linen)
- WEBUI_NAME=Gregore, title=Gregore, Greg purple accents

## Recent Commits
- fa55fb0 fix(sprint_tool): correct schema access, column names, key type
- 8142ffc4 theme: Gregore Dark + Gregore Light in theme selector
- 74acb993 brand: canonical design system assets
