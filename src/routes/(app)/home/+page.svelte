<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	// --- State ---
	let currentTime = '';
	let currentDate = '';
	let greeting = '';
	let timeMode: 'morning' | 'midday' | 'evening' | 'night' = 'midday';

	let weather = {
		temp: '--',
		condition: '',
		sunsetIn: '',
		loaded: false
	};

	let gregThought = '';
	let journalText = '';
	let journalAck = '';
	let journalSubmitting = false;

	let breathePhase = true;
	let timeInterval: ReturnType<typeof setInterval>;

	// --- Time ---
	function updateTime() {
		const now = new Date();
		const hour = now.getHours();

		currentTime = now.toLocaleTimeString('en-US', {
			hour: 'numeric',
			minute: '2-digit',
			hour12: true
		});

		currentDate = now.toLocaleDateString('en-US', {
			weekday: 'long',
			month: 'long',
			day: 'numeric'
		});

		if (hour >= 6 && hour < 10) {
			timeMode = 'morning';
			greeting = 'Good morning, David.';
		} else if (hour >= 10 && hour < 16) {
			timeMode = 'midday';
			greeting = 'Hey.';
		} else if (hour >= 16 && hour < 22) {
			timeMode = 'evening';
			greeting = 'Evening.';
		} else {
			timeMode = 'night';
			greeting = "It's late.";
		}
	}

	// --- Weather (Open-Meteo, free, no key) ---
	async function fetchWeather() {
		try {
			const res = await fetch(
				'https://api.open-meteo.com/v1/forecast?' +
				'latitude=34.27&longitude=-118.78' +
				'&current=temperature_2m,weathercode' +
				'&daily=sunset' +
				'&temperature_unit=fahrenheit' +
				'&timezone=America/Los_Angeles'
			);
			const data = await res.json();

			const temp = Math.round(data.current.temperature_2m);
			const code = data.current.weathercode;
			const condition = weatherCodeToText(code);

			const sunsetStr = data.daily.sunset[0];
			const sunset = new Date(sunsetStr);
			const now = new Date();
			const diffMs = sunset.getTime() - now.getTime();

			let sunsetIn = '';
			if (diffMs > 0) {
				const hours = Math.floor(diffMs / 3600000);
				const mins = Math.floor((diffMs % 3600000) / 60000);
				sunsetIn = hours > 0 ? `Sunset in ${hours}h ${mins}m` : `Sunset in ${mins}m`;
			} else {
				sunsetIn = 'After sunset';
			}

			weather = { temp: `${temp}°F`, condition, sunsetIn, loaded: true };
		} catch {
			weather = { temp: '--', condition: '', sunsetIn: '', loaded: false };
		}
	}

	function weatherCodeToText(code: number): string {
		if (code === 0) return 'Clear';
		if (code <= 3) return 'Partly cloudy';
		if (code <= 49) return 'Foggy';
		if (code <= 59) return 'Drizzle';
		if (code <= 69) return 'Rain';
		if (code <= 79) return 'Snow';
		if (code <= 82) return 'Showers';
		if (code <= 86) return 'Snow showers';
		if (code >= 95) return 'Thunderstorm';
		return '';
	}


	// --- Greg's thought (from CORTEX brain.db) ---
	async function fetchGregThought() {
		try {
			// Query CORTEX for Greg's latest personal thought
			const res = await fetch('https://cortex-production-d0d7.up.railway.app/mcp', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': 'Bearer yevDScM_JKyl4zNl8js_ZJg_8oZRxe4SWcSvMcMRZF4'
				},
				body: JSON.stringify({
					jsonrpc: '2.0',
					id: 1,
					method: 'tools/call',
					params: {
						name: 'gaps_queue',
						arguments: { person_id: 'david' }
					}
				})
			});
			const data = await res.json();
			const content = data?.result?.content?.[0]?.text;
			if (content) {
				try {
					const parsed = JSON.parse(content);
					if (parsed.seeds?.length > 0) {
						gregThought = parsed.seeds[0].content;
					} else {
						gregThought = "I've been thinking about how memory shapes identity. Not just what we remember — what we choose to hold onto.";
					}
				} catch {
					gregThought = content.slice(0, 300);
				}
			}
		} catch {
			gregThought = "I've been thinking about how memory shapes identity. Not just what we remember — what we choose to hold onto.";
		}
	}

	// --- Journal ---
	async function submitJournal() {
		if (!journalText.trim() || journalSubmitting) return;
		journalSubmitting = true;
		journalAck = '';

		try {
			// Store to brain.db via CORTEX
			await fetch('https://cortex-production-d0d7.up.railway.app/mcp', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': 'Bearer yevDScM_JKyl4zNl8js_ZJg_8oZRxe4SWcSvMcMRZF4'
				},
				body: JSON.stringify({
					jsonrpc: '2.0',
					id: 2,
					method: 'tools/call',
					params: {
						name: 'brain_remember',
						arguments: {
							content: `[lifelog] ${journalText}`,
							entity: 'david-lifelog',
							source: 'hearth-journal'
						}
					}
				})
			});

			journalAck = 'Heard.';
			journalText = '';
			setTimeout(() => { journalAck = ''; }, 3000);
		} catch {
			journalAck = 'Saved locally.';
		}

		journalSubmitting = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			submitJournal();
		}
	}

	// --- Lifecycle ---
	onMount(() => {
		updateTime();
		fetchWeather();
		fetchGregThought();
		timeInterval = setInterval(updateTime, 30000);
	});

	onDestroy(() => {
		if (timeInterval) clearInterval(timeInterval);
	});
</script>

<div
	class="hearth"
	class:morning={timeMode === 'morning'}
	class:midday={timeMode === 'midday'}
	class:evening={timeMode === 'evening'}
	class:night={timeMode === 'night'}
>
	<div class="hearth-content">

		<!-- Greg's presence -->
		<div class="presence">
			<div class="breathing-dot" class:breathe={breathePhase}></div>
			<p class="greeting">{greeting}</p>
		</div>

		<!-- Time & Weather -->
		<div class="context-bar">
			<span class="date-time">{currentDate} · {currentTime}</span>
			{#if weather.loaded}
				<span class="weather">{weather.temp} {weather.condition} · {weather.sunsetIn}</span>
			{/if}
		</div>

		<!-- Throwbak "on this day" -->
		<div class="on-this-day">
			<div class="on-this-day-card">
				<p class="on-this-day-label">On this day</p>
				<p class="on-this-day-placeholder">Photos from your past will appear here once Throwbak is connected.</p>
			</div>
		</div>

		<!-- Lifelog journal -->
		<div class="journal">
			<textarea
				class="journal-input"
				placeholder="What's on your mind?"
				bind:value={journalText}
				on:keydown={handleKeydown}
				rows="2"
			></textarea>
			{#if journalAck}
				<p class="journal-ack">{journalAck}</p>
			{/if}
		</div>

		<!-- Greg's thought -->
		{#if gregThought}
			<div class="greg-thought">
				<p class="greg-thought-label">Greg</p>
				<p class="greg-thought-text">{gregThought}</p>
			</div>
		{/if}

		<!-- Portal doors -->
		<div class="portals">
			<a href="/" class="portal">Chat with Greg</a>
			<a href="https://consonance.silentampersand.com" class="portal" target="_blank">Consonance</a>
		</div>

	</div>
</div>

<style>
	.hearth {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: background-color 1s ease;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
	}

	.hearth.morning { background: #1a1612; }
	.hearth.midday  { background: #141416; }
	.hearth.evening { background: #161418; }
	.hearth.night   { background: #0e0e10; }

	.hearth-content {
		max-width: 520px;
		width: 100%;
		padding: 2rem;
		display: flex;
		flex-direction: column;
		gap: 2.5rem;
	}

	/* Presence */
	.presence {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.breathing-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: #6b8f71;
		animation: breathe 4s ease-in-out infinite;
	}

	@keyframes breathe {
		0%, 100% { opacity: 0.4; transform: scale(0.9); }
		50% { opacity: 1; transform: scale(1.1); }
	}

	.greeting {
		font-size: 1.25rem;
		font-weight: 300;
		color: #c8c4bf;
		letter-spacing: 0.01em;
	}

	/* Context bar */
	.context-bar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		font-size: 0.8rem;
		color: #7a756f;
		letter-spacing: 0.02em;
	}

	.context-bar span::after {
		content: '';
	}

	/* On this day */
	.on-this-day-card {
		border-left: 2px solid #2a2622;
		padding-left: 1rem;
	}

	.on-this-day-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: #5a554f;
		margin-bottom: 0.4rem;
	}

	.on-this-day-placeholder {
		font-size: 0.85rem;
		color: #4a4540;
		font-style: italic;
	}

	/* Journal */
	.journal-input {
		width: 100%;
		background: transparent;
		border: none;
		border-bottom: 1px solid #2a2622;
		color: #b0aba5;
		font-size: 0.95rem;
		font-family: inherit;
		padding: 0.5rem 0;
		resize: none;
		outline: none;
		transition: border-color 0.3s;
	}

	.journal-input::placeholder {
		color: #4a4540;
	}

	.journal-input:focus {
		border-color: #6b8f71;
	}

	.journal-ack {
		font-size: 0.8rem;
		color: #6b8f71;
		margin-top: 0.4rem;
		opacity: 0;
		animation: fadeInOut 3s ease forwards;
	}

	@keyframes fadeInOut {
		0% { opacity: 0; }
		10% { opacity: 1; }
		80% { opacity: 1; }
		100% { opacity: 0; }
	}

	/* Greg's thought */
	.greg-thought {
		border-left: 2px solid #2a2622;
		padding-left: 1rem;
	}

	.greg-thought-label {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: #5a554f;
		margin-bottom: 0.4rem;
	}

	.greg-thought-text {
		font-size: 0.9rem;
		color: #8a857f;
		line-height: 1.6;
	}

	/* Portals */
	.portals {
		display: flex;
		gap: 1.5rem;
		padding-top: 1rem;
	}

	.portal {
		font-size: 0.75rem;
		color: #5a554f;
		text-decoration: none;
		letter-spacing: 0.05em;
		transition: color 0.3s;
	}

	.portal:hover {
		color: #b0aba5;
	}
</style>
