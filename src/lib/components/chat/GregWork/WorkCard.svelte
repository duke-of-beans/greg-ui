<script lang="ts">
	/**
	 * One work order as Gregore's work panel shows it (Gregore-private docs/GREGORE_WORK_PANEL_SPEC.md).
	 * Pure: everything comes in as props. A step is green only because CORTEX found evidence for it; no percentages.
	 */
	import type { Station, WorkCard } from '$lib/apis/greg/work';
	import { prLinkOf } from '$lib/apis/greg/work';

	export let card: WorkCard;
	export let now: number = Date.now();

	const LABELS: Record<string, string> = {
		received: 'Received',
		dispatched: 'Dispatched',
		picked_up: 'Picked up',
		pr: 'Pull request',
		checks: 'Checks',
		deployed: 'Deployed',
		recorded: 'Recorded'
	};

	const STATUS: Record<string, { label: string; cls: string }> = {
		thinking: { label: 'Thinking', cls: 'text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/10' },
		working: { label: 'Working', cls: 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-500/10' },
		waiting_on_you: { label: 'Waiting on you', cls: 'text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10' },
		done: { label: 'Done', cls: 'text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-500/10' },
		failed: { label: 'Failed', cls: 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-500/10' }
	};

	let open: string | null = null;

	const clock = (iso: string | null) =>
		iso ? new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
	const span = (ms: number | null) => {
		if (ms === null) return '';
		const m = Math.round(ms / 60_000);
		return m < 1 ? '<1m' : m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`;
	};
	const since = (iso: string | null) => (iso ? span(Math.max(0, now - Date.parse(iso))) : '');

	$: live = card.stations.find((s) => s.state === 'live' || s.state === 'failed') ?? null;
	/** The live step started when the last step with a time finished. */
	$: liveSince = (() => {
		const done = card.stations.filter((s) => s.state === 'done' && s.at);
		return done.length ? done[done.length - 1].at : card.lastEventAt;
	})();
	$: pr = prLinkOf(card.stations.flatMap((s) => s.evidence));
	$: status = STATUS[card.status] ?? STATUS.working;
	$: finished = card.status === 'done';
	$: total = (() => {
		const first = card.stations.find((s) => s.at)?.at;
		return first && card.lastEventAt ? Date.parse(card.lastEventAt) - Date.parse(first) : null;
	})();

	const evidenceLines = (s: Station): string[] =>
		s.evidence.map((ev) => {
			const kind = String(ev.kind ?? '');
			if (kind === 'checks') return `checks ${ev.state}${Array.isArray(ev.failing) && ev.failing.length ? `: ${ev.failing.join(', ')}` : ''}`;
			if (kind === 'pickup') return `picked up by ${ev.effector ?? 'a machine'}`;
			if (kind === 'review') return `review: ${ev.verdict ?? ''}`;
			return [kind, ev.id].filter(Boolean).join(' · ');
		});
</script>

<article
	class="rounded-xl border px-3.5 py-3 flex flex-col gap-2.5 {card.stale && !finished
		? 'border-amber-300/70 dark:border-amber-500/40'
		: 'border-gray-100 dark:border-gray-850'}"
>
	<header class="flex items-start justify-between gap-3">
		<div class="min-w-0 flex flex-col gap-0.5">
			<span class="text-sm font-medium text-gray-900 dark:text-gray-100 line-clamp-2">{card.title}</span>
			<span class="text-xs text-gray-600 dark:text-gray-400 font-mono truncate">{card.id} · {card.project}</span>
		</div>
		<span class="shrink-0 text-xs font-medium rounded-full px-2 py-0.5 whitespace-nowrap {status.cls}"
			>{status.label}{finished && total !== null ? ` · ${span(total)}` : ''}</span
		>
	</header>

	{#if card.stale && !finished}
		<div class="text-xs text-amber-800 dark:text-amber-300">Quiet for {since(card.lastEventAt)}</div>
	{/if}

	{#if !finished}
		<ol class="flex flex-col">
			{#each card.stations as s, i (s.key)}
				<li class="flex gap-2.5">
					<span class="flex flex-col items-center w-3 pt-1" aria-hidden="true">
						{#if s.state === 'done'}
							<span class="size-2.5 rounded-full bg-green-500"></span>
						{:else if s.state === 'live'}
							<span class="size-2.5 rounded-full bg-blue-500 animate-pulse"></span>
						{:else if s.state === 'failed'}
							<span class="size-2.5 rounded-full bg-red-500"></span>
						{:else}
							<span class="size-2.5 rounded-full border-2 border-gray-300 dark:border-gray-600"></span>
						{/if}
						{#if i < card.stations.length - 1}
							<span
								class="w-px flex-1 min-h-3 {s.state === 'done'
									? 'bg-green-500/40'
									: 'bg-gray-200 dark:bg-gray-800'}"
							></span>
						{/if}
					</span>
					<div class="flex-1 min-w-0 pb-1.5">
						<button
							class="w-full flex items-center justify-between gap-2 text-left text-xs rounded disabled:cursor-default"
							disabled={!s.evidence.length}
							aria-expanded={open === s.key}
							on:click={() => (open = open === s.key ? null : s.key)}
						>
							<span
								class={s.state === 'todo'
									? 'text-gray-500 dark:text-gray-500'
									: s.state === 'failed'
										? 'text-red-700 dark:text-red-300 font-medium'
										: s.state === 'live'
											? 'text-gray-900 dark:text-gray-100 font-medium'
											: 'text-gray-700 dark:text-gray-300'}
							>
								{LABELS[s.key] ?? s.key}
							</span>
							<span class="font-mono text-gray-600 dark:text-gray-400 tabular-nums">
								{#if s.state === 'live'}
									{since(liveSince)} and counting
								{:else if s.at}
									{clock(s.at)}{s.ms !== null ? ` · ${span(s.ms)}` : ''}
								{/if}
							</span>
						</button>
						{#if open === s.key}
							<ul class="mt-1 rounded-lg bg-gray-50 dark:bg-gray-850 px-2.5 py-1.5 flex flex-col gap-0.5">
								{#each evidenceLines(s) as line}
									<li class="text-xs font-mono text-gray-600 dark:text-gray-300 break-all">{line}</li>
								{/each}
							</ul>
						{/if}
					</div>
				</li>
			{/each}
		</ol>
	{/if}

	{#if pr}
		<a
			href={pr}
			target="_blank"
			rel="noopener noreferrer"
			class="self-start text-xs text-gray-600 dark:text-gray-300 underline underline-offset-2 hover:text-gray-900 dark:hover:text-white"
			>Open pull request</a
		>
	{/if}
	{#if live && !finished}
		<span class="sr-only">Current step: {LABELS[live.key]}</span>
	{/if}
</article>
