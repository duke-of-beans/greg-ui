import { WEBUI_API_BASE_URL } from '$lib/constants';

/** Mirrors CORTEX cortex/src/work-orders/panel.ts (Gregore-private). Steps turn done only on order-event evidence. */
export type StationKey = 'received' | 'dispatched' | 'picked_up' | 'pr' | 'checks' | 'deployed' | 'recorded';
export type StationState = 'done' | 'live' | 'todo' | 'failed';
export type PanelStatus = 'thinking' | 'working' | 'waiting_on_you' | 'done' | 'failed';

export interface Station {
	key: StationKey;
	state: StationState;
	at: string | null;
	ms: number | null;
	evidence: Array<Record<string, unknown>>;
}

export interface WorkCard {
	id: string;
	title: string;
	project: string;
	workClass: string | null;
	state: string;
	status: PanelStatus;
	stale: boolean;
	lastEventAt: string | null;
	stations: Station[];
	pressing: { why: 'gate' | 'kicked_up' | 'blocked' | 'checks'; ask: string | null } | null;
}

export interface ChatWork {
	chat: string;
	cards: WorkCard[];
}

/** One chat's orders as panel cards (proxied to CORTEX server-side; the browser never holds the CORTEX key). */
export const getChatWork = async (token: string, chatId: string): Promise<ChatWork> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/greg/work/chat?id=${encodeURIComponent(chatId)}`, {
		headers: { Accept: 'application/json', authorization: `Bearer ${token}` }
	});
	const body = await res.json().catch(() => null);
	if (!res.ok) throw new Error(body?.detail ?? `work panel: ${res.status}`);
	return body as ChatWork;
};

/** Live order events for one chat (Server-Sent Events; authenticated by the session cookie). */
export const chatWorkEventsUrl = (chatId: string): string =>
	`${WEBUI_API_BASE_URL}/greg/work/events?chat=${encodeURIComponent(chatId)}`;

/** First pull-request link in a step's evidence, if any. */
export const prLinkOf = (evidence: Array<Record<string, unknown>>): string | null => {
	for (const ev of evidence) {
		if (typeof ev.url === 'string' && /\/pull\/\d+/.test(ev.url)) return ev.url;
		const ref = typeof ev.id === 'string' ? ev.id : typeof ev.pr === 'string' ? ev.pr : null;
		const m = ref ? /^([\w.-]+\/[\w.-]+)#(\d+)$/.exec(ref) : null;
		if (m) return `https://github.com/${m[1]}/pull/${m[2]}`;
	}
	return null;
};
