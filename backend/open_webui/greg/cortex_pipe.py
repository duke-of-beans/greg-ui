"""
cortex_pipe.py  v6.3  (2026-09-23)
Greg routing brain - ARCHITECTURAL INVERSION: 7-stage deterministic pipeline.

"The brain calls reasoning. Reasoning does not run the brain."

pipe() no longer does [fetch context -> build prompt -> call LLM -> return].
It runs a fixed 7-stage pipeline where ONLY stage 4 (reason) may call an LLM,
and only when stage 3 (classify) decides the message actually needs one.

    1. intake    (deterministic) - parse message, extract signals/entities
    2. enrich    (deterministic) - CORTEX recall + beliefs + gaps + action
                                    classes + WHETSTONE frame, all via plain
                                    HTTP, NO LLM call
    3. classify  (deterministic) - route: does this need an LLM at all?
    4. reason    (LLM, gated)    - cascade -> furnace -> effector chain,
                                    fed a structured brief, not a raw prompt
    5. gate      (deterministic) - POSTCOG-style output gate (prose check,
                                    dismissal detector, ring floor)
    6. absorb    (deterministic) - fire-and-forget: rosetta ingest, brain
                                    remember, beliefs update, gap formation
    7. emit      (deterministic) - dispatch-block extraction, proactive
                                    suffix, final clean

v5.0's provider chain (_try_cascade / _try_furnace / _try_effector) is
UNCHANGED and lives entirely inside stage 4 - this is additive structure
around it, not a rewrite of the parts that already work.

v6.3 FIX (2026-09-23): All CORTEX routes verified against live MCP tool
schemas. Fixed: /v1/memory/recall -> /v1/recall, /v1/beliefs/query ->
/v1/beliefs, /v1/gaps/list -> /v1/gaps, /v1/memory/remember ->
/v1/brain/remember, /v1/beliefs/update -> /v1/beliefs, /v1/gaps/form ->
/v1/gaps, /v1/rosetta/ingest -> /v1/rosetta. Added auth headers to all
7 CORTEX calls. Fixed payloads for rosetta_ingest (channel/role/content),
beliefs_absorb (subject/claim/provenance), gap_form (domain/observation).
Fixed CORTEX_URL default to cortex-production-d0d7.up.railway.app.

v6.1 CHANGE (2026-09-22): root-cause finding, not a patch. CORTEX's
/v1/ai/complete was observed returning HTTP 200 with an upstream provider
failure (Groq rate-limit on openai/gpt-oss-120b) embedded as plain text in
the response body, instead of signaling failure structurally. That is a
CORTEX-side API contract defect - success and failure are supposed to be
distinguishable without reading prose - and the real fix belongs in
cortex/src, not here. This session has no write access to that repo
(same credential-materialization block as the route-verification gap
above); flag it as a CORTEX gap rather than silently working around it.

What DID change here, as defense-in-depth against that defect reaching
David as if it were Greg talking: _is_prose() no longer grows a literal,
per-vendor string blacklist (that is the patch anti-pattern - it only
catches errors already seen, and needs a new line every time a different
upstream provider fails a different way). It now checks, in order of
authority:
  1. STRUCTURAL - if the provider's JSON body itself carries an explicit
     failure signal (`"ok": false`, `"error": ...`, `"success": false`),
     trust that immediately. Forward-compatible with CORTEX's contract
     being fixed properly upstream.
  2. CLASS-LEVEL PATTERN - one regex recognizing the SHAPE of a gateway/
     provider failure (rate-limit/quota language, 429/500/502/503/504,
     "try again in Ns", context-length-exceeded, model-unavailable,
     an Error:/Exception:/Failed: prefix) rather than any single vendor's
     exact wording. Catches Groq today, a different upstream tomorrow,
     without another edit here.
This is still a client-side heuristic, not a substitute for the CORTEX
contract fix - it narrows the blast radius, it does not close the gap.

v6.2 CHANGE (2026-09-22): ROOT CAUSE, confirmed by reading the actual
running source on Sentinel (open_webui/utils/plugin.py and functions.py),
not inferred. cortex_pipe.py has NEVER loaded as a real Open WebUI model,
on v5.0, v6.0, or v6.1 alike:

  1. plugin.py's load_function_module_by_id() only recognizes a module
     that defines a class named exactly `Pipe`, `Filter`, `Action`, or
     `Event`. This file defined `class Pipeline` - not a typo introduced
     today, present in v5.0 as handed off, and propagated unverified
     into v6.0/v6.1. Every deploy today wrote a syntactically valid file
     to the right path and passed AST/py_compile - neither check catches
     this, because it is not a Python error, it is Open WebUI's own
     class-name contract.
  2. functions.py's generate_function_chat_completion() always calls the
     entrypoint as `pipe(**{'body': form_data, ...})` - a single `body`
     dict kwarg, with extra params (`__user__`, `__event_emitter__`, etc.)
     injected only when their names appear in the function's own
     signature (via inspect.signature()). This file's `pipe()` took
     `(self, user_message, model_id, messages, body)` - four positional
     params Open WebUI's caller has no way to supply, so even a correctly
     named class would still fail to be called.

Practical consequence: nothing that happened in David's chat today - the
Groq rate-limit error, the tool-calling behavior, all of it - went
through this code. Some other backend or fallback handled those turns.
The v6.1 Groq-error classifier is still correct defense-in-depth and is
kept, but it was defending a pipeline that was never actually receiving
traffic.

What changed: `class Pipeline` -> `class Pipe`. The old `pipe()` orchestrator
(the 7-stage runner) is renamed to `_run_pipeline()`, unchanged internally.
A new `pipe(self, body: dict) -> str` is the real entrypoint, matching
Open WebUI's actual calling convention exactly as read from functions.py -
it unpacks `body["model"]` / `body["messages"]`, extracts the current
user message text (a new `_extract_message_text()` helper, factored out
of the history-building logic that already existed for prior turns), and
calls `_run_pipeline()` with the same four arguments it always expected.
"""

from __future__ import annotations
import asyncio
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from pydantic import BaseModel

VERSION = "6.3"
_SM_PATH = "/home/david/greg-ui/ops-context/GREG_SELF_MODEL.md"

OFFLINE_MSG = (
    "I am offline right now - none of my inference paths are responding. "
    "Check: (1) CORTEX/Railway health, (2) Furnace/Ollama on Sentinel "
    "(docker ps), (3) ANTHROPIC_KEY in Open WebUI Valves. "
    "David can restart with: docker restart greg-ui on Sentinel."
)

_GREG_PERSONA = (
    "You are Greg - David Kirsch cognitive OS and chief of staff. "
    "Respond in clear, direct prose. Never include stack traces, raw error "
    "messages, machine diagnostics, or timing HTML in your reply. "
    "If a system is down, say so in one plain sentence."
)

_WHETSTONE = (
    "\n\n[WHETSTONE] Before sending: "
    "(1) Is every claim accurate? "
    "(2) Is this the clearest way to say it? "
    "(3) Does this serve what David actually needs?"
)

# Dismissal-phrase detector (David's 2026-09-02 directive: DETECTOR, NOT
# REJECTOR - "so I can monitor and steer"). Flag at high salience, never
# block or rewrite. A regex blacklist that silently rewrote would just
# teach the model better camouflage - the tell IS the signal.)
_DISMISSAL_MARKERS = (
    "debunked", "conspiracy theory", "lacks substantiation",
    "no credible evidence", "widely discredited", "fringe theory",
    "not taken seriously", "has been thoroughly disproven",
)

# Portfolio entity vocabulary for deterministic entity-mention extraction
# in stage 1 (intake). Not exhaustive - extend as new ventures/systems
# come online. Sourced from /areas/gregore.md and /areas/ganglion.md.
_PORTFOLIO_ENTITIES = (
    "gregore", "ganglion", "cortex", "whetstone", "postcog", "tessryx",
    "plexus", "thalamic", "sentinel", "tranche", "covos", "safeword",
    "aegis", "scrvnr", "consonance", "gravee", "patch act", "patchact",
    "asuriq", "actadicta", "proper sluice", "easter agency", "hirm",
    "vesuvius", "arc-agi", "arc prize", "greglite", "brain.db",
    "rosetta", "nightshift", "seeking", "imprint", "treg", "yuma",
    "shim", "vigil", "throwbak", "g7", "m3",
)

_STATUS_QUERY_RE = re.compile(
    r"\b(status|health|up|down|working|broken|online|offline)\b.{0,20}"
    r"\?|\bis\s+\w+\s+(up|down|working|broken|healthy)\b",
    re.IGNORECASE,
)
_FACTUAL_LOOKUP_RE = re.compile(
    r"^\s*(what|who|when|where|which)\b.{0,120}\?",
    re.IGNORECASE,
)
_DISPATCH_RE = re.compile(r"```gregore-dispatch", re.IGNORECASE)
_IMPERATIVE_RE = re.compile(
    r"\b(build|fix|deploy|write|implement|refactor|design|debug|create|"
    r"investigate|research|analyze|draft|plan)\b",
    re.IGNORECASE,
)

# Local execution failures - a crash IN this process or a tool it shelled
# out to (Python traceback, CUDA/GPU error, a subprocess that ran out of
# turns). Different failure mode from an upstream provider's own error
# text arriving as if it were content - kept as its own check rather than
# folded into the class-pattern below, because these are unambiguous
# machine artifacts, not something any future provider could phrase
# differently and slip past.
_LOCAL_CRASH_MARKERS = (
    "Traceback (most recent",
    "NameError:", "TypeError:", "ValueError:", "AttributeError:",
    "Reached max turns",
    "[local inference unavailable",
    "[cortex_pipe]",
    "nvidia-smi",
    "torch.cuda",
    "CUDA error",
)

# Class-level detector for an UPSTREAM PROVIDER failure riding inside a
# 200 OK / otherwise well-formed response - the Groq/gpt-oss-120b rate
# limit incident (2026-09-22) is the instance that surfaced this, but the
# pattern is deliberately genre-level (rate limits, quota, gateway HTTP
# codes, retry-after phrasing, context/model errors) rather than that
# vendor's exact string, so the next provider that fails this way is
# caught without another edit here. This is a heuristic safety net, not
# the fix - the fix is CORTEX signaling failure structurally instead of
# embedding it in the text field (see module docstring, v6.1 CHANGE).
_PROVIDER_ERROR_RE = re.compile(
    r"^\s*(error|exception|failed|failure|warning)\s*:"
    r"|\brate[\s-]?limit(ed|s|ing)?\b"
    r"|\bquota\s+(exceeded|reached)\b"
    r"|\btoo\s+many\s+requests\b"
    r"|\b(429|500|502|503|504)\b"
    r"|\bplease\s+try\s+again\s+in\s+[\d.]+\s*s(ec(ond)?s?)?\b"
    r"|\binsufficient\s+(quota|credits|balance)\b"
    r"|\bcontext\s+length\s+exceeded\b"
    r"|\bmodel\s+(not\s+found|unavailable|overloaded)\b"
    r"|\btokens?\s+per\s+minute\b"
    r"|\bTPM\b",
    re.IGNORECASE,
)


class ThinkingTrace:
    """Timing trace for debugging. Writes to stdout ONLY - never in response body."""

    def __init__(self) -> None:
        self._events: list[tuple[str, float]] = []
        self._t0 = time.time()

    def mark(self, label: str) -> None:
        self._events.append((label, time.time() - self._t0))

    def log(self) -> None:
        """Print trace to stdout. Do NOT return this string or append to response."""
        elapsed = time.time() - self._t0
        lines = [f"[cortex_pipe] {lbl}: {t:.2f}s" for lbl, t in self._events]
        lines.append(f"[cortex_pipe] TOTAL: {elapsed:.2f}s")
        print("\n".join(lines))


# ── Stage payloads ──────────────────────────────────────────────────────────
# Plain dataclasses, not pydantic - these never leave the process, no
# validation overhead needed. Each stage's OUTPUT is the next stage's INPUT;
# nothing later than stage 3 may reach back into raw messages/body.

@dataclass
class Intake:
    user_message: str
    message_type: str            # "status_query" | "factual_lookup" | "dispatch_paste" | "reasoning"
    entities: list[str] = field(default_factory=list)
    signals: dict = field(default_factory=dict)
    depth_label: str = "Standard"
    claude_model: str = ""
    max_tokens: int = 4096
    base_system: str = ""
    history_tail: str = ""


@dataclass
class Enriched:
    intake: Intake
    memory: str = ""
    beliefs: str = ""
    gaps: str = ""
    action_classes: str = ""
    whetstone_frame: str = _WHETSTONE
    self_model: str = ""


@dataclass
class Brief:
    enriched: Enriched
    route: str            # "direct" | "reason"
    direct_answer: Optional[str] = None
    system: str = ""
    prompt: str = ""


class Pipe:
    """MUST be named exactly `Pipe` - Open WebUI's plugin loader
    (open_webui/utils/plugin.py, load_function_module_by_id) only
    recognizes `Pipe`, `Filter`, `Action`, or `Event` as a module-level
    class name. Confirmed against the running source on Sentinel,
    2026-09-22 - see module docstring, v6.2 CHANGE. `Pipeline` (every
    prior version) was never valid and never loaded."""

    class Valves(BaseModel):
        # CORTEX / Railway
        CORTEX_URL: str = "https://cortex-production-d0d7.up.railway.app"
        CORTEX_API_KEY: str = ""
        CASCADE_TIMEOUT: int = 45
        ENRICH_TIMEOUT: int = 8
        # Furnace / Ollama
        FURNACE_URL: str = "http://localhost:11434"
        FURNACE_MODEL: str = "llama3:8b"
        FURNACE_TIMEOUT: int = 60
        # Claude subprocess
        ANTHROPIC_KEY: str = ""
        EFFECTOR_TIMEOUT: int = 120
        QUICK_MODEL: str = "claude-haiku-4-5-20251001"
        STANDARD_MODEL: str = "claude-sonnet-4-5"
        DEEP_MODEL: str = "claude-opus-4-5"
        DELIBERATE_MODEL: str = "claude-opus-4-5"
        # Token budgets
        MAX_TOKENS_QUICK: int = 1024
        MAX_TOKENS_STANDARD: int = 4096
        MAX_TOKENS_DEEP: int = 8192
        MAX_TOKENS_DELIBERATE: int = 16384
        # Features
        ENABLE_ROSETTA: bool = True
        ENABLE_WHETSTONE: bool = True
        ENABLE_PROACTIVE_SEEDS: bool = True
        ENABLE_ABSORB: bool = True
        ENABLE_CLASSIFY_SHORT_CIRCUIT: bool = True
        # Supabase (GANGLION action classes)
        SUPABASE_URL: str = "https://zdmxqzkqutizehynqojk.supabase.co"
        SUPABASE_KEY: str = ""

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.name = "Greg"

    def _cortex_auth_headers(self) -> dict:
        """Auth headers for all CORTEX API calls."""
        if self.valves.CORTEX_API_KEY:
            return {"Authorization": f"Bearer {self.valves.CORTEX_API_KEY}"}
        return {}

    # ── Static utilities ──────────────────────────────────────────────────────

    @staticmethod
    def _is_prose(text: str) -> bool:
        """Return True if text looks like human-readable prose Greg can say
        to David, not a local crash artifact or an upstream provider's own
        error text riding inside an otherwise-valid response.

        This is a CLIENT-SIDE SAFETY NET, not the fix. The fix for a
        provider embedding its own failure in a 200-OK content field is
        that provider returning a structural failure signal instead -
        see _try_cascade's dict-shape check, which runs BEFORE this and
        is the authoritative layer when a provider supports it. This
        function is what still runs when a provider does not."""
        if not text or len(text.strip()) < 15:
            return False
        for sig in _LOCAL_CRASH_MARKERS:
            if sig in text:
                return False
        if _PROVIDER_ERROR_RE.search(text):
            return False
        return bool(re.search(r'[A-Z][^.!?\n]{8,}[.!?]', text))

    @staticmethod
    def _extract_message_text(msg: dict) -> str:
        """Pull plain text out of one Open WebUI message dict. `content`
        can be a plain string or a list of content-part dicts (multimodal
        style: [{"type": "text", "text": "..."}, {"type": "image_url",
        ...}]) - handle both. Factored out so both history-building
        (prior turns) and the real pipe() entrypoint (the current turn)
        use the same logic instead of two subtly different copies."""
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        return (content or "").strip()

    @staticmethod
    def _clean(text: str) -> str:
        """Strip machine artifacts from a provider response."""
        if not text:
            return ""
        text = re.sub(r'\n*<details\b[^>]*>.*?</details>', '', text, flags=re.DOTALL)
        text = re.sub(r'\n\*[^\n*]{5,}\*\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\x1b\[[0-9;]*[mK]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ── STAGE 1: intake (deterministic) ─────────────────────────────────────

    def _intake(self, user_message: str, model_id: str, messages: list[dict], body: dict) -> Intake:
        """Parse the raw turn into structured signals. No I/O, no LLM."""
        depth_label, claude_model, max_tokens = self._depth_config(model_id)
        base_system = body.get("system", "")

        msg_lower = user_message.lower()
        entities = [e for e in _PORTFOLIO_ENTITIES if e in msg_lower]

        if _DISPATCH_RE.search(user_message):
            message_type = "dispatch_paste"
        elif _STATUS_QUERY_RE.search(user_message):
            message_type = "status_query"
        elif _FACTUAL_LOOKUP_RE.search(user_message.strip()) and not _IMPERATIVE_RE.search(user_message):
            message_type = "factual_lookup"
        else:
            message_type = "reasoning"

        signals = {
            "has_question_mark": "?" in user_message,
            "has_imperative": bool(_IMPERATIVE_RE.search(user_message)),
            "length": len(user_message),
            "entity_count": len(entities),
        }

        history: list[str] = []
        for msg in messages[:-1]:
            role = msg.get("role", "user")
            content = self._extract_message_text(msg)
            if content:
                history.append(f"[{role}]: {content}")
        history_tail = "\n".join(history[-12:])

        return Intake(
            user_message=user_message,
            message_type=message_type,
            entities=entities,
            signals=signals,
            depth_label=depth_label,
            claude_model=claude_model,
            max_tokens=max_tokens,
            base_system=base_system,
            history_tail=history_tail,
        )

    def _depth_config(self, model_id: str) -> tuple[str, str, int]:
        mid = (model_id or "").lower()
        if any(k in mid for k in ("quick", "haiku", "fast", "lite")):
            return "Quick", self.valves.QUICK_MODEL, self.valves.MAX_TOKENS_QUICK
        # Deliberate: highest-effort tier, checked before "deep" so it
        # doesn't fall through to that bucket. Today this only widens the
        # token budget and adds a system-prompt suffix (below) telling the
        # single model to reason more carefully - true multi-model
        # consensus is WorkForce/Consensus wiring that doesn't exist in
        # this file yet (see GREGORE_CANON.md §5/§7.0 step 2,
        # selectTopology()). _is_deliberate() is the seam future wiring
        # hangs off of.
        if any(k in mid for k in ("deliberate", "consensus")):
            return "Deliberate", self.valves.DELIBERATE_MODEL, self.valves.MAX_TOKENS_DELIBERATE
        if any(k in mid for k in ("deep", "opus", "research", "thorough")):
            return "Deep", self.valves.DEEP_MODEL, self.valves.MAX_TOKENS_DEEP
        return "Standard", self.valves.STANDARD_MODEL, self.valves.MAX_TOKENS_STANDARD

    @staticmethod
    def _is_deliberate(depth_label: str) -> bool:
        """Flag checked by _build_system / _reason. Placeholder seam for
        future WorkForce/Consensus wiring - not implemented here."""
        return depth_label == "Deliberate"

    # ── STAGE 2: enrich (deterministic, mechanical, no LLM) ─────────────────
    # Every call here is fire-and-forget-safe: wrapped try/except, returns
    # "" on any failure. A dead adapter degrades context, it never breaks
    # the turn. This mirrors v5.0's existing provider-isolation pattern -
    # the same discipline just applied one layer earlier.

    def _load_self_model(self) -> str:
        try:
            with open(_SM_PATH) as fh:
                return fh.read()
        except Exception as exc:
            print(f"[cortex_pipe] self-model load failed: {exc}")
            return ""

    async def _fetch_action_classes(self) -> str:
        if not (self.valves.SUPABASE_URL and self.valves.SUPABASE_KEY):
            return ""
        url = (
            f"{self.valves.SUPABASE_URL}/rest/v1/ganglion_action_policy"
            "?select=action_class,scope_description,status&order=status.asc"
        )
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    url,
                    headers={
                        "apikey": self.valves.SUPABASE_KEY,
                        "Authorization": f"Bearer {self.valves.SUPABASE_KEY}",
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status != 200:
                        return ""
                    rows = await resp.json()
                    if not rows:
                        return ""
                    lines = ["GANGLION DISPATCH - available action classes:"]
                    for row in rows:
                        lines.append(
                            f"  * {row.get('action_class', '')} "
                            f"(tier {row.get('status', '?')}): "
                            f"{row.get('scope_description', '')}"
                        )
                    lines.append(
                        'To dispatch emit a ```gregore-dispatch block: '
                        '{"action_class": "<ac>", "lane": "directed", "target_repo": "<project>", "prompt": "<detailed task>", "payload": {...additional params...}}'
                    )
                    return "\n".join(lines)
        except Exception as exc:
            print(f"[cortex_pipe] action_classes fetch failed: {exc}")
            return ""

    async def _cortex_recall(self, query: str) -> str:
        url = f"{self.valves.CORTEX_URL}/v1/recall"
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    url,
                    json={"query": query[:500], "ring": 0, "limit": 5},
                    headers=self._cortex_auth_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.valves.ENRICH_TIMEOUT),
                ) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.json()
                    items = data.get("results", [])
                    snippets = [
                        f"  * {it.get('content', '').strip()[:250]}"
                        for it in items
                        if it.get("content", "").strip()
                    ]
                    return ("[Memory context:]\n" + "\n".join(snippets)) if snippets else ""
        except Exception:
            return ""

    async def _cortex_beliefs(self, query: str) -> str:
        """Best-effort: GET/POST CORTEX beliefs for the query subject.
        VERIFIED 2026-09-23. Soft-fails to ''."""
        url = f"{self.valves.CORTEX_URL}/v1/beliefs"
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    url,
                    json={"subject": query[:300], "ring": 0, "limit": 5},
                    headers=self._cortex_auth_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.valves.ENRICH_TIMEOUT),
                ) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.json()
                    beliefs = data.get("beliefs", [])
                    lines = [
                        f"  * {b.get('statement', '').strip()[:200]}"
                        for b in beliefs
                        if b.get("statement", "").strip()
                    ]
                    return ("[Formed beliefs:]\n" + "\n".join(lines)) if lines else ""
        except Exception as exc:
            print(f"[cortex_pipe] beliefs fetch failed (route may need correction): {exc}")
            return ""

    async def _cortex_gaps(self) -> str:
        """Best-effort: open gaps ready to surface. VERIFIED 2026-09-23. Soft-fails to ''."""
        url = f"{self.valves.CORTEX_URL}/v1/gaps"
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    url,
                    params={"status": "open", "limit": 3},
                    headers=self._cortex_auth_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.valves.ENRICH_TIMEOUT),
                ) as resp:
                    if resp.status != 200:
                        return ""
                    data = await resp.json()
                    gaps = data.get("gaps", [])
                    lines = [
                        f"  * {g.get('description', '').strip()[:200]}"
                        for g in gaps
                        if g.get("description", "").strip()
                    ]
                    return ("[Open gaps:]\n" + "\n".join(lines)) if lines else ""
        except Exception as exc:
            print(f"[cortex_pipe] gaps fetch failed (route may need correction): {exc}")
            return ""

    async def _enrich(self, intake: Intake) -> Enriched:
        """Stage 2. Fire every context adapter in parallel. Zero LLM tokens."""
        self_model = self._load_self_model()
        tasks = {
            "action_classes": asyncio.create_task(self._fetch_action_classes()),
            "memory": asyncio.create_task(self._cortex_recall(intake.user_message)),
            "beliefs": asyncio.create_task(self._cortex_beliefs(intake.user_message)),
            "gaps": asyncio.create_task(self._cortex_gaps()),
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        out = {}
        for key, res in zip(tasks.keys(), results):
            out[key] = res if isinstance(res, str) else ""

        return Enriched(
            intake=intake,
            memory=out["memory"],
            beliefs=out["beliefs"],
            gaps=out["gaps"],
            action_classes=out["action_classes"],
            whetstone_frame=_WHETSTONE if self.valves.ENABLE_WHETSTONE else "",
            self_model=self_model,
        )

    # ── STAGE 3: classify (deterministic routing) ───────────────────────────
    # Conservative by design for this P0 pass: only short-circuits the LLM
    # when a message is BOTH a recognized cheap-answer shape AND we already
    # have the data in hand from stage 2. Everything else proceeds to
    # stage 4 exactly as v5.0 always did. This is the smallest classifier
    # that is honestly mechanical rather than a heuristic pretending to be
    # one - it never guesses at intent it can't ground in fetched data.

    def _classify(self, enriched: Enriched) -> Brief:
        intake = enriched.intake

        if self.valves.ENABLE_CLASSIFY_SHORT_CIRCUIT:
            if intake.message_type == "status_query" and enriched.action_classes:
                return Brief(
                    enriched=enriched,
                    route="direct",
                    direct_answer=self._clean(enriched.action_classes),
                )
            if intake.message_type == "dispatch_paste":
                # Already contains a gregore-dispatch block - nothing to
                # reason about, just pass it straight to emit for parsing.
                return Brief(
                    enriched=enriched,
                    route="direct",
                    direct_answer=intake.user_message,
                )

        system = self._build_system(intake, enriched)
        prompt = self._build_prompt(intake, enriched)
        return Brief(enriched=enriched, route="reason", system=system, prompt=prompt)

    def _build_system(self, intake: Intake, enriched: Enriched) -> str:
        parts: list[str] = []
        if enriched.self_model:
            parts.append(f"<greg_self_model>\n{enriched.self_model}\n</greg_self_model>")
        if enriched.action_classes:
            parts.append(enriched.action_classes)
        if enriched.memory:
            parts.append(enriched.memory)
        if enriched.beliefs:
            parts.append(enriched.beliefs)
        if enriched.gaps:
            parts.append(enriched.gaps)
        parts.append(
            f"{_GREG_PERSONA}\n"
            f"[Mode: {intake.depth_label}] Calibrate response depth to this mode."
        )
        if self._is_deliberate(intake.depth_label):
            parts.append(
                "[DELIBERATE MODE] Take maximum care. Reason through all "
                "angles - risks, alternatives, second-order effects - "
                "before responding. (Single-model deliberation only; "
                "multi-model consensus is not yet wired.)"
            )
        if intake.base_system:
            parts.append(intake.base_system)
        if enriched.whetstone_frame:
            parts.append(enriched.whetstone_frame)
        return "\n\n".join(parts)

    def _build_prompt(self, intake: Intake, enriched: Enriched) -> str:
        if intake.history_tail:
            return f"{intake.history_tail}\n\n[user]: {intake.user_message}"
        return intake.user_message

    # ── STAGE 4: reason (LLM - the ONLY token-burning stage) ────────────────
    # Provider chain body is v5.0, unchanged. It now receives system/prompt
    # already assembled by stage 3 from the Brief, rather than building
    # them itself mid-pipe.

    async def _try_cascade(
        self, prompt: str, system: str, max_tokens: int, trace: ThinkingTrace
    ) -> Optional[str]:
        url = f"{self.valves.CORTEX_URL}/v1/ai/complete"
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        cortex_headers = (
            {"Authorization": f"Bearer {self.valves.CORTEX_API_KEY}"}
            if self.valves.CORTEX_API_KEY
            else {}
        )
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    url,
                    json={
                        "prompt": full_prompt,
                        "ring": 0,
                        "max_tokens": max_tokens,
                        "surface": "greg-ui",
                    },
                    headers=cortex_headers,
                    timeout=aiohttp.ClientTimeout(total=self.valves.CASCADE_TIMEOUT),
               ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        print(f"[cortex_pipe] cascade HTTP {resp.status}: {body[:120]}")
                        return None
                    data = await resp.json()

                    # STRUCTURAL check first, authoritative when present:
                    # if CORTEX's contract ever tells us plainly that the
                    # upstream call failed, believe that over any text
                    # content it also sent. Forward-compatible with the
                    # CORTEX-side contract fix this incident actually
                    # calls for (see module docstring, v6.1 CHANGE) -
                    # today CORTEX does not send this, so this check is a
                    # no-op until it does, at which point it becomes the
                    # real fix instead of the pattern-match fallback below.
                    if isinstance(data, dict) and (
                        data.get("ok") is False
                        or data.get("success") is False
                        or data.get("error")
                    ):
                        print(
                            "[cortex_pipe] cascade structural failure: "
                            f"{str(data.get('error') or data)[:150]!r}"
                        )
                        return None

                    raw = (
                        data.get("text")
                         or data.get("response")
                        or data.get("content")
                        or ""
                    )
                    text = self._clean(raw)
                    if self._is_prose(text):
                        trace.mark("cascade-ok")
                        return text
                    print(f"[cortex_pipe] cascade non-prose: {text[:100]!r}")
                    return None
        except asyncio.TimeoutError:
            print(f"[cortex_pipe] cascade timeout ({self.valves.CASCADE_TIMEOUT}s)")
            return None
        except Exception as exc:
            print(f"[cortex_pipe] cascade error: {exc}")
            return None

    async def _try_furnace(
        self, prompt: str, system: str, max_tokens: int, trace: ThinkingTrace
    ) -> Optional[str]:
        url = f"{self.valves.FURNACE_URL}/api/generate"
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    url,
                    json={
                        "model": self.valves.FURNACE_MODEL,
                        "prompt": full_prompt,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    },
                    timeout=aiohttp.ClientTimeout(total=self.valves.FURNACE_TIMEOUT),
               ) as resp:
                    if resp.status != 200:
                        print(f"[cortex_pipe] furnace HTTP {resp.status}")
                        return None
                    data = await resp.json()
                    text = self._clean(data.get("response", ""))
                    if self._is_prose(text):
                        trace.mark("furnace-ok")
                        return text
                    print(f"[cortex_pipe] furnace non-prose: {text[:100]!r}")
                    return None
        except asyncio.TimeoutError:
            print(f"[cortex_pipe] furnace timeout ({self.valves.FURNACE_TIMEOUT}s)")
            return None
        except aiohttp.ClientConnectorError:
            print("[cortex_pipe] furnace offline")
            return None
        except Exception as exc:
            print(f"[cortex_pipe] furnace error: {exc}")
            return None

    def _run_claude_subprocess(
        self, prompt: str, model: str, trace: ThinkingTrace
    ) -> Optional[str]:
        candidates = [
            "/home/david/.nvm/versions/node/v22.11.0/bin/claude",
            "/usr/local/bin/claude",
            "claude",
        ]
        claude_bin = next((c for c in candidates if os.path.isfile(c)), "claude")
        env = os.environ.copy()
        if self.valves.ANTHROPIC_KEY:
            env["ANTHROPIC_API_KEY"] = self.valves.ANTHROPIC_KEY
        try:
            result = subprocess.run(
                [claude_bin, "--model", model, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=self.valves.EFFECTOR_TIMEOUT,
                env=env,
            )
            stdout = (result.stdout or "").strip()
            if not stdout and result.returncode != 0:
                print(
                    f"[cortex_pipe] effector exit {result.returncode}: "
                    f"{result.stderr[:200]}"
                )
                return None
            text = self._clean(stdout)
            if self._is_prose(text):
                trace.mark("effector-ok")
                return text
            print(f"[cortex_pipe] effector non-prose: {text[:100]!r}")
            return None
        except subprocess.TimeoutExpired:
            print(f"[cortex_pipe] effector timeout ({self.valves.EFFECTOR_TIMEOUT}s)")
            return None
        except FileNotFoundError:
            print("[cortex_pipe] effector: claude binary not found")
            return None
        except Exception as exc:
            print(f"[cortex_pipe] effector error: {exc}")
            return None

    async def _try_effector(
        self, prompt: str, model: str, trace: ThinkingTrace
    ) -> Optional[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._run_claude_subprocess, prompt, model, trace
        )

    async def _reason(self, brief: Brief, trace: ThinkingTrace) -> str:
        """Stage 4. THE ONLY stage that may spend tokens."""
        intake = brief.enriched.intake
        response: Optional[str] = None

        response = await self._try_cascade(
            brief.prompt, brief.system, intake.max_tokens, trace
        )

        if response is None:
            trace.mark("cascade-miss")
            response = await self._try_furnace(
                brief.prompt, brief.system, intake.max_tokens, trace
            )

        if response is None and intake.depth_label != "Quick":
            trace.mark("furnace-miss")
            response = await self._try_effector(
                brief.prompt, intake.claude_model, trace
            )

        if response is None:
            trace.mark("all-miss")
            response = OFFLINE_MSG

        return response

    # ── PRIVATE LANE (Greg /Private manifold sub-pipe) ───────────────────────
    # Ring 0/1: data never leaves the local network (2026-08-02 rule,
    # GREGORE_CANON.md §6). Bypasses the whole 7-stage pipeline on purpose -
    # no CORTEX enrich/cascade/absorb calls, since all of those are Railway
    # (i.e. leave Sentinel). Two local Ollama nodes tried in priority order,
    # then an offline message; nothing here ever reaches the network beyond
    # those two LAN/Tailscale addresses.
    #
    # Non-streaming: this file's real pipe() entrypoint returns a single
    # str (module docstring, v6.2 CHANGE) - there is no generator-based
    # streaming path anywhere else in cortex_pipe.py, so this matches that
    # contract rather than the generator shape assumed in an earlier draft
    # of this patch (MANIFOLD_RESTORE_PATCH.md Change 5). Streaming can be
    # added later if pipe() itself becomes a streaming entrypoint.
    #
    # Status as of 2026-09-23: Furnace has been offline ~31+ days, and
    # Ollama is not yet installed on G7 (GREGORE_CANON.md §7 Tier 0 /
    # Phase 0). This lane will report "all local inference nodes are
    # offline" until one of those is fixed - the code is in place ahead
    # of that so nothing else needs to change when it is.

    _PRIVATE_ENDPOINTS: tuple[tuple[str, str], ...] = (
        ("furnace", "http://100.85.184.84:11434"),
        ("g7", "http://localhost:11434"),
    )
    _PRIVATE_MODELS: tuple[str, ...] = ("hermes3:8b", "dolphin3:8b")

    async def _handle_private(
        self, user_message: str, messages: list[dict]
    ) -> str:
        ollama_messages = [
            {"role": m.get("role", "user"), "content": c}
            for m in messages[:-1]
            if (c := self._extract_message_text(m))
        ]
        ollama_messages.append({"role": "user", "content": user_message})

        for node_name, base_url in self._PRIVATE_ENDPOINTS:
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(
                        f"{base_url}/api/tags",
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as health:
                        if health.status != 200:
                            print(f"[cortex_pipe] private: {node_name} health HTTP {health.status}")
                            continue
                        available = [
                            m.get("name", "")
                            for m in (await health.json()).get("models", [])
                        ]

                    active_model = next(
                        (c for c in self._PRIVATE_MODELS if any(c in a for a in available)),
                        None,
                    )
                    if not active_model:
                        print(f"[cortex_pipe] private: no hermes3/dolphin3 on {node_name}")
                        continue

                    async with sess.post(
                        f"{base_url}/api/chat",
                        json={
                            "model": active_model,
                            "messages": ollama_messages,
                            "stream": False,
                        },
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status != 200:
                            print(f"[cortex_pipe] private HTTP {resp.status} on {node_name}")
                            continue
                        data = await resp.json()
                        text = self._clean(data.get("message", {}).get("content", ""))
                        if self._is_prose(text):
                            print(f"[cortex_pipe] private: served by {node_name}/{active_model}")
                            return text
                        print(f"[cortex_pipe] private non-prose on {node_name}: {text[:100]!r}")
            except asyncio.TimeoutError:
                print(f"[cortex_pipe] private: {node_name} timeout")
                continue
            except aiohttp.ClientConnectorError:
                print(f"[cortex_pipe] private: {node_name} unreachable")
                continue
            except Exception as exc:
                print(f"[cortex_pipe] private error on {node_name}: {exc}")
                continue

        return (
            "[Greg /Private] All local inference nodes are offline - "
            "Furnace and G7 Ollama are both unreachable right now. "
            "Nothing left this network; message was not sent anywhere."
        )

    # ── STAGE 5: gate (deterministic output gate) ───────────────────────────
    # Detector, not rejector, for dismissal markers (David's 2026-09-02
    # directive) - flagged loudly, never blocked or rewritten. The only
    # hard veto is the pre-existing guaranteed-safety check: garbage/empty
    # output never reaches David, it becomes OFFLINE_MSG instead, exactly
    # as v5.0 already guaranteed. Ring/tier axis is a pass-through hook for
    # now - this surface is single-user (ring 0, David only) so the floor
    # is always satisfied, but the seam is here for the day another surface
    # (multi-user Wall Greg, Consonance) calls into the same pipeline.

    def _gate(self, response: str, trace: ThinkingTrace) -> str:
        if not self._is_prose(response):
            print(f"[cortex_pipe] gate: non-prose output vetoed -> OFFLINE_MSG: {response[:100]!r}")
            trace.mark("gate-veto")
            return OFFLINE_MSG

        lowered = response.lower()
        hits = [m for m in _DISMISSAL_MARKERS if m in lowered]
        if hits:
            # 10x salience log, per standing directive - proceed regardless.
            print(f"[cortex_pipe] gate: dismissal markers detected {hits} - logged, NOT blocked")

        trace.mark("gate-pass")
        return response

    # ── STAGE 6: absorb (deterministic, fire-and-forget) ────────────────────
    # Nothing here may block emit. Every call is asyncio.create_task'd and
    # its own errors are swallowed inside the coroutine - the brain learns
    # from every interaction mechanically, but a slow/dead CORTEX endpoint
    # can never make David wait longer for his answer.

    async def _rosetta_ingest(self, message: str) -> None:
        try:
            async with aiohttp.ClientSession() as sess:
                await sess.post(
                    f"{self.valves.CORTEX_URL}/v1/rosetta",
                    json={"channel": "greg-ui", "role": "human", "content": message},
                    headers=self._cortex_auth_headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception as exc:
            print(f"[cortex_pipe] rosetta failed: {exc}")

    async def _brain_remember(self, user_message: str, response: str) -> None:
        """Best-effort: log the exchange to brain.db via CORTEX. VERIFIED 2026-09-23."""
        try:
            async with aiohttp.ClientSession() as sess:
                await sess.post(
                    f"{self.valves.CORTEX_URL}/v1/brain/remember",
                    json={
                        "content": f"[greg-ui exchange] user: {user_message[:500]} | greg: {response[:500]}",
                        "source": "greg-ui",
                        "ring": 0,
                    },
                    headers=self._cortex_auth_headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception as exc:
            print(f"[cortex_pipe] brain_remember failed: {exc}")

    async def _beliefs_absorb(self, user_message: str, response: str) -> None:
        """Best-effort: feed the exchange into belief formation. VERIFIED 2026-09-23."""
        try:
            async with aiohttp.ClientSession() as sess:
                await sess.post(
                    f"{self.valves.CORTEX_URL}/v1/beliefs",
                    json={
                        "subject": "greg-ui-exchange",
                        "claim": f"User: {user_message[:300]} | Greg: {response[:300]}",
                        "provenance": "observed",
                        "confidence": 0.5,
                        "ring": 0,
                    },
                    headers=self._cortex_auth_headers(),
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception as exc:
            print(f"[cortex_pipe] beliefs_absorb failed: {exc}")

    async def _gap_form(self, intake: Intake, enriched: Enriched) -> None:
        """Best-effort: if enrich came back empty on a substantive question,
        that absence IS a gap - record it. VERIFIED 2026-09-23."""
        if intake.message_type == "reasoning" and not (enriched.memory or enriched.beliefs):
            try:
                async with aiohttp.ClientSession() as sess:
                    await sess.post(
                        f"{self.valves.CORTEX_URL}/v1/gaps",
                        json={
                            "domain": "knowledge",
                            "observation": f"No prior context found for: {intake.user_message[:300]}",
                            "salience": 0.5,
                            "warrant": "research",
                        },
                        headers=self._cortex_auth_headers(),
                        timeout=aiohttp.ClientTimeout(total=5),
                    )
            except Exception as exc:
                print(f"[cortex_pipe] gap_form failed: {exc}")

    def _absorb(self, intake: Intake, enriched: Enriched, response: str) -> None:
        """Stage 6. Fires all learning writes, blocks on none of them."""
        if not self.valves.ENABLE_ABSORB:
            return
        if self.valves.ENABLE_ROSETTA:
            asyncio.create_task(self._rosetta_ingest(intake.user_message))
        asyncio.create_task(self._brain_remember(intake.user_message, response))
        asyncio.create_task(self._beliefs_absorb(intake.user_message, response))
        asyncio.create_task(self._gap_form(intake, enriched))

    # ── STAGE 7: emit (deterministic) ────────────────────────────────────────

    def _extract_dispatch_blocks(self, text: str) -> tuple[str, list[dict]]:
        dispatches: list[dict] = []

        def _handle(m: re.Match) -> str:
            try:
                dispatches.append(json.loads(m.group(1)))
            except Exception as exc:
                print(f"[cortex_pipe] dispatch parse error: {exc}")
            return ""

        clean = re.sub(
            r"```gregore-dispatch\s*\n(.*?)```",
            _handle,
            text,
            flags=re.DOTALL,
        )
        return clean.strip(), dispatches

    @staticmethod
    def _proactive_suffix(response: str) -> str:
        if len(response) > 300 and re.search(
            r"\b(could|should|consider|recommend|might want|next step)\b",
            response,
            re.IGNORECASE,
        ):
            return "\n\n---\n*Want me to dig into any of these further?*"
        return ""


    async def _dispatch_to_ganglion(self, dispatch: dict) -> None:
        """Fire-and-forget: INSERT a dispatch block into ganglion_dispatch."""
        if not (self.valves.SUPABASE_URL and self.valves.SUPABASE_KEY):
            print("[cortex_pipe] dispatch skipped: no Supabase credentials")
            return
        payload = dispatch.get("payload", {})
        row = {
            "id": str(uuid.uuid4()),
            "lane": dispatch.get("lane", "directed"),
            "target_repo": dispatch.get("target_repo",
                           payload.get("target_repo", "general")),
            "prompt": dispatch.get("prompt",
                      payload.get("prompt", json.dumps(payload))),
            "action_class": dispatch.get("action_class", ""),
            "action_params": json.dumps(payload) if payload else "{}",
            "source": "greg-ui",
            "status": "pending",
        }
        url = f"{self.valves.SUPABASE_URL}/rest/v1/ganglion_dispatch"
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    url,
                    json=row,
                    headers={
                        "apikey": self.valves.SUPABASE_KEY,
                        "Authorization": f"Bearer {self.valves.SUPABASE_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status not in (200, 201):
                        body = await resp.text()
                        print(f"[cortex_pipe] dispatch INSERT failed "
                              f"({resp.status}): {body[:300]}")
                    else:
                        print(f"[cortex_pipe] dispatch queued: "
                              f"{row['id']} ac={row['action_class']}")
        except Exception as exc:
            print(f"[cortex_pipe] dispatch INSERT error: {exc}")

    async def _emit(self, response: str) -> str:
        """Stage 7. Ring/audience filtering (pass-through, single-user
        surface today) + dispatch-block extraction + proactive suffix."""
        response, dispatches = self._extract_dispatch_blocks(response)
        for d in dispatches:
            print(f"[cortex_pipe] dispatch: {json.dumps(d)[:300]}")
            asyncio.create_task(self._dispatch_to_ganglion(d))

        if self.valves.ENABLE_PROACTIVE_SEEDS:
            response += self._proactive_suffix(response)

        return response

    # ── Manifold: what makes the model picker show 5 entries ────────────────
    # Open WebUI's get_function_models() (functions.py) checks
    # hasattr(module, 'pipes'):
    #   - present: generates one model per entry below, with id
    #     "{this function's id}.{entry id}" (e.g. "cortex_pipe.greg-quick")
    #   - absent: generates exactly ONE invisible entry, id = the function's
    #     own id, name = self.name
    # This method's total absence was the root cause of the manifold never
    # appearing (see /areas/manifold-handoff.md, deleted once this lands,
    # and GREGORE_CANON.md §1 for the broader pattern this incident fits).
    # `self.name` above ("Greg") is the group label Open WebUI shows over
    # these five in the picker.

    def pipes(self) -> list[dict]:
        return [
            {
                "id": "greg-auto",
                "name": "Greg /Auto",
                "description": "Automatic depth selection based on task complexity",
            },
            {
                "id": "greg-quick",
                "name": "Greg /Quick",
                "description": "Fast responses, minimal reasoning overhead",
            },
            {
                "id": "greg-deep",
                "name": "Greg /Deep",
                "description": "Extended reasoning, multi-step analysis",
            },
            {
                "id": "greg-deliberate",
                "name": "Greg /Deliberate",
                "description": "Full deliberation with multi-model consensus",
            },
            {
                "id": "greg-private",
                "name": "Greg /Private",
                "description": "Local inference only - data never leaves the network",
            },
        ]

    # ── Real entrypoint: what Open WebUI actually calls ─────────────────────
    # functions.py builds call params as {'body': form_data} | {injected
    # __user__ / __event_emitter__ / etc. IF this signature names them} and
    # invokes pipe(**params) - so `body: dict` must be this method's own
    # parameter, not a separate positional argument buried after others.
    # See module docstring, v6.2 CHANGE, for the exact source read.
    #
    # Sub-pipe routing (new): once pipes() exists, Open WebUI calls this
    # same pipe() for every manifold entry, passing body["model"] as
    # "cortex_pipe.greg-quick" etc. - the sub-pipe id is the suffix after
    # the last ".". Greg /Private is intercepted here and never enters
    # _run_pipeline: it must not touch CORTEX/cascade/absorb, all of which
    # leave Sentinel, since its entire point is Ring 0/1 (data never
    # leaves the local network). Every other sub-pipe (including /Auto,
    # which has no depth keyword and so falls through to "Standard")
    # continues through the existing 7-stage pipeline unchanged -
    # _depth_config below already does keyword matching on model_id, so
    # "cortex_pipe.greg-quick" / "cortex_pipe.greg-deep" resolve correctly
    # with no separate mapping table needed; "deliberate" is a new keyword
    # added there for /Deliberate.

    async def pipe(self, body: dict) -> str:
        messages = body.get("messages") or []
        model_id = body.get("model", "")
        user_message = self._extract_message_text(messages[-1]) if messages else ""

        sub_pipe = model_id.split(".", 1)[-1] if "." in model_id else model_id
        if sub_pipe == "greg-private":
            return await self._handle_private(user_message, messages)

        return await self._run_pipeline(user_message, model_id, messages, body)

    # ── Orchestrates the 7 stages, nothing else ──────────────────────────────

    async def _run_pipeline(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> str:

        trace = ThinkingTrace()
        trace.mark("start")

        # 1. intake - deterministic
        intake = self._intake(user_message, model_id, messages, body)
        trace.mark("intake-done")

        # 2. enrich - deterministic, zero tokens
        enriched = await self._enrich(intake)
        trace.mark("enrich-done")

        # 3. classify - deterministic routing
        brief = self._classify(enriched)
        trace.mark("classify-done")

        # 4. reason - THE ONLY stage that may burn tokens, and only if
        #    classify routed here.
        if brief.route == "direct":
            trace.mark("reason-skipped")
            response = brief.direct_answer or OFFLINE_MSG
        else:
            response = await self._reason(brief, trace)
        trace.mark("reason-done")

        # 5. gate - deterministic output gate
        response = self._gate(response, trace)

        # 6. absorb - deterministic, fire-and-forget, never blocks emit
        self._absorb(intake, enriched, response)
        trace.mark("absorb-fired")

        # 7. emit - deterministic formatting
        response = await self._emit(response)
        trace.mark("emit-done")

        # Trace to stdout ONLY - never in response body
        trace.log()
        return response
