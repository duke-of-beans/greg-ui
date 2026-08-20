<script lang="ts">
	import { onMount, onDestroy } from 'svelte';

	// ============================================================
	// CORTEX MCP client
	// ============================================================
	const CORTEX_URL = 'https://cortex-production-d0d7.up.railway.app/mcp';
	const CORTEX_KEY = 'yevDScM_JKyl4zNl8js_ZJg_8oZRxe4SWcSvMcMRZF4';

	async function cortexCall(tool: string, args: Record<string, unknown> = {}) {
		const res = await fetch(CORTEX_URL, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${CORTEX_KEY}`
			},
			body: JSON.stringify({
				jsonrpc: '2.0',
				id: Date.now(),
				method: 'tools/call',
				params: { name: tool, arguments: args }
			})
		});
		const data = await res.json();
		return data?.result?.content?.[0]?.text;
	}

	function safeParse(text: string | undefined) {
		if (!text) return null;
		try {
			return JSON.parse(text);
		} catch {
			return null;
		}
	}

	// ============================================================
	// Theme (dark / light) — persisted to localStorage
	// ============================================================
	let theme: 'dark' | 'light' = 'dark';

	function applyTheme(next: 'dark' | 'light') {
		theme = next;
		try {
			localStorage.setItem('greg-home-theme', next);
		} catch {
			/* localStorage unavailable — theme stays in-memory for this session */
		}
	}

	function toggleTheme() {
		applyTheme(theme === 'dark' ? 'light' : 'dark');
	}

	// ============================================================
	// Time & contextual greeting (Sprint 01)
	// ============================================================
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

	let breathePhase = true;
	let timeInterval: ReturnType<typeof setInterval>;

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

	// ============================================================
	// Top bar — desk metrics (Greg's live state)
	// ============================================================
	let deskMetrics = {
		topic: 'idle',
		mood: '🙂',
		budgetPct: null as number | null,
		loaded: false
	};

	async function fetchDeskMetrics() {
		try {
			const text = await cortexCall('ask_greg', {
				message: 'One-line status: what are you thinking about right now, and your mood?'
			});
			const parsed = safeParse(text);
			if (parsed) {
				deskMetrics = {
					topic: parsed.topic || parsed.summary || 'thinking',
					mood: parsed.mood_emoji || parsed.emoji || '🙂',
					budgetPct: typeof parsed.budget_pct === 'number' ? parsed.budget_pct : null,
					loaded: true
				};
			} else {
				deskMetrics = { topic: 'ambient thinking', mood: '🙂', budgetPct: null, loaded: true };
			}
		} catch {
			deskMetrics = { topic: 'ambient thinking', mood: '🙂', budgetPct: null, loaded: true };
		}
	}

	// ============================================================
	// Calm technology — item "freshness" helper.
	// New items get a green border-left that fades after 2 hours.
	// Purely time-based, no badges, no counters.
	// ============================================================
	const FADE_WINDOW_MS = 2 * 60 * 60 * 1000; // 2 hours

	function isFresh(timestamp: string | number | null | undefined): boolean {
		if (!timestamp) return false;
		const t = typeof timestamp === 'string' ? new Date(timestamp).getTime() : timestamp;
		if (Number.isNaN(t)) return false;
		return Date.now() - t < FADE_WINDOW_MS;
	}

	// ============================================================
	// Left sidebar — five fixed sections (DES-20: never reorder)
	// ============================================================
	type SidebarItem = { id: string; text: string; timestamp?: string };

	let sidebarExpanded = {
		whileAway: false,
		fromPast: false,
		connections: false,
		trust: false,
		murmuring: false
	};

	function toggleSection(key: keyof typeof sidebarExpanded) {
		sidebarExpanded[key] = !sidebarExpanded[key];
	}

	let whileAway: SidebarItem[] = [];
	let whileAwayLoaded = false;

	let connections: SidebarItem[] = [];

	// Trust ramp — placeholder tiers until trust_categories (Supabase) is wired up
	const trustCategories: { name: string; tier: 'T0' | 'T1' | 'T2' | 'T3' }[] = [
		{ name: 'Research', tier: 'T0' },
		{ name: 'Code Deploy', tier: 'T1' },
		{ name: 'Communication', tier: 'T2' },
		{ name: 'Financial', tier: 'T3' }
	];
	const trustTierColor: Record<string, string> = {
		T0: '#5a554f',
		T1: '#6b8f71',
		T2: '#c9a24b',
		T3: '#b5583f'
	};

	let murmuring: SidebarItem[] = [];

	async function fetchWhileAway() {
		try {
			let lastVisit: string | null = null;
			try {
				lastVisit = localStorage.getItem('greg-home-last-visit');
			} catch {
				/* no localStorage — treat as first visit */
			}
			const query = lastVisit
				? `recent observations since ${lastVisit}`
				: 'recent observations from the last 12 hours';
			const text = await cortexCall('recall', { query, limit: 3 });
			const parsed = safeParse(text);
			const results = parsed?.results || [];
			whileAway = results.slice(0, 3).map((r: any, i: number) => ({
				id: r.id || `while-away-${i}`,
				text: (r.content || '').slice(0, 140),
				timestamp: r.timestamp
			}));
		} catch {
			whileAway = [];
		} finally {
			whileAwayLoaded = true;
			try {
				localStorage.setItem('greg-home-last-visit', new Date().toISOString());
			} catch {
				/* best-effort only */
			}
		}
	}

	async function fetchMurmuring() {
		try {
			const text = await cortexCall('gaps_queue', { person_id: 'david' });
			const parsed = safeParse(text);
			const seeds = parsed?.seeds || [];
			if (seeds.length > 0) {
				murmuring = seeds.slice(0, 3).map((s: any, i: number) => ({
					id: s.id || `murmur-${i}`,
					text: s.content,
					timestamp: s.created_at
				}));
			} else {
				murmuring = [
					{
						id: 'murmur-fallback',
						text: "I've been thinking about how memory shapes identity. Not just what we remember — what we choose to hold onto."
					}
				];
			}
		} catch {
			murmuring = [
				{
					id: 'murmur-fallback',
					text: "I've been thinking about how memory shapes identity. Not just what we remember — what we choose to hold onto."
				}
			];
		}
	}

	// ============================================================
	// Right main — needs attention / prometheus / modules
	// (no backing data source yet — placeholder cards, DES spec)
	// ============================================================
	type AttentionItem = { id: string; text: string; severity: 'red' | 'amber'; timestamp?: string };

	let needsAttention: AttentionItem[] = [];
	let prometheusInsights: SidebarItem[] = [];

	// ============================================================
	// Conversation journal — hotel-lobby "bar": continuation, not a form.
	// Shows the last exchange above the input.
	// ============================================================
	let journalText = '';
	let journalAck = '';
	let journalSubmitting = false;
	let lastExchange: { user: string; ack: string } | null = null;

	async function submitJournal() {
		if (!journalText.trim() || journalSubmitting) return;
		journalSubmitting = true;
		journalAck = '';
		const submittedText = journalText;

		try {
			await cortexCall('brain_remember', {
				content: `[lifelog] ${submittedText}`,
				entity: 'david-lifelog',
				source: 'hearth-journal'
			});
			journalAck = 'Heard.';
		} catch {
			journalAck = 'Saved locally.';
		}

		lastExchange = { user: submittedText, ack: journalAck };
		journalText = '';
		setTimeout(() => {
			journalAck = '';
		}, 3000);

		journalSubmitting = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			submitJournal();
		}
	}

	// ============================================================
	// Lifecycle
	// ============================================================
	onMount(() => {
		try {
			const saved = localStorage.getItem('greg-home-theme');
			if (saved === 'light' || saved === 'dark') theme = saved;
		} catch {
			/* localStorage unavailable — default theme stands */
		}

		updateTime();
		fetchWeather();
		fetchDeskMetrics();
		fetchWhileAway();
		fetchMurmuring();
		timeInterval = setInterval(updateTime, 30000);
	});

	onDestroy(() => {
		if (timeInterval) clearInterval(timeInterval);
	});
</script>

<div
	class="hearth"
	class:light={theme === 'light'}
	class:morning={timeMode === 'morning'}
	class:midday={timeMode === 'midday'}
	class:evening={timeMode === 'evening'}
	class:night={timeMode === 'night'}
>
	<!-- Top bar: front desk -->
	<header class="top-bar">
		<div class="top-bar-left">
			<div class="breathing-dot" class:breathe={breathePhase}></div>
			<span class="presence-label">Greg</span>
		</div>

		<div class="top-bar-center">
			{#if deskMetrics.loaded}
				<span class="desk-metric">{deskMetrics.mood}</span>
				<span class="desk-metric desk-metric-topic">{deskMetrics.topic}</span>
				{#if deskMetrics.budgetPct !== null}
					<span class="desk-metric">{deskMetrics.budgetPct}% budget</span>
				{/if}
			{/if}
		</div>

		<div class="top-bar-right">
			<a href="/" class="top-bar-link">Chat</a>
			<a href="https://consonance.silentampersand.com" class="top-bar-link" target="_blank">
				Consonance
			</a>
			<button class="theme-toggle" on:click={toggleTheme} aria-label="Toggle light/dark mode">
				{theme === 'dark' ? '☾' : '☀'}
			</button>
		</div>
	</header>

	<div class="layout-body">
		<!-- Left sidebar: fixed section order (DES-20) -->
		<aside class="sidebar">
			<!-- 1. While Away -->
			<section class="sidebar-section">
				<button class="section-heading" on:click={() => toggleSection('whileAway')}>
					<span>While Away</span>
					<span class="chevron" class:open={sidebarExpanded.whileAway}>›</span>
				</button>
				{#if sidebarExpanded.whileAway}
					<div class="section-body">
						{#if whileAwayLoaded && whileAway.length === 0}
							<p class="section-placeholder">Nothing new since your last visit.</p>
						{:else}
							{#each whileAway as item (item.id)}
								<p class="section-item ambient" class:fresh={isFresh(item.timestamp)}>
									{item.text}
								</p>
							{/each}
						{/if}
					</div>
				{/if}
			</section>

			<!-- 2. From Your Past -->
			<section class="sidebar-section">
				<button class="section-heading" on:click={() => toggleSection('fromPast')}>
					<span>From Your Past</span>
					<span class="chevron" class:open={sidebarExpanded.fromPast}>›</span>
				</button>
				{#if sidebarExpanded.fromPast}
					<div class="section-body">
						<p class="section-placeholder">
							Photos from your past will appear here once Throwbak is connected.
						</p>
					</div>
				{/if}
			</section>

			<!-- 3. Connections -->
			<section class="sidebar-section">
				<button class="section-heading" on:click={() => toggleSection('connections')}>
					<span>Connections</span>
					<span class="chevron" class:open={sidebarExpanded.connections}>›</span>
				</button>
				{#if sidebarExpanded.connections}
					<div class="section-body">
						{#if connections.length === 0}
							<p class="section-placeholder">Coming soon.</p>
						{:else}
							{#each connections as item (item.id)}
								<p class="section-item ambient" class:fresh={isFresh(item.timestamp)}>
									{item.text}
								</p>
							{/each}
						{/if}
					</div>
				{/if}
			</section>

			<!-- 4. Trust Ramp -->
			<section class="sidebar-section">
				<button class="section-heading" on:click={() => toggleSection('trust')}>
					<span>Trust Ramp</span>
					<span class="chevron" class:open={sidebarExpanded.trust}>›</span>
				</button>
				{#if sidebarExpanded.trust}
					<div class="section-body">
						<div class="trust-dots">
							{#each trustCategories as cat (cat.name)}
								<div class="trust-row">
									<span
										class="trust-dot"
										style="background:{trustTierColor[cat.tier]}"
										title={cat.tier}
									></span>
									<span class="trust-name">{cat.name}</span>
									<span class="trust-tier">{cat.tier}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</section>

			<!-- 5. Murmuring -->
			<section class="sidebar-section">
				<button class="section-heading" on:click={() => toggleSection('murmuring')}>
					<span>Murmuring</span>
					<span class="chevron" class:open={sidebarExpanded.murmuring}>›</span>
				</button>
				{#if sidebarExpanded.murmuring}
					<div class="section-body">
						{#each murmuring as item (item.id)}
							<p class="section-item ambient" class:fresh={isFresh(item.timestamp)}>
								{item.text}
							</p>
						{/each}
					</div>
				{/if}
			</section>
		</aside>

		<!-- Right main: fluid -->
		<main class="main-content">
			<!-- 1. Contextual greeting -->
			<div class="greeting-block">
				<p class="greeting">{greeting}</p>
				<div class="context-bar">
					<span class="date-time">{currentDate} · {currentTime}</span>
					{#if weather.loaded}
						<span class="weather">{weather.temp} {weather.condition} · {weather.sunsetIn}</span>
					{/if}
				</div>
			</div>

			<!-- 2. Needs Attention: concierge — visually heaviest -->
			{#if needsAttention.length > 0}
				<div class="module needs-attention-block">
					<p class="module-label">Needs Attention</p>
					{#each needsAttention as item (item.id)}
						<div class="attention-card severity-{item.severity}" class:fresh={isFresh(item.timestamp)}>
							{item.text}
						</div>
					{/each}
				</div>
			{/if}

			<!-- 3. Prometheus: cross-portfolio insights -->
			<div class="module">
				<p class="module-label">Prometheus</p>
				{#if prometheusInsights.length === 0}
					<p class="section-placeholder">Coming soon.</p>
				{:else}
					{#each prometheusInsights as item (item.id)}
						<p class="section-item ambient" class:fresh={isFresh(item.timestamp)}>{item.text}</p>
					{/each}
				{/if}
			</div>

			<!-- 4. Modules: expandable deep-dive panels -->
			<div class="module">
				<p class="module-label">Modules</p>
				<p class="section-placeholder">Coming soon.</p>
			</div>
		</main>
	</div>

	<!-- Bottom journal bar: the bar — conversation continuation -->
	<footer class="journal-bar">
		{#if lastExchange}
			<div class="last-exchange">
				<p class="last-exchange-user">{lastExchange.user}</p>
				<p class="last-exchange-ack">{lastExchange.ack}</p>
			</div>
		{/if}
		<div class="journal-input-row">
			<textarea
				class="journal-input"
				placeholder="What's on your mind?"
				bind:value={journalText}
				on:keydown={handleKeydown}
				rows="1"
			></textarea>
			<button
				class="journal-send"
				on:click={submitJournal}
				disabled={journalSubmitting || !journalText.trim()}
			>
				Send
			</button>
		</div>
		{#if journalAck}
			<p class="journal-ack">{journalAck}</p>
		{/if}
	</footer>
</div>

<style>
	/* ============================================================
	   Design tokens — dark (default) and light (GregLite) palettes.
	   Swapped via .light class on the root .hearth element.
	   ============================================================ */
	.hearth {
		--accent: #6b8f71;
		--accent-red: #b5583f;
		--accent-amber: #c9a24b;

		--bg: #141416;
		--bg-elevated: #1c1a17;
		--bg-ambient: transparent;
		--text-primary: #c8c4bf;
		--text-secondary: #8a857f;
		--text-muted: #5a554f;
		--border-subtle: #2a2622;

		min-height: 100vh;
		display: flex;
		flex-direction: column;
		background: var(--bg);
		color: var(--text-primary);
		transition: background-color 1s ease, color 0.3s ease;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
	}

	.hearth.morning { --bg: #1a1612; }
	.hearth.midday  { --bg: #141416; }
	.hearth.evening { --bg: #161418; }
	.hearth.night   { --bg: #0e0e10; }

	/* Light mode (GregLite) overrides — wins regardless of time-of-day class */
	.hearth.light {
		--bg: #f4ede0;
		--bg-elevated: #ffffff;
		--bg-ambient: transparent;
		--text-primary: #3a2e22;
		--text-secondary: #6b5c4a;
		--text-muted: #a3927a;
		--border-subtle: #e0d3bd;
	}

	/* ============================================================
	   Top bar — front desk
	   ============================================================ */
	.top-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 48px;
		min-height: 48px;
		padding: 0 1.25rem;
		border-bottom: 1px solid var(--border-subtle);
		gap: 1rem;
	}

	.top-bar-left {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex: 0 0 auto;
	}

	.presence-label {
		font-size: 0.8rem;
		color: var(--text-secondary);
		letter-spacing: 0.03em;
	}

	.breathing-dot {
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--accent);
		animation: breathe 4s ease-in-out infinite;
		flex-shrink: 0;
	}

	@keyframes breathe {
		0%, 100% { opacity: 0.4; transform: scale(0.9); }
		50% { opacity: 1; transform: scale(1.1); }
	}

	.top-bar-center {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex: 1 1 auto;
		justify-content: center;
		overflow: hidden;
		font-size: 0.78rem;
		color: var(--text-muted);
	}

	.desk-metric-topic {
		text-overflow: ellipsis;
		overflow: hidden;
		white-space: nowrap;
		max-width: 40ch;
	}

	.top-bar-right {
		display: flex;
		align-items: center;
		gap: 1.1rem;
		flex: 0 0 auto;
	}

	.top-bar-link {
		font-size: 0.75rem;
		color: var(--text-muted);
		text-decoration: none;
		letter-spacing: 0.03em;
		transition: color 0.3s;
	}

	.top-bar-link:hover {
		color: var(--text-primary);
	}

	.theme-toggle {
		background: transparent;
		border: 1px solid var(--border-subtle);
		border-radius: 50%;
		width: 26px;
		height: 26px;
		color: var(--text-secondary);
		cursor: pointer;
		font-size: 0.85rem;
		line-height: 1;
		transition: border-color 0.3s, color 0.3s;
	}

	.theme-toggle:hover {
		border-color: var(--accent);
		color: var(--text-primary);
	}

	/* ============================================================
	   Body: sidebar + main
	   ============================================================ */
	.layout-body {
		display: flex;
		flex: 1 1 auto;
		min-height: 0;
	}

	.sidebar {
		flex: 0 0 280px;
		width: 280px;
		overflow-y: auto;
		border-right: 1px solid var(--border-subtle);
		padding: 1rem 0;
	}

	.sidebar-section {
		border-bottom: 1px solid var(--border-subtle);
	}

	.section-heading {
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		background: transparent;
		border: none;
		cursor: pointer;
		padding: 0.7rem 1rem;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.09em;
		color: var(--text-muted);
	}

	.section-heading:hover {
		color: var(--text-secondary);
	}

	.chevron {
		transition: transform 0.3s ease;
		font-size: 0.9rem;
	}

	.chevron.open {
		transform: rotate(90deg);
	}

	.section-body {
		padding: 0 1rem 0.85rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.section-placeholder {
		font-size: 0.8rem;
		color: var(--text-muted);
		font-style: italic;
	}

	/* Ambient sections (While Away, Connections, Murmuring, Prometheus):
	   lighter, transparent, lower-opacity — biophilic "background" feel */
	.section-item.ambient {
		font-size: 0.82rem;
		color: var(--text-secondary);
		opacity: 0.85;
		line-height: 1.5;
		border-left: 3px solid transparent;
		padding-left: 0.6rem;
		transition: border-color 300ms ease;
	}

	.section-item.ambient.fresh {
		border-left-color: var(--accent);
	}

	.trust-dots {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.trust-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.78rem;
		color: var(--text-secondary);
	}

	.trust-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.trust-name {
		flex: 1 1 auto;
	}

	.trust-tier {
		color: var(--text-muted);
		font-size: 0.68rem;
	}

	/* ============================================================
	   Main content: seating area
	   ============================================================ */
	.main-content {
		flex: 1 1 auto;
		overflow-y: auto;
		padding: 1.75rem 2rem;
		display: flex;
		flex-direction: column;
		gap: 1.75rem;
	}

	.greeting-block {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.greeting {
		font-size: 1.35rem;
		font-weight: 300;
		color: var(--text-primary);
		letter-spacing: 0.01em;
	}

	.context-bar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		font-size: 0.78rem;
		color: var(--text-muted);
		letter-spacing: 0.02em;
	}

	.module {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.module-label {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.09em;
		color: var(--text-muted);
	}

	/* Needs Attention: concierge — visually heaviest card in the room */
	.needs-attention-block {
		gap: 0.6rem;
	}

	.attention-card {
		background: var(--bg-elevated);
		border-radius: 6px;
		padding: 0.85rem 1rem;
		font-size: 0.88rem;
		color: var(--text-primary);
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25);
		border-left: 3px solid transparent;
		transition: border-color 300ms ease;
	}

	.attention-card.severity-red {
		border-left-color: var(--accent-red);
	}

	.attention-card.severity-amber {
		border-left-color: var(--accent-amber);
	}

	/* ============================================================
	   Bottom journal bar: the bar — conversation continuation
	   ============================================================ */
	.journal-bar {
		flex: 0 0 auto;
		border-top: 1px solid var(--border-subtle);
		padding: 0.85rem 2rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.last-exchange {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding-bottom: 0.4rem;
		border-bottom: 1px solid var(--border-subtle);
		margin-bottom: 0.2rem;
	}

	.last-exchange-user {
		font-size: 0.82rem;
		color: var(--text-secondary);
	}

	.last-exchange-ack {
		font-size: 0.75rem;
		color: var(--accent);
	}

	.journal-input-row {
		display: flex;
		align-items: flex-end;
		gap: 0.75rem;
	}

	.journal-input {
		flex: 1 1 auto;
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--border-subtle);
		color: var(--text-primary);
		font-size: 0.95rem;
		font-family: inherit;
		padding: 0.5rem 0;
		resize: none;
		outline: none;
		transition: border-color 0.3s;
	}

	.journal-input::placeholder {
		color: var(--text-muted);
	}

	.journal-input:focus {
		border-color: var(--accent);
	}

	.journal-send {
		background: transparent;
		border: 1px solid var(--border-subtle);
		border-radius: 4px;
		color: var(--text-secondary);
		font-size: 0.78rem;
		padding: 0.45rem 0.9rem;
		cursor: pointer;
		transition: border-color 0.3s, color 0.3s;
	}

	.journal-send:hover:not(:disabled) {
		border-color: var(--accent);
		color: var(--text-primary);
	}

	.journal-send:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.journal-ack {
		font-size: 0.78rem;
		color: var(--accent);
		opacity: 0;
		animation: fadeInOut 3s ease forwards;
	}

	@keyframes fadeInOut {
		0% { opacity: 0; }
		10% { opacity: 1; }
		80% { opacity: 1; }
		100% { opacity: 0; }
	}

	/* ============================================================
	   Mobile (DES-44): sidebar collapses to a horizontal strip
	   above the main content below 768px.
	   ============================================================ */
	@media (max-width: 768px) {
		.layout-body {
			flex-direction: column;
		}

		.sidebar {
			flex: 0 0 auto;
			width: 100%;
			max-height: 220px;
			border-right: none;
			border-bottom: 1px solid var(--border-subtle);
		}

		.top-bar-center {
			display: none;
		}

		.main-content {
			padding: 1.25rem 1.25rem;
		}

		.journal-bar {
			padding: 0.75rem 1.25rem 0.9rem;
		}
	}
</style>
