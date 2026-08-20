<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';

	// ============================================================
	// Sprint 09 — /face kiosk full expression
	// CORTEX affect + ask_greg are proxied through the Open WebUI
	// backend (/api/v1/greg/mcp), the same pattern the /home hearth
	// page uses (sprint 01). The CORTEX bearer token lives server-side
	// only (see greg_cortex_client.py) — this page never sees it and
	// it never ships in the JS bundle.
	// ============================================================
	async function cortexCall(tool: string, args: Record<string, unknown> = {}) {
		const res = await fetch(`${WEBUI_API_BASE_URL}/greg/mcp`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				authorization: `Bearer ${localStorage.token}`
			},
			body: JSON.stringify({ tool, arguments: args })
		});
		if (!res.ok) throw new Error(`CORTEX proxy error ${res.status}`);
		const data = await res.json();
		return data?.text as string | undefined;
	}

	function safeParse(text: string | undefined) {
		if (!text) return null;
		try {
			return JSON.parse(text);
		} catch {
			return null;
		}
	}

	// --- Affect state (Task 1) ---
	type Affect = {
		surprise: number;
		novelty: number;
		arousal: number;
		reward: number;
		conflict: number;
		summary?: string;
	};
	let affect: Affect = { surprise: 0, novelty: 0, arousal: 0, reward: 0, conflict: 0 };
	let affectInterval: ReturnType<typeof setInterval>;

	async function pollAffect() {
		try {
			const text = await cortexCall('affect');
			const parsed = safeParse(text);
			if (parsed) affect = { surprise: 0, novelty: 0, arousal: 0, reward: 0, conflict: 0, ...parsed };
		} catch {
			// CORTEX unreachable — keep the last known affect and stay neutral.
		}
	}

	// --- Face state ---
	let blinking = false;
	let mouthOpenPhase = false;
	let headTilt = 0; // degrees
	let idleHeadTilt = 0;
	let breatheScale = 1;
	let conversationState: 'idle' | 'listening' | 'thinking' | 'speaking' = 'idle';

	// --- Presence / wake-sleep cycle (Task 6) ---
	let presence: 'active' | 'resting' | 'sleeping' = 'active';
	let lastInteraction = Date.now();
	let presenceInterval: ReturnType<typeof setInterval>;
	const RESTING_MS = 5 * 60 * 1000;
	const SLEEPING_MS = 15 * 60 * 1000;

	function checkPresence() {
		const idleMs = Date.now() - lastInteraction;
		presence = idleMs > SLEEPING_MS ? 'sleeping' : idleMs > RESTING_MS ? 'resting' : 'active';
	}

	function registerInteraction() {
		lastInteraction = Date.now();
		if (presence !== 'active') presence = 'active';
		if (!audioUnlocked) unlockAudio();
	}

	let responseText = '';
	let cursorHidden = false;
	let cursorTimeout: ReturnType<typeof setTimeout>;
	let blinkTimeout: ReturnType<typeof setTimeout>;
	let breatheInterval: ReturnType<typeof setInterval>;
	let saccadeTimeout: ReturnType<typeof setTimeout>;
	let idleLookInterval: ReturnType<typeof setInterval>;
	let revealInterval: ReturnType<typeof setInterval>;
	let clearResponseTimeout: ReturnType<typeof setTimeout>;

	// --- Time-of-day warmth ---
	let warmth = 0.5;
	function updateWarmth() {
		const hour = new Date().getHours();
		if (hour >= 6 && hour < 10) warmth = 0.7; // morning amber
		else if (hour >= 10 && hour < 16) warmth = 0.5; // midday neutral
		else if (hour >= 16 && hour < 20) warmth = 0.6; // evening warm
		else warmth = 0.3; // night cool
	}

	// --- Blink (with occasional natural double-blink cluster) ---
	function blink() {
		blinking = true;
		setTimeout(() => {
			blinking = false;
			if (Math.random() < 0.18) {
				setTimeout(blink, 200 + Math.random() * 150);
			}
		}, 150);
	}

	function startBlinking() {
		function scheduleNext() {
			// High arousal → faster blink rate (Task 1).
			const arousalCut = affect.arousal * 3500;
			const base = 3500 + Math.random() * 3500 - arousalCut;
			blinkTimeout = setTimeout(() => {
				blink();
				scheduleNext();
			}, Math.max(1200, base));
		}
		scheduleNext();
	}

	// --- Breathe, eye drift, and micro-saccades (Task 3) ---
	// Driven off one low-frequency tick (~15fps) rather than requestAnimationFrame,
	// per the "no rAF heavy loops" constraint.
	let driftPhaseX = 0;
	let driftPhaseY = 0;
	let saccadeX = 0;
	let saccadeY = 0;
	let eyeOffsetX = 0;
	let eyeOffsetY = 0;

	function startBreathing() {
		let phase = 0;
		breatheInterval = setInterval(() => {
			const speed = presence === 'sleeping' ? 0.015 : presence === 'resting' ? 0.03 : 0.05;
			const amp = presence === 'sleeping' ? 0.004 : presence === 'resting' ? 0.006 : 0.008;
			phase += speed;
			breatheScale = 1 + Math.sin(phase) * amp;

			// Slow organic drift — two sine frequencies summed, per the sprint note.
			driftPhaseX += 0.008;
			driftPhaseY += 0.006;
			const driftX = Math.sin(driftPhaseX) * 3 + Math.sin(driftPhaseX * 2.3) * 1.2;
			const driftY = Math.sin(driftPhaseY) * 2;
			eyeOffsetX = driftX + saccadeX;
			eyeOffsetY = driftY + saccadeY;
		}, 66); // ~15fps
	}

	function scheduleSaccade() {
		const delay = 2000 + Math.random() * 1000; // every 2-3s
		saccadeTimeout = setTimeout(() => {
			saccadeX = (Math.random() - 0.5) * 10;
			saccadeY = (Math.random() - 0.5) * 6;
			setTimeout(() => {
				saccadeX = 0;
				saccadeY = 0;
			}, 350);
			scheduleSaccade();
		}, delay);
	}

	// --- Idle look-around head tilt drift (Task 2) ---
	function startIdleLookAround() {
		idleLookInterval = setInterval(() => {
			if (conversationState !== 'idle') return;
			if (Math.random() < 0.2) {
				idleHeadTilt = (Math.random() - 0.5) * 6; // -3..3 deg
				setTimeout(
					() => {
						idleHeadTilt = 0;
					},
					1500 + Math.random() * 1500
				);
			}
		}, 4000);
	}

	// --- Cursor auto-hide ---
	function onMouseMove() {
		cursorHidden = false;
		clearTimeout(cursorTimeout);
		cursorTimeout = setTimeout(() => {
			cursorHidden = true;
		}, 3000);
		registerInteraction();
	}

	// --- Response subtitle display (Task 4) ---
	// Word-by-word reveal, auto-clears after 10s of silence.
	function showResponse(text: string) {
		clearInterval(revealInterval);
		clearTimeout(clearResponseTimeout);
		const words = text.split(/\s+/).filter(Boolean);
		let revealedCount = 0;
		responseText = '';
		revealInterval = setInterval(() => {
			revealedCount++;
			responseText = words.slice(0, revealedCount).join(' ');
			if (revealedCount >= words.length) {
				clearInterval(revealInterval);
				scheduleResponseClear();
			}
		}, 140);
	}

	function scheduleResponseClear() {
		clearTimeout(clearResponseTimeout);
		clearResponseTimeout = setTimeout(() => {
			responseText = '';
		}, 10000);
	}

	// --- Voice (Chatterbox TTS via Open WebUI's built-in /api/v1/audio/speech —
	// already wired to Chatterbox in docker-compose.greg.yaml via
	// AUDIO_TTS_ENGINE=openai / AUDIO_TTS_OPENAI_API_BASE_URL, so this page
	// only needs to call the standard speech endpoint, same as the rest of
	// the app.) (Task 5)
	let audioEl: HTMLAudioElement;
	let audioUnlocked = false;
	let mouthInterval: ReturnType<typeof setInterval>;

	function unlockAudio() {
		if (audioUnlocked || !audioEl) return;
		audioUnlocked = true;
		try {
			audioEl.muted = true;
			audioEl
				.play()
				.then(() => {
					audioEl.pause();
					audioEl.currentTime = 0;
					audioEl.muted = false;
				})
				.catch(() => {
					audioEl.muted = false;
				});
		} catch {
			/* autoplay unlock is best-effort */
		}
	}

	async function speak(text: string) {
		conversationState = 'speaking';
		showResponse(text);

		let ttsOk = false;
		if (audioUnlocked) {
			try {
				const res = await fetch(`${WEBUI_API_BASE_URL}/audio/speech`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						authorization: `Bearer ${localStorage.token}`
					},
					body: JSON.stringify({ input: text })
				});
				if (res.ok) {
					const blob = await res.blob();
					const url = URL.createObjectURL(blob);
					ttsOk = true;
					await new Promise<void>((resolve) => {
						function cleanup() {
							audioEl.removeEventListener('ended', onEnded);
							audioEl.removeEventListener('error', onError);
							clearInterval(mouthInterval);
							mouthOpenPhase = false;
							URL.revokeObjectURL(url);
						}
						function onEnded() {
							cleanup();
							resolve();
						}
						function onError() {
							cleanup();
							resolve();
						}
						audioEl.addEventListener('ended', onEnded);
						audioEl.addEventListener('error', onError);
						mouthInterval = setInterval(() => {
							mouthOpenPhase = !mouthOpenPhase;
						}, 180);
						audioEl.src = url;
						audioEl.play().catch(() => {
							cleanup();
							resolve();
						});
					});
				}
			} catch {
				ttsOk = false;
			}
		}

		if (!ttsOk) {
			// No audio (locked, unavailable, or errored) — approximate the
			// speaking duration from text length so the mouth still animates
			// and the state machine still resolves.
			const duration = Math.min(8000, Math.max(1200, text.length * 55));
			mouthInterval = setInterval(() => {
				mouthOpenPhase = !mouthOpenPhase;
			}, 180);
			await new Promise((r) => setTimeout(r, duration));
			clearInterval(mouthInterval);
			mouthOpenPhase = false;
		}

		setTimeout(() => {
			if (conversationState === 'speaking') conversationState = 'idle';
		}, 2000);
	}

	// --- Minimal kiosk input → CORTEX ask_greg (Task 2) ---
	// Open WebUI's chat UI and the cortex_pipe Function live on /c/[id];
	// this kiosk page has no chat surface of its own today, so the
	// conversation state machine is driven by this small input for now.
	let userInput = '';
	let typingTimeout: ReturnType<typeof setTimeout>;

	function onUserTyping() {
		registerInteraction();
		if (conversationState === 'idle') conversationState = 'listening';
		clearTimeout(typingTimeout);
		typingTimeout = setTimeout(() => {
			if (conversationState === 'listening') conversationState = 'idle';
		}, 4000);
	}

	async function sendMessage() {
		const text = userInput.trim();
		if (!text || conversationState === 'thinking' || conversationState === 'speaking') return;
		userInput = '';
		clearTimeout(typingTimeout);
		registerInteraction();
		conversationState = 'thinking';
		try {
			const reply = (await cortexCall('ask_greg', { intent: text, register: 'casual' }))?.trim();
			await speak(reply || "I didn't catch that.");
		} catch {
			await speak("I'm having trouble reaching CORTEX right now.");
		}
	}

	function onInputKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}

	// --- Lifecycle ---
	onMount(() => {
		updateWarmth();
		startBlinking();
		startBreathing();
		scheduleSaccade();
		startIdleLookAround();
		blink(); // initial blink

		pollAffect();
		affectInterval = setInterval(pollAffect, 10000);

		checkPresence();
		presenceInterval = setInterval(checkPresence, 30000);

		window.addEventListener('keydown', registerInteraction);
		window.addEventListener('touchstart', registerInteraction, { passive: true });
	});

	onDestroy(() => {
		clearTimeout(blinkTimeout);
		clearInterval(breatheInterval);
		clearTimeout(cursorTimeout);
		clearTimeout(saccadeTimeout);
		clearInterval(idleLookInterval);
		clearInterval(affectInterval);
		clearInterval(presenceInterval);
		clearInterval(revealInterval);
		clearTimeout(clearResponseTimeout);
		clearTimeout(typingTimeout);
		clearInterval(mouthInterval);
		if (typeof window !== 'undefined') {
			window.removeEventListener('keydown', registerInteraction);
			window.removeEventListener('touchstart', registerInteraction);
		}
	});

	// Eye state priority: blink (transient) > conversation state > affect > default.
	$: baseEyeState =
		conversationState === 'thinking'
			? 'squint'
			: conversationState === 'listening'
				? 'wide'
				: affect.surprise > 0.6
					? 'wide'
					: affect.conflict > 0.55
						? 'squint'
						: 'open';
	$: eyeState = blinking ? 'blinking' : baseEyeState;

	$: baseEyeHeight =
		eyeState === 'blinking' ? 2 : eyeState === 'wide' ? 22 : eyeState === 'squint' ? 10 : 16;
	// Wake/sleep cycle scales eye openness down (Task 6).
	$: presenceEyeScale = presence === 'sleeping' ? 0.06 : presence === 'resting' ? 0.45 : 1;
	$: eyeHeight = eyeState === 'blinking' ? 2 : baseEyeHeight * presenceEyeScale;
	$: eyeRy = eyeHeight / 2;

	// Slightly dilated pupils on high arousal (Task 1).
	$: pupilR = 3 + affect.arousal * 2.5;

	// Mouth state priority: speaking (TTS-driven open/close cycle) > affect > default.
	$: mouthState =
		conversationState === 'speaking'
			? mouthOpenPhase
				? 'speaking'
				: 'neutral'
			: affect.reward > 0.55
				? 'smile'
				: affect.conflict > 0.6
					? 'frown'
					: 'neutral';

	// Head tilt priority: thinking/listening posture > idle look-around drift.
	$: headTilt =
		conversationState === 'thinking' ? -4 : conversationState === 'listening' ? 1 : idleHeadTilt;

	// Ambient color from warmth
	$: faceColor = `hsl(${30 + warmth * 20}, ${10 + warmth * 15}%, ${65 + warmth * 10}%)`;
	$: eyeColor = `hsl(${200 - warmth * 30}, ${20 + warmth * 10}%, ${75}%)`;

	// Wake/sleep presence dims the whole face (Task 6).
	$: presenceOpacity = presence === 'sleeping' ? 0.35 : presence === 'resting' ? 0.7 : 1;
</script>

<div
	class="face-container"
	class:cursor-hidden={cursorHidden}
	on:mousemove={onMouseMove}
	on:touchstart={registerInteraction}
	role="presentation"
>
	<!-- Greg's face -->
	<svg
		viewBox="0 0 400 500"
		class="face-svg"
		style="transform: scale({breatheScale}) rotate({headTilt}deg); opacity: {presenceOpacity}"
	>
		<!-- Head outline -->
		<ellipse cx="200" cy="220" rx="120" ry="150" fill="none" stroke={faceColor} stroke-width="1.5" opacity="0.4" />

		<!-- Left eye -->
		<ellipse
			cx={160 + eyeOffsetX}
			cy={200 + eyeOffsetY}
			rx="12"
			ry={eyeRy}
			fill={eyeColor}
			opacity="0.8"
			style="transition: cx 0.4s ease, cy 0.4s ease, ry 0.1s ease"
		/>
		{#if eyeState !== 'blinking'}
			<circle cx={160 + eyeOffsetX} cy={200 + eyeOffsetY} r={pupilR} fill="#141414" opacity="0.55" />
		{/if}

		<!-- Right eye -->
		<ellipse
			cx={240 + eyeOffsetX}
			cy={200 + eyeOffsetY}
			rx="12"
			ry={eyeRy}
			fill={eyeColor}
			opacity="0.8"
			style="transition: cx 0.4s ease, cy 0.4s ease, ry 0.1s ease"
		/>
		{#if eyeState !== 'blinking'}
			<circle cx={240 + eyeOffsetX} cy={200 + eyeOffsetY} r={pupilR} fill="#141414" opacity="0.55" />
		{/if}

		<!-- Nose (subtle line) -->
		<line x1="200" y1="230" x2="200" y2="255" stroke={faceColor} stroke-width="1" opacity="0.2" />

		<!-- Mouth -->
		{#if mouthState === 'speaking'}
			<ellipse
				cx="200"
				cy="285"
				rx="15"
				ry={mouthOpenPhase ? 8 : 3}
				fill="none"
				stroke={faceColor}
				stroke-width="1.2"
				opacity="0.5"
				style="transition: ry 0.12s ease"
			/>
		{:else if mouthState === 'smile'}
			<path d="M 175 280 Q 200 300 225 280" fill="none" stroke={faceColor} stroke-width="1.2" opacity="0.5" />
		{:else if mouthState === 'frown'}
			<path d="M 175 290 Q 200 275 225 290" fill="none" stroke={faceColor} stroke-width="1.2" opacity="0.5" />
		{:else}
			<line x1="180" y1="285" x2="220" y2="285" stroke={faceColor} stroke-width="1.2" opacity="0.3" />
		{/if}

		<!-- Breathing dot (chest area) -->
		<circle cx="200" cy="400" r="4" fill="#6b8f71" opacity="0.6">
			<animate attributeName="opacity" values="0.3;0.8;0.3" dur="4s" repeatCount="indefinite" />
			<animate attributeName="r" values="3;5;3" dur="4s" repeatCount="indefinite" />
		</circle>
	</svg>

	<!-- Response text area -->
	{#if responseText}
		<div class="response-area">
			<p class="response-text">{responseText}</p>
		</div>
	{/if}

	<!-- Conversation state indicator -->
	<div class="state-indicator">
		{#if conversationState === 'listening'}
			<span class="state-dot listening"></span>
		{:else if conversationState === 'thinking'}
			<span class="state-dot thinking"></span>
		{:else if conversationState === 'speaking'}
			<span class="state-dot speaking"></span>
		{/if}
	</div>

	<!-- Minimal kiosk input, driving the conversation state machine -->
	<form class="kiosk-input" on:submit|preventDefault={sendMessage}>
		<input
			type="text"
			placeholder="Talk to Greg…"
			bind:value={userInput}
			on:input={onUserTyping}
			on:keydown={onInputKeydown}
			on:focus={registerInteraction}
			disabled={conversationState === 'thinking' || conversationState === 'speaking'}
		/>
	</form>

	<!-- Hidden audio element for Chatterbox TTS playback -->
	<audio bind:this={audioEl} style="display:none"></audio>

	{#if !audioUnlocked}
		<button class="tap-overlay" on:click={unlockAudio} aria-label="Tap to activate Greg's voice">
			<span>Tap to activate</span>
		</button>
	{/if}
</div>

<style>
	.face-container {
		width: 100%;
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		background: #000;
		position: relative;
	}

	.face-container.cursor-hidden {
		cursor: none;
	}

	.face-svg {
		width: 300px;
		height: 375px;
		transition:
			transform 0.3s ease,
			opacity 2s ease;
	}

	.response-area {
		position: absolute;
		bottom: 15vh;
		left: 50%;
		transform: translateX(-50%);
		max-width: 600px;
		text-align: center;
		pointer-events: none;
	}

	.response-text {
		color: #8a857f;
		font-size: 1.2rem;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
		font-weight: 300;
		line-height: 1.6;
		letter-spacing: 0.01em;
	}

	.state-indicator {
		position: absolute;
		bottom: 40px;
		display: flex;
		gap: 8px;
	}

	.state-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}

	.state-dot.listening {
		background: #6b8f71;
		animation: pulse 1s ease infinite;
	}

	.state-dot.thinking {
		background: #8f8b6b;
		animation: pulse 0.5s ease infinite;
	}

	.state-dot.speaking {
		background: #6b7e8f;
		animation: pulse 0.8s ease infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 0.4;
		}
		50% {
			opacity: 1;
		}
	}

	.kiosk-input {
		position: absolute;
		bottom: 12px;
		left: 50%;
		transform: translateX(-50%);
		width: min(90vw, 420px);
	}

	.kiosk-input input {
		width: 100%;
		background: transparent;
		border: none;
		border-bottom: 1px solid rgba(138, 133, 127, 0.25);
		color: #8a857f;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
		font-size: 0.9rem;
		font-weight: 300;
		text-align: center;
		padding: 6px 4px;
		opacity: 0.35;
		transition:
			opacity 0.3s ease,
			border-color 0.3s ease;
	}

	.kiosk-input input:focus {
		outline: none;
		opacity: 0.9;
		border-color: rgba(138, 133, 127, 0.6);
	}

	.kiosk-input input::placeholder {
		color: #5a5650;
	}

	.tap-overlay {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		background: transparent;
		border: none;
		cursor: pointer;
		display: flex;
		align-items: flex-end;
		justify-content: center;
		padding-bottom: 20vh;
	}

	.tap-overlay span {
		color: #5a5650;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
		font-size: 0.8rem;
		font-weight: 300;
		letter-spacing: 0.05em;
		opacity: 0.6;
		animation: pulse 2.5s ease infinite;
	}
</style>
