<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	// --- Face state ---
	let eyeState: 'open' | 'blinking' | 'squint' | 'wide' = 'open';
	let mouthState: 'neutral' | 'speaking' | 'smile' = 'neutral';
	let headTilt = 0; // degrees, -5 to 5
	let breatheScale = 1;
	let conversationState: 'idle' | 'listening' | 'thinking' | 'speaking' = 'idle';

	let responseText = '';
	let cursorHidden = false;
	let cursorTimeout: ReturnType<typeof setTimeout>;
	let blinkInterval: ReturnType<typeof setInterval>;
	let breatheInterval: ReturnType<typeof setInterval>;

	// --- Time-of-day warmth ---
	let warmth = 0.5;
	function updateWarmth() {
		const hour = new Date().getHours();
		if (hour >= 6 && hour < 10) warmth = 0.7;      // morning amber
		else if (hour >= 10 && hour < 16) warmth = 0.5; // midday neutral
		else if (hour >= 16 && hour < 20) warmth = 0.6; // evening warm
		else warmth = 0.3;                               // night cool
	}

	// --- Blink ---
	function blink() {
		eyeState = 'blinking';
		setTimeout(() => { eyeState = 'open'; }, 150);
	}

	function startBlinking() {
		blinkInterval = setInterval(() => {
			const delay = 3000 + Math.random() * 4000; // 3-7s random
			setTimeout(blink, delay);
		}, 7000);
	}

	// --- Breathe ---
	function startBreathing() {
		let phase = 0;
		breatheInterval = setInterval(() => {
			phase += 0.05;
			breatheScale = 1 + Math.sin(phase) * 0.008; // subtle
		}, 66); // ~15fps
	}

	// --- Cursor auto-hide ---
	function onMouseMove() {
		cursorHidden = false;
		clearTimeout(cursorTimeout);
		cursorTimeout = setTimeout(() => { cursorHidden = true; }, 3000);
	}

	// --- Lifecycle ---
	onMount(() => {
		updateWarmth();
		startBlinking();
		startBreathing();
		blink(); // initial blink
	});

	onDestroy(() => {
		clearInterval(blinkInterval);
		clearInterval(breatheInterval);
		clearTimeout(cursorTimeout);
	});

	// Eye geometry based on state
	$: eyeHeight = eyeState === 'blinking' ? 2
		: eyeState === 'wide' ? 22
		: eyeState === 'squint' ? 10
		: 16;

	$: eyeRy = eyeHeight / 2;

	// Ambient color from warmth
	$: faceColor = `hsl(${30 + warmth * 20}, ${10 + warmth * 15}%, ${65 + warmth * 10}%)`;
	$: eyeColor = `hsl(${200 - warmth * 30}, ${20 + warmth * 10}%, ${75}%)`;
</script>

<div
	class="face-container"
	class:cursor-hidden={cursorHidden}
	on:mousemove={onMouseMove}
	role="presentation"
>
	<!-- Greg's face -->
	<svg
		viewBox="0 0 400 500"
		class="face-svg"
		style="transform: scale({breatheScale}) rotate({headTilt}deg)"
	>
		<!-- Head outline -->
		<ellipse
			cx="200" cy="220"
			rx="120" ry="150"
			fill="none"
			stroke={faceColor}
			stroke-width="1.5"
			opacity="0.4"
		/>

		<!-- Left eye -->
		<ellipse
			cx="160" cy="200"
			rx="12" ry={eyeRy}
			fill={eyeColor}
			opacity="0.8"
			style="transition: ry 0.1s ease"
		/>

		<!-- Right eye -->
		<ellipse
			cx="240" cy="200"
			rx="12" ry={eyeRy}
			fill={eyeColor}
			opacity="0.8"
			style="transition: ry 0.1s ease"
		/>

		<!-- Nose (subtle line) -->
		<line
			x1="200" y1="230" x2="200" y2="255"
			stroke={faceColor}
			stroke-width="1"
			opacity="0.2"
		/>

		<!-- Mouth -->
		{#if mouthState === 'speaking'}
			<ellipse
				cx="200" cy="285"
				rx="15" ry="8"
				fill="none"
				stroke={faceColor}
				stroke-width="1.2"
				opacity="0.5"
			/>
		{:else if mouthState === 'smile'}
			<path
				d="M 175 280 Q 200 300 225 280"
				fill="none"
				stroke={faceColor}
				stroke-width="1.2"
				opacity="0.5"
			/>
		{:else}
			<line
				x1="180" y1="285" x2="220" y2="285"
				stroke={faceColor}
				stroke-width="1.2"
				opacity="0.3"
			/>
		{/if}

		<!-- Breathing dot (chest area) -->
		<circle
			cx="200" cy="400"
			r="4"
			fill="#6b8f71"
			opacity="0.6"
		>
			<animate
				attributeName="opacity"
				values="0.3;0.8;0.3"
				dur="4s"
				repeatCount="indefinite"
			/>
			<animate
				attributeName="r"
				values="3;5;3"
				dur="4s"
				repeatCount="indefinite"
			/>
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
		transition: transform 0.3s ease;
	}

	.response-area {
		position: absolute;
		bottom: 80px;
		left: 50%;
		transform: translateX(-50%);
		max-width: 600px;
		text-align: center;
	}

	.response-text {
		color: #8a857f;
		font-size: 1rem;
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
		0%, 100% { opacity: 0.4; }
		50% { opacity: 1; }
	}
</style>
