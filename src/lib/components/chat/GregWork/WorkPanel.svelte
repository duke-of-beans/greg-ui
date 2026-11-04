<script lang="ts">
	/**
	 * Gregore's work panel for one chat (Gregore-private docs/GREGORE_WORK_PANEL_SPEC.md): what needs David on top,
	 * then work in flight as steps that tick off on evidence, then finished work, then the state key.
	 * Data: GET /api/v1/greg/work/chat; live: the order-event feed, which triggers a re-read (never a guess).
	 */
	import { onDestroy } from 'svelte';
	import WorkCard from './WorkCard.svelte';
	import { chatWorkEventsUrl, getChatWork, prLinkOf, type WorkCard as Card } from '$lib/apis/greg/work';

	export let chatId: string | null = null;
	/** Told how many cards are pressing and live, so the pane can open itself when the context calls for it. */
	export let onCounts: ((c: { pressing: number; live: number; total: number }) => void) | null = null;

	let cards: Card[] = [];
	let error: string | null = null;
	let loading = false;
	let now = Date.now();
	let source: EventSource | null = null;
	let loadedFor: string | null = null;
	let refetchTimer: ReturnType<typeof setTimeout> | null = null;

	const tick = setInterval(() => (now = Date.now()), 30_000);

	const load = async (id: string) => {
		loading = cards.length === 0;
		try {
			const r = await getChatWork(localStorage.token, id);
			if (id !== chatId) return; // the user moved to another chat meanwhile
			cards = r.cards;
			error = null;
			now = Date.now();
			onCounts?.({
				pressing: cards.filter((c) => c.pressing).length,
				live: cards.filter((c) => c.status !== 'done').length,
				total: cards.length
			});
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	};

	const listen = (id: string) => {
		source?.close();
		source = new EventSource(chatWorkEventsUrl(id), { withCredentials: true });
		// Any order event for this chat: re-read the cards (debounced) so the steps stay what CORTEX can prove.
		source.addEventListener('order', () => {
			if (refetchTimer) clearTimeout(refetchTimer);
			refetchTimer = setTimeout(() => chatId && load(chatId), 400);
		});
	};

	$: if (chatId && chatId !== loadedFor) {
		loadedFor = chatId;
		cards = [];
		error = null;
		load(chatId);
		listen(chatId);
	}

	onDestroy(() => {
		clearInterval(tick);
		if (refetchTimer) clearTimeout(refetchTimer);
		source?.close();
	});

	const PRESSING_LABEL: Record<string, string> = {
		checks: 'Needs a fix',
		blocked: 'Blocked',
		kicked_up: 'Waiting on you',
		gate: 'Waiting on your word'
	};

	$: pressing = cards.filter((c) => c.pressing);
	$: inFlight = cards.filter((c) => !c.pressing && c.status !== 'done');
	$: finished = cards.filter((c) => !c.pressing && c.status === 'done');
</script>

<div class="flex flex-col gap-3 px-3 pt-1 pb-3 h-full overflow-y-auto">
	{#if error}
		<div class="rounded-xl border border-red-200 dark:border-red-500/30 px-3 py-2 text-xs text-red-700 dark:text-red-300">
			Couldn't read this chat's work: {error}
		</div>
	{/if}

	{#each pressing as card (card.id)}
		{@const why = card.pressing?.why ?? 'blocked'}
		{@const pr = prLinkOf(card.stations.flatMap((s) => s.evidence))}
		<section
			class="rounded-xl px-3.5 py-3 flex flex-col gap-2 {why === 'checks' || why === 'blocked'
				? 'bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30'
				: 'bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30'}"
			aria-label="Needs you"
		>
			<span
				class="text-[11px] font-semibold tracking-wide uppercase {why === 'checks' || why === 'blocked'
					? 'text-red-700 dark:text-red-300'
					: 'text-amber-800 dark:text-amber-300'}">{PRESSING_LABEL[why] ?? 'Needs you'}</span
			>
			<span class="text-sm font-medium text-gray-900 dark:text-gray-100">{card.title}</span>
			{#if card.pressing?.ask}
				<p class="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-line">{card.pressing.ask}</p>
			{/if}
			{#if pr}
				<a
					href={pr}
					target="_blank"
					rel="noopener noreferrer"
					class="self-start text-xs font-medium rounded-lg px-3 py-2 text-gray-900 dark:text-gray-100 bg-white/70 dark:bg-gray-900/60 border border-gray-200 dark:border-gray-800 hover:bg-white dark:hover:bg-gray-900"
					>Open pull request</a
				>
			{/if}
		</section>
	{/each}

	{#each inFlight as card (card.id)}
		<WorkCard {card} {now} />
	{/each}

	{#each finished as card (card.id)}
		<WorkCard {card} {now} />
	{/each}

	{#if loading}
		<div class="text-xs text-gray-600 dark:text-gray-400 px-1">Reading this chat's work…</div>
	{:else if !error && cards.length === 0}
		<div class="text-xs text-gray-600 dark:text-gray-400 px-1 leading-relaxed">
			Nothing dispatched from this chat yet. When Greg hands work off, it shows up here and ticks off as it happens.
		</div>
	{/if}

	<div
		class="mt-auto pt-2.5 border-t border-gray-100 dark:border-gray-850 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-gray-600 dark:text-gray-400"
		aria-label="Key"
	>
		<span class="flex items-center gap-1"><span class="size-2 rounded-full bg-violet-500"></span>thinking</span>
		<span class="flex items-center gap-1"><span class="size-2 rounded-full bg-blue-500"></span>working</span>
		<span class="flex items-center gap-1"><span class="size-2 rounded-full bg-amber-500"></span>waiting on you</span>
		<span class="flex items-center gap-1"><span class="size-2 rounded-full bg-green-500"></span>done</span>
		<span class="flex items-center gap-1"><span class="size-2 rounded-full bg-red-500"></span>failed</span>
	</div>
</div>
