# Sprint: /face Kiosk — Full Greg Face with Eye Tracking + Voice + Affect
# Covers: HEARTH Blueprint §9 (Face/Kiosk Mode)
# Repo: duke-of-beans/greg-ui
# File: src/routes/(app)/face/+page.svelte (already exists, basic version)

## Context
The /face route has a basic SVG face: ellipse eyes, blink animation, breathe
animation, mouth states, state indicator dots. This sprint makes it a real
conversational face that responds to Greg's cognitive state.

The face runs on the Skylight tablet (wall-mounted kiosk) and on M3 laptop.

## Task

### 1. Affect-Driven Expression
Connect the face to Greg's affect state via CORTEX's `affect` tool. **Do not
call CORTEX directly from this Svelte page with a hardcoded bearer token**
— this repo is public, and a token embedded in a `.svelte` file ships in
the JS bundle and git history. Route through the Open WebUI backend
instead, the same way `/home` does (see `backend/open_webui/routers/
greg_home.py`'s `/api/v1/greg/mcp` proxy, added in sprint 01): either reuse
that endpoint (add `'affect'` to its `ALLOWED_TOOLS` set) or add an
`/api/v1/greg/affect` route following the same pattern — `CORTEX_URL`/
`CORTEX_KEY` come from env vars via `greg_cortex_client.py`, never a
literal in source.
```
Body: { method: "tools/call", params: { name: "affect", arguments: {} }}
```

Returns: { surprise, novelty, arousal, reward, conflict, summary }

Map affect to face expressions:
- High surprise → wide eyes (eyeState='wide')
- High conflict → squint + slight frown
- High reward → smile
- High arousal → faster blink rate, slightly dilated pupils
- Neutral → default resting face

Poll affect every 10 seconds. Smooth transitions between states.

### 2. Conversation State
The face should reflect what Greg is doing:
- **Idle**: Slow blink, breathing, occasional look-around (head tilt drift)
- **Listening**: Eyes focused (slightly wider), mouth neutral, state dot green
- **Thinking**: Eyes squint slightly, head tilts, state dot amber (faster pulse)
- **Speaking**: Mouth animates (open/close cycle), eyes normal, state dot blue

Wire these to Open WebUI's chat state if possible, or use a simple
state machine driven by user interaction:
- User starts typing → listening
- Message sent → thinking
- Response streaming → speaking
- Response done → idle (after 2s delay)

### 3. Eye Tracking (Basic)
Subtle eye movement that makes the face feel alive:
- Micro-saccades: tiny random eye position shifts every 2-3 seconds
- Slow drift: eyes drift slightly left/right/up/down on a slow cycle
- Blink clusters: occasional double-blink (natural, not mechanical)

Implementation: Add cx/cy offsets to the eye ellipses, driven by
a slow noise function (use Math.sin with multiple frequencies for
organic movement).

### 4. Response Text Display
When Greg speaks (via the cortex_pipe in /chat), show the response
text below the face in a subtitle-style display:
- Fade in word by word or line by line
- Large readable text (1.2rem minimum)
- Auto-clear after 10 seconds of silence
- Positioned in the lower third of the screen

### 5. Voice Integration (Chatterbox TTS)
If Chatterbox TTS is available (http://host.docker.internal:8004/v1),
enable speech:
- After Greg's response arrives, send it to TTS
- Play audio while animating the mouth
- Sync mouth animation to audio duration (approximate)

For the kiosk, auto-play is important — no click-to-speak.
Note: browser autoplay policies may require an initial user interaction.
Add a "Tap to activate" overlay on first load that enables audio context.

### 6. Wake/Sleep Cycle
The face should have a presence cycle:
- Active: full expression, responding to state
- Resting: eyes half-closed, slower breathing, dimmer
- Sleeping: eyes closed, very slow breathing, minimal ambient glow

Transition to resting after 5 minutes of no interaction.
Transition to sleeping after 15 minutes.
Wake on any interaction (mouse move, touch, or new message).

## Constraints
- Pure Svelte, no external libraries
- SVG-based (no canvas, no WebGL)
- Must work on Skylight tablet browser (Chrome-based, limited GPU)
- Keep the page performant — no requestAnimationFrame heavy loops
- Use CSS animations where possible, JS only for state-driven changes
- Auto-hiding cursor (already implemented)
- Full black background, zero chrome (already implemented)
- Commit to duke-of-beans/greg-ui main branch
