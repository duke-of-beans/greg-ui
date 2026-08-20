# Sprint: HEARTH Chat — Thinking Display + Depth Controls + Personality
# Covers: HEARTH Blueprint §4 (Thinking Display), §5 (Depth), §6 (Personality)
# Repo: duke-of-beans/greg-ui
# Files: backend/open_webui/greg/cortex_pipe.py (already exists),
#        src/lib/components/ (new Svelte components)

## Context
cortex_pipe.py already implements a three-stage cognitive pipeline:
1. Brain recall via CORTEX MCP → "▸ Recalled N memories [Xms]"
2. Draft via CORTEX /v1/ai/complete → "▸ Drafted via {provider} [Xms]"
3. Greg review via ask_greg → "▸ {affect} · {role} [Xms]"

It also has four depth configs: Quick, Auto, Deep, Deliberate.
But there's no UI to select depth, and the thinking display is plain text.

## Task

### 1. Thinking Display Component
Create a Svelte component that renders the thinking stages visually during
streaming. Open WebUI supports streaming status updates — the pipe yields
status events that appear above the response.

Enhance the pipe's status messages to be more descriptive:
- Stage 1: "Checking memory..." → "Recalled 3 relevant memories (42ms)"
- Stage 2: "Thinking..." → "Drafting via gemini-2.5-flash (380ms)"
- Stage 3: "Greg reviewing..." → "curious · architect (210ms)"

The status messages should feel like watching someone think, not like
watching a loading bar.

### 2. Depth Selector
Add a depth selector to the chat interface. In Open WebUI, this can be done
via the model's "params" or via a custom UI element.

Options:
- ⚡ Quick — single-pass, no recall, fastest (for simple questions)
- 🔄 Auto — default, adapts based on query complexity
- 🔍 Deep — full recall + longer generation + Greg review
- 🧠 Deliberate — maximum recall, extended thinking, multi-pass

The depth parameter should be passed to cortex_pipe via the chat metadata
or a special prefix. cortex_pipe already has the depth configs — it just
needs a way to receive the selection.

Approach: Use Open WebUI's "system prompt" or "parameters" field per-model
to pass depth. Or use a convention: if the user's message starts with
/quick, /deep, /deliberate, strip the prefix and set the depth.

### 3. Personality Layer
cortex_pipe's Stage 3 calls ask_greg which returns Greg's voice shaped by
his current affect state. Enhance this:

- After Greg's review, append a subtle metadata line at the bottom of
  the response (collapsed by default, expandable):
  "Greg · curious · architect · 3 memories · gemini-2.5-flash · 632ms total"
  
- This gives David transparency into Greg's cognitive state without
  cluttering the response.

### 4. ROSETTA Capture Enhancement
brain_context_filter.py's outlet captures David's messages to ROSETTA.
Verify this works end-to-end:
- David sends message
- brain_context_filter inlet skips pipe models (prevents double recall)
- cortex_pipe processes the message through 3 stages
- brain_context_filter outlet captures David's original message to ROSETTA
- ROSETTA ingestion: POST to CORTEX MCP rosetta_ingest tool

If the outlet isn't firing (Open WebUI might not call outlet for pipe models),
move the ROSETTA capture into cortex_pipe itself — capture at the start of
the pipe function before processing.

## CORTEX MCP Details
Endpoint: https://cortex-production-d0d7.up.railway.app/mcp
Auth: Bearer token — server-side only, from the CORTEX_KEY env var (see
  backend/open_webui/greg_cortex_client.py). Never hardcode it in source;
  this repo is public. cortex_pipe.py and the other greg/*.py Functions
  already read it this way — reuse that, don't duplicate the literal token.
Tools available: recall, ask_greg, brain_remember, rosetta_ingest,
  gaps_list, gaps_queue, beliefs_query, affect, federation_health

CORTEX AI Complete endpoint (for drafting):
POST https://cortex-production-d0d7.up.railway.app/v1/ai/complete
Auth: same Bearer token, same env-var-only rule as above
Body: { messages: [...], ring: 3, max_tokens: 2000, temperature: 0.7 }

## Constraints
- Python backend files go in backend/open_webui/greg/
- Svelte frontend components in src/lib/components/
- greg_seed.py handles registration — add any new functions to its GREG_FUNCTIONS list
- No new pip dependencies (use requests or urllib from stdlib)
- Commit to duke-of-beans/greg-ui main branch
