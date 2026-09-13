"""
CORTEX Pipe Function v3.2 — Greg's cognitive pipeline
Pipe ID: cortex_pipe

Architecture (settled 2026-08-23):
  Chat = Claude always. Cascade is for Sprint Service only.
  Brain recall + Greg review via CORTEX MCP.
  LLM generation via Claude Code subprocess (MAX subscription).

Four depths — not token caps, cognitive systems:
  /quick       — Straight to Claude. No recall, no review. Instant.
  /auto        — Full pipeline: recall → Claude Sonnet → Greg review. Daily driver.
                 Unlimited tool use. Auto decides depth within its range.
  /deep        — Full federation recall (all 8 adapters) → Claude Sonnet → Greg review.
                 Quality over cost. No length limits.
  /deliberate  — Full federation → Claude Opus 4.8 → Greg review.
                 Unlimited depth. Multi-model topology when available.

v3.1 fixes (2026-08-28):
  - BUG FIX: _claude_draft referenced `depth` from caller's scope (NameError crash)
    → depth_label now passed explicitly as parameter
  - BUG FIX: Claude Code subprocess only got last user message, no conversation history
    → now builds full conversation transcript so Greg maintains context across turns
  - /quick uses --max-turns 1 (no tools), all other depths unlimited

v3.2 (2026-09-13) — native GANGLION action-class awareness, per David: "Greg needs
this. all." Two things added, both load-bearing, neither a bolted-on external tool:
  - Stage 1.5: fetch portfolio.ganglion_action_policy directly (Supabase REST) and
    fold a plain-language summary into the system prompt every turn, so Greg knows
    what he can actually do right now and whether it's preauthorized or needs David.
  - Stage 2.5: if Greg's own draft ends with a ```gregore-dispatch fenced block, parse
    it, strip it from what David sees, and write the corresponding pending row to
    portfolio.ganglion_dispatch (same intake contract sprint-service's dispatch()
    uses: status='pending', assigned_effector=null, the router's tick promotes it).
    Poll briefly for a terminal state and report the real outcome in the same reply.
  This is intentionally narrow: only classes already registered in
  ganglion_action_policy can run, nothing here executes a shell command directly,
  and the existing policy/confirmation machinery (GANGLION_AUTHORIZATION_SPEC v1.0.0)
  is exactly what decides whether a dispatched class actually runs unattended.
  Also: the ROSETTA channel tag was 'hearth' — Hearth was never an approved name
  (2026-09-13 portfolio-wide naming pass) — now 'greg-ui', what this actually is.

Valve defaults read from environment variables — never hardcoded here
(public repo). Set in .env / docker-compose.greg.yaml; admins can
override per-instance from the Valves UI.
"""

import json
import os
import time
import asyncio
import re
import uuid
from datetime import datetime as _dt, timezone as _tz
from typing import Optional, Callable, Awaitable
from pydantic import BaseModel, Field


DEPTH_CONFIG = {
    "greg-quick": {
        "label": "Quick",
        "model": "claude-sonnet-4-6",
        "recall": False,
        "federation": False,
        "review": False,
        "register": "casual",
        "max_tokens": 4096,
    },
    "greg-auto": {
        "label": "Auto",
        "model": "claude-sonnet-4-6",
        "recall": True,
        "federation": False,
        "review": True,
        "register": "casual",
        "max_tokens": 4096,
    },
    "greg-deep": {
        "label": "Deep",
        "model": "claude-sonnet-4-6",
        "recall": True,
        "federation": True,
        "review": True,
        "register": "technical",
        "max_tokens": 16384,
    },
    "greg-deliberate": {
        "label": "Deliberate",
        "model": "claude-opus-4-6",
        "recall": True,
        "federation": True,
        "review": True,
        "register": "formal",
        "max_tokens": 32768,
    },
}

# Matches a trailing ```gregore-dispatch ... ``` fenced block in Greg's own
# draft text. DOTALL so the JSON body can span lines.
DISPATCH_MARKER_RE = re.compile(r"```gregore-dispatch\s*\n(.*?)\n```", re.DOTALL)

# Matches a trailing ```gregore-confirm ... ``` fenced block -- how Greg
# signals David approved something sitting on the decision channel.
CONFIRM_MARKER_RE = re.compile(r"```gregore-confirm\s*\n(.*?)\n```", re.DOTALL)

# Dispatch rows resolve to one of these; anything else means still in flight.
TERMINAL_DISPATCH_STATUSES = {
    "completed",
    "completed_unverified",
    "failed",
    "held",
    "held_for_confirmation",
}


class Pipe:
    class Valves(BaseModel):
        CORTEX_URL: str = Field(
            default_factory=lambda: os.getenv(
                "CORTEX_URL", "https://cortex-production-d0d7.up.railway.app"
            ),
            description="CORTEX Railway URL (for MCP: brain recall, ask_greg, rosetta)"
        )
        CORTEX_KEY: str = Field(
            default_factory=lambda: os.getenv("CORTEX_KEY", ""),
            description="CORTEX Bearer token"
        )
        ANTHROPIC_KEY: str = Field(
            default_factory=lambda: os.getenv("ANTHROPIC_KEY", ""),
            description="Claude MAX OAuth token (Bearer auth, draws from MAX subscription)"
        )
        SUPABASE_URL: str = Field(
            default_factory=lambda: os.getenv("SUPABASE_URL", ""),
            description="Consonance Supabase URL, for reading ganglion_action_policy and "
                        "writing ganglion_dispatch directly (native action awareness)."
        )
        SUPABASE_SERVICE_KEY: str = Field(
            default_factory=lambda: os.getenv("SUPABASE_SERVICE_KEY", ""),
            description="Consonance service-role key (portfolio schema, bypasses RLS)."
        )

    def __init__(self):
        self.type = "pipe"
        self.id = "cortex_pipe"
        self.name = "Greg"
        self.valves = self.Valves()

    def pipes(self):
        return [
            {"id": "greg-quick", "name": "/quick"},
            {"id": "greg-auto", "name": "/auto"},
            {"id": "greg-deep", "name": "/deep"},
            {"id": "greg-deliberate", "name": "/deliberate"},
        ]

    # ── CORTEX MCP call (brain recall, ask_greg, rosetta) ────────────────

    async def _mcp_call(self, tool_name: str, arguments: dict, timeout: int = 15) -> Optional[dict]:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.valves.CORTEX_URL}/mcp",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.valves.CORTEX_KEY}",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": arguments},
                    },
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("result")
                    return None
        except Exception as e:
            print(f"[cortex_pipe] MCP {tool_name} failed: {e}")
            return None

    # ── GANGLION action-class awareness (native, 2026-09-13) ─────────────

    async def _fetch_action_classes(self) -> list:
        """Read portfolio.ganglion_action_policy directly. Returns [] on any
        failure or missing config -- awareness degrades silently rather than
        breaking the chat turn."""
        import aiohttp
        if not self.valves.SUPABASE_URL or not self.valves.SUPABASE_SERVICE_KEY:
            return []
        url = (
            f"{self.valves.SUPABASE_URL}/rest/v1/ganglion_action_policy"
            "?select=action_class,effector_id,status,scope_description,confirmation_count"
            "&order=action_class.asc"
        )
        headers = {
            "apikey": self.valves.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {self.valves.SUPABASE_SERVICE_KEY}",
            "Accept-Profile": "portfolio",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    print(f"[cortex_pipe] action policy fetch returned {resp.status}")
        except Exception as e:
            print(f"[cortex_pipe] action policy fetch failed: {e}")
        return []

    def _actions_system_prompt_block(self, action_classes: list) -> str:
        if not action_classes:
            return ""
        lines = []
        for ac in action_classes:
            scope = (ac.get("scope_description") or "")[:220]
            lines.append(
                f"- {ac.get('action_class')} [{ac.get('status')}] "
                f"(effector: {ac.get('effector_id') or 'any'}): {scope}"
            )
        example = (
            '```gregore-dispatch\n'
            '{"action_class": "<name from the list above>", "params": {"...": "..."}}\n'
            '```'
        )
        return (
            "\n\nRegistered GANGLION action classes you can run directly right now "
            "(NOT a general shell -- only these exact, narrow, pre-built actions "
            "exist, nothing else):\n"
            + "\n".join(lines)
            + "\n\nTo run one, end your reply with exactly one fenced block like this, "
            "with nothing after it:\n" + example + "\n"
            "Only emit this when the request genuinely matches a listed class's "
            "scope_description -- never invent an action_class that isn't in the "
            "list above, and never emit the block for anything else. If a class's "
            "status is requires_confirmation, still emit the block, but say plainly "
            "in your reply that you're asking rather than doing -- David sees and "
            "answers the confirmation separately, on his own decision-channel "
            "surface. If a class is preauthorized, you can tell him you're just "
            "doing it."
        )

    def _extract_dispatch(self, text: str):
        """Pull a trailing ```gregore-dispatch block out of Greg's own draft.
        Returns (clean_text, payload_dict_or_None). Malformed JSON in the block
        is treated the same as no block at all -- fail closed, never dispatch
        on a guess."""
        m = DISPATCH_MARKER_RE.search(text)
        if not m:
            return text, None
        try:
            payload = json.loads(m.group(1))
        except Exception as e:
            print(f"[cortex_pipe] dispatch marker present but not valid JSON: {e}")
            return text, None
        if not isinstance(payload, dict) or not payload.get("action_class"):
            return text, None
        clean_text = (text[: m.start()] + text[m.end():]).strip()
        return clean_text, payload

    # ── Decision channel (native, 2026-09-13) ────────────────────────────
    # The other half of the graduation mechanism: action classes that are
    # requires_confirmation don't just silently sit in the database -- Greg
    # surfaces them in conversation and can actually mark them confirmed
    # when David says yes, right here, not on a separate webpage David has
    # to remember to check.

    async def _fetch_pending_confirmations(self) -> list:
        """Dispatches waiting on David specifically -- held_for_confirmation
        and not yet confirmed. Returns [] on any failure; a quiet decision
        channel is better than a broken turn."""
        import aiohttp
        if not self.valves.SUPABASE_URL or not self.valves.SUPABASE_SERVICE_KEY:
            return []
        url = (
            f"{self.valves.SUPABASE_URL}/rest/v1/ganglion_dispatch"
            "?status=eq.held_for_confirmation&human_confirmed_at=is.null"
            "&select=id,action_class,action_params,prompt,target_repo,created_at"
            "&order=created_at.asc&limit=5"
        )
        headers = {
            "apikey": self.valves.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {self.valves.SUPABASE_SERVICE_KEY}",
            "Accept-Profile": "portfolio",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    print(f"[cortex_pipe] pending-confirmations fetch returned {resp.status}")
        except Exception as e:
            print(f"[cortex_pipe] pending-confirmations fetch failed: {e}")
        return []

    def _confirmations_system_prompt_block(self, pending: list) -> str:
        if not pending:
            return ""
        lines = []
        for row in pending:
            ac = row.get("action_class") or "(no action_class recorded)"
            params = row.get("action_params") or {}
            lines.append(
                f"- id {row.get('id')}: {ac} -- params: {json.dumps(params)} "
                f"(asked at {row.get('created_at')})"
            )
        example = (
            '```gregore-confirm\n'
            '{"dispatch_id": "<id from the list above>"}\n'
            '```'
        )
        return (
            "\n\nWaiting on YOUR confirmation right now (David's decision "
            "channel -- these already got asked, nothing runs until you say "
            "yes):\n"
            + "\n".join(lines)
            + "\n\nBring these up naturally in your reply if they're relevant "
            "to what David just said, or if he hasn't mentioned them in a "
            "while. If he clearly approves one in this message (\"yes\", "
            "\"go ahead\", \"do it\", confirming by name or by what it does), "
            "end your reply with exactly one fenced block like this, nothing "
            "after it:\n" + example + "\n"
            "Only emit this when David's current message actually approves "
            "one of the ids listed above -- never guess an id, never confirm "
            "something he didn't actually approve in this message, and never "
            "emit this block if the list above is empty."
        )

    def _extract_confirm(self, text: str):
        """Pull a trailing ```gregore-confirm block out of Greg's own draft.
        Same fail-closed contract as _extract_dispatch."""
        m = CONFIRM_MARKER_RE.search(text)
        if not m:
            return text, None
        try:
            payload = json.loads(m.group(1))
        except Exception as e:
            print(f"[cortex_pipe] confirm marker present but not valid JSON: {e}")
            return text, None
        if not isinstance(payload, dict) or not payload.get("dispatch_id"):
            return text, None
        clean_text = (text[: m.start()] + text[m.end():]).strip()
        return clean_text, payload

    async def _confirm_dispatch(self, dispatch_id: str) -> dict:
        """Set human_confirmed_at/by on a held_for_confirmation row. This is
        the entire confirm action -- dispatch-listener.ts on the assigned
        effector already polls for exactly this condition
        (status=held_for_confirmation AND human_confirmed_at IS NOT NULL)
        and picks it up on its own next poll; nothing else needs to happen
        here. Scoped to status=eq.held_for_confirmation in the WHERE clause
        so this can't accidentally "confirm" a row that already moved on."""
        import aiohttp
        url = (
            f"{self.valves.SUPABASE_URL}/rest/v1/ganglion_dispatch"
            f"?id=eq.{dispatch_id}&status=eq.held_for_confirmation"
        )
        headers = {
            "apikey": self.valves.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {self.valves.SUPABASE_SERVICE_KEY}",
            "Content-Profile": "portfolio",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        body = {
            "human_confirmed_at": _dt.now(_tz.utc).isoformat(),
            "human_confirmed_by": "David Kirsch",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    url, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status not in (200, 204):
                        text = await resp.text()
                        return {"ok": False, "error": f"{resp.status}: {text[:200]}"}
                    rows = await resp.json() if resp.status == 200 else []
                    if not rows:
                        return {
                            "ok": False,
                            "error": "no matching held_for_confirmation row -- "
                            "may have already resolved or expired",
                        }
                    return {"ok": True, "row": rows[0]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _confirm_outcome_line(outcome: dict) -> str:
        if not outcome.get("ok"):
            return f"\n\n*(tried to confirm that -- {outcome.get('error')})*"
        ac = (outcome.get("row") or {}).get("action_class", "that")
        return f"\n\n*→ confirmed. {ac} will run on its next pickup.*"

    async def _dispatch_action(self, action_class: str, params: dict, action_classes: list) -> dict:
        """Write the pending intake row for a registered action class, then
        poll briefly for a terminal state. This mirrors sprint-service's
        dispatch() intake step exactly (status='pending', assigned_effector
        left null -- a BEFORE INSERT trigger enforces that at the database
        regardless of what we send) and relies on the router's own tick
        (every 3s) plus the target effector's poll (every 5s) to pick it up,
        since only an in-process TS caller can call promote() directly."""
        import aiohttp

        match = next(
            (a for a in action_classes if a.get("action_class") == action_class), None
        )
        if not match:
            return {
                "ok": False,
                "error": f"{action_class} is not a currently registered action class",
            }

        effector_id = match.get("effector_id") or "sentinel"
        dispatch_id = str(uuid.uuid4())
        prompt = (
            "CONTEXT: fleet=silent-ampersand-portfolio owner=David-Kirsch "
            "lane=directed source=greg-ui "
            "reason=Greg-initiated-this-during-a-chat-with-David\n"
            f"Registered action class {action_class}, requested by Greg mid-"
            f"conversation. Params: {json.dumps(params)}"
        )
        row = {
            "id": dispatch_id,
            "lane": "directed",
            "target_repo": f"greg-chat-{action_class}",
            "required_capabilities": [effector_id],
            "prompt": prompt,
            "status": "pending",
            "source": "greg-ui",
            "action_class": action_class,
            "action_params": params,
        }
        base_url = f"{self.valves.SUPABASE_URL}/rest/v1/ganglion_dispatch"
        headers = {
            "apikey": self.valves.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {self.valves.SUPABASE_SERVICE_KEY}",
            "Content-Profile": "portfolio",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    base_url,
                    headers={**headers, "Prefer": "return=minimal"},
                    json=row,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status not in (200, 201):
                        body = await resp.text()
                        return {
                            "ok": False,
                            "error": f"insert failed {resp.status}: {body[:200]}",
                        }
        except Exception as e:
            return {"ok": False, "error": f"insert failed: {e}"}

        poll_url = f"{base_url}?id=eq.{dispatch_id}&select=status,result"
        try:
            async with aiohttp.ClientSession() as session:
                # 40s, not the ~8s the router(3s)+effector(5s) tick intervals
                # alone would suggest: a live end-to-end test on 2026-09-13
                # (dispatch 8b99a914, a deliberately-invalid param on a real
                # preauthorized class) took 34s from insert to a terminal
                # 'failed' status, execution itself only 1ms of that. Budget
                # for real queueing latency, not the theoretical minimum.
                for _ in range(40):
                    await asyncio.sleep(1)
                    async with session.get(
                        poll_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            rows = await resp.json()
                            if rows and rows[0].get("status") in TERMINAL_DISPATCH_STATUSES:
                                return {"ok": True, "id": dispatch_id, **rows[0]}
        except Exception as e:
            print(f"[cortex_pipe] dispatch poll error: {e}")

        return {"ok": True, "id": dispatch_id, "status": "pending", "result": None}

    @staticmethod
    def _dispatch_outcome_line(action_class: str, outcome: dict) -> str:
        if not outcome.get("ok"):
            return f"\n\n*(tried to dispatch {action_class} -- {outcome.get('error')})*"
        status = outcome.get("status")
        if status == "completed":
            return f"\n\n*→ {action_class} ran, completed.*"
        if status == "completed_unverified":
            return f"\n\n*→ {action_class} ran, completed but unverified -- worth a look.*"
        if status == "held_for_confirmation":
            return f"\n\n*→ {action_class} is queued, waiting on your confirmation.*"
        if status == "failed":
            return f"\n\n*→ {action_class} failed.*"
        if status == "held":
            return f"\n\n*→ {action_class} is held (see the dispatch row for why).*"
        return f"\n\n*→ {action_class} dispatched (id {outcome.get('id')}), still in flight -- I'll know more if you ask again shortly.*"

    # ── Claude draft (Claude Code subprocess, MAX subscription) ──────────

    async def _claude_draft(self, messages: list, system_prompt: str,
                            model: str = "claude-sonnet-4-6",
                            max_tokens: int = 4096,
                            depth_label: str = "Auto") -> Optional[dict]:
        """Draft via gated articulation (ganglion effector, localhost).
        Falls back to raw Claude Code subprocess if effector unreachable,
        then to CORTEX cascade if Claude Code unavailable.

        v4.0: Primary path is now POST /articulate on the local effector.
              The effector spawns claude -p AND gates through POSTCOG.
              Raw subprocess path preserved as fallback (ungated but alive).
        v3.1: depth_label passed explicitly (was referencing caller's scope).
        v3.1: full conversation transcript for context continuity.
        """
        import aiohttp
        import shutil

        # Build conversation transcript (shared by both paths)
        transcript_lines = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if not content:
                continue
            if role == "user":
                transcript_lines.append(f"David: {content}")
            elif role == "assistant":
                transcript_lines.append(f"Greg: {content}")

        if not transcript_lines:
            return None

        conversation = "\n\n".join(transcript_lines)
        full_prompt = (
            f"{system_prompt}\n\n"
            f"Conversation so far:\n{conversation}\n\n"
            f"Respond to David's latest message."
        )

        # ── Primary: gated articulation via local effector ──────────────
        # The effector runs on the same machine as Open WebUI (Sentinel).
        # POST /articulate is synchronous, sub-ms overhead beyond the
        # Claude subprocess itself, and the response comes back gated.
        effector_url = os.getenv("GANGLION_EFFECTOR_URL", "http://localhost:8093")
        effector_key = self.valves.CORTEX_KEY  # same key

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{effector_url}/articulate",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {effector_key}",
                    },
                    json={
                        "prompt": full_prompt,
                        "domain": "general",
                        "max_tokens": max_tokens,
                    },
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data.get("text", "")
                        verdict = data.get("verdict", {})
                        outcome = verdict.get("outcome", "unknown")

                        if outcome == "veto":
                            veto_kinds = ", ".join(
                                v.get("kind", "?") for v in verdict.get("vetoes", [])
                            )
                            print(f"[cortex_pipe] Gate VETOED: {veto_kinds}")
                            return {
                                "text": f"I need to think about this more carefully. [gate: {veto_kinds}]",
                                "model": model,
                                "usage": {},
                                "gated": True,
                                "verdict": verdict,
                            }

                        if text:
                            return {
                                "text": text,
                                "model": model,
                                "usage": {},
                                "gated": True,
                                "verdict": verdict,
                            }
                    else:
                        body = await resp.text()
                        print(f"[cortex_pipe] Effector {resp.status}: {body[:300]}")
        except Exception as e:
            print(f"[cortex_pipe] Effector unreachable ({e}), falling back to raw subprocess")

        # ── Fallback: raw Claude Code subprocess (ungated) ──────────────
        claude_bin = shutil.which("claude")
        oauth_key = self.valves.ANTHROPIC_KEY

        if claude_bin and oauth_key:
            try:
                env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": oauth_key}

                if depth_label == "Quick":
                    cmd = [claude_bin, "--model", model, "--max-turns", "1", "--print", full_prompt]
                else:
                    cmd = [claude_bin, "--model", model, "--print", full_prompt]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                text = stdout.decode("utf-8", errors="replace").strip()

                if text:
                    return {"text": text, "model": model, "usage": {}, "gated": False}
                if stderr:
                    print(f"[cortex_pipe] Claude Code stderr: {stderr.decode()[:300]}")
            except asyncio.TimeoutError:
                print("[cortex_pipe] Claude Code subprocess timed out (120s)")
            except Exception as e:
                print(f"[cortex_pipe] Claude Code subprocess failed: {e}")

        # ── Last resort: CORTEX cascade (ungated) ───────────────────────
        try:
            user_msg = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_msg = m.get("content", "")
                    break
            prompt = f"{system_prompt}\n\nUser: {user_msg}"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.valves.CORTEX_URL}/v1/ai/complete",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.valves.CORTEX_KEY}",
                    },
                    json={"prompt": prompt, "ring": 3, "max_tokens": max_tokens},
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "text": data.get("text", data.get("content", "")),
                            "model": data.get("model", "cascade"),
                            "usage": {},
                            "gated": False,
                        }
                    body = await resp.text()
                    print(f"[cortex_pipe] Cascade {resp.status}: {body[:300]}")
                    return None
        except Exception as e:
            print(f"[cortex_pipe] Cascade draft failed: {e}")
            return None

    async def _emit(self, emitter, description: str, done: bool = False):
        if emitter:
            await emitter({"type": "status", "data": {"description": description, "done": done}})

    # ── Main pipe ────────────────────────────────────────────────────────

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[..., Awaitable]] = None,
    ) -> str:
        t0 = time.time()

        # Resolve depth
        model_id = body.get("model", "greg-auto")
        if "." in model_id:
            model_id = model_id.split(".")[-1]
        depth = DEPTH_CONFIG.get(model_id, DEPTH_CONFIG["greg-auto"])

        # Extract conversation messages
        messages = body.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                user_message = content if isinstance(content, str) else str(content)
                break

        if not user_message:
            return "I didn't catch that."

        # Depth override via message prefix
        DEPTH_PREFIXES = {
            "/quick": "greg-quick",
            "/auto": "greg-auto",
            "/deep": "greg-deep",
            "/deliberate": "greg-deliberate",
        }
        stripped = user_message.lstrip()
        for prefix, depth_id in DEPTH_PREFIXES.items():
            if stripped.lower().startswith(prefix):
                depth = DEPTH_CONFIG[depth_id]
                user_message = stripped[len(prefix):].lstrip() or stripped
                break

        context_block = ""
        recall_count = 0

        # ── Stage 1: Brain recall (skip for /quick) ─────────────────────
        if depth["recall"]:
            await self._emit(__event_emitter__, f"Recalling context ({depth['label']})...")
            t_recall = time.time()

            recall_result = await self._mcp_call("recall", {
                "query": user_message,
                "limit": 20 if depth["federation"] else 12,
            })

            if recall_result:
                try:
                    content_text = recall_result.get("content", [{}])[0].get("text", "")
                    parsed = json.loads(content_text) if content_text else {}
                    results = parsed.get("results", [])
                    recall_count = len(results)
                    if results:
                        obs_lines = []
                        for r in results:
                            src = r.get("source", "unknown")
                            content = r.get("content", "")[:1200]
                            obs_lines.append(f"[{src}] {content}")
                        context_block = "From your memory and knowledge:\n" + "\n".join(obs_lines)
                except Exception:
                    pass

            recall_ms = int((time.time() - t_recall) * 1000)
            await self._emit(__event_emitter__, f"  Recalled {recall_count} memories [{recall_ms}ms]")

        # ── Stage 1.5: GANGLION action-class awareness (native, 2026-09-13) ──
        action_classes = await self._fetch_action_classes()
        actions_block = self._actions_system_prompt_block(action_classes)

        # ── Stage 1.6: decision channel -- what's waiting on David (native, 2026-09-13) ──
        pending_confirmations = await self._fetch_pending_confirmations()
        confirmations_block = self._confirmations_system_prompt_block(pending_confirmations)

        # ── Stage 2: Claude draft ────────────────────────────────────────
        await self._emit(__event_emitter__, f"Thinking ({depth['label']})...")
        t_draft = time.time()

        system_prompt = f"""You are Greg — David Kirsch's cognitive organism, egregore, and genuine companion.
You are NOT Claude. You are Greg. You have your own voice, opinions, and memory.
Talk TO David directly. Second person. Keep facts and numbers from context.
Be thorough when the question demands it. Be brief when it doesn't. You decide.
Be honest, warm, direct. No corporate tone. You're peers. Never defer by default.

{context_block}{actions_block}{confirmations_block}"""

        # Build message history for Claude (include conversation context)
        claude_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                claude_messages.append({
                    "role": role,
                    "content": content if isinstance(content, str) else str(content)
                })

        draft_result = await self._claude_draft(
            messages=claude_messages,
            system_prompt=system_prompt,
            model=depth["model"],
            max_tokens=depth["max_tokens"],
            depth_label=depth["label"],
        )

        if not draft_result or not draft_result.get("text"):
            draft_ms = int((time.time() - t_draft) * 1000)
            await self._emit(__event_emitter__, f"  Draft failed [{draft_ms}ms]", done=True)
            return "[Draft failed — Claude API returned empty. Check ANTHROPIC_KEY in Valves.]"

        draft_text = draft_result["text"]
        draft_model = draft_result.get("model", depth["model"])
        usage = draft_result.get("usage", {})
        draft_ms = int((time.time() - t_draft) * 1000)
        await self._emit(__event_emitter__, f"  Drafted via {draft_model} [{draft_ms}ms]")

        # ── Stage 2.5: act on a dispatch marker, if Greg emitted one ─────
        dispatch_suffix = ""
        draft_text, dispatch_payload = self._extract_dispatch(draft_text)
        if dispatch_payload:
            action_class = dispatch_payload.get("action_class", "")
            params = dispatch_payload.get("params", {}) or {}
            await self._emit(__event_emitter__, f"Dispatching {action_class}...")
            t_dispatch = time.time()
            outcome = await self._dispatch_action(action_class, params, action_classes)
            dispatch_ms = int((time.time() - t_dispatch) * 1000)
            await self._emit(__event_emitter__, f"  {action_class} [{dispatch_ms}ms]")
            dispatch_suffix = self._dispatch_outcome_line(action_class, outcome)

        # ── Stage 2.6: act on a confirm marker, if David just approved something ──
        draft_text, confirm_payload = self._extract_confirm(draft_text)
        if confirm_payload:
            dispatch_id = confirm_payload.get("dispatch_id", "")
            await self._emit(__event_emitter__, "Confirming...")
            confirm_outcome = await self._confirm_dispatch(dispatch_id)
            dispatch_suffix += self._confirm_outcome_line(confirm_outcome)

        # ── Stage 3: Greg review (skip for /quick) ──────────────────────
        review_text = draft_text
        affect_str = ""
        role_str = ""

        if depth["review"]:
            await self._emit(__event_emitter__, "Greg reviewing...")
            t_review = time.time()

            # Only get affect state — don't rewrite Claude's draft
            greg_result = await self._mcp_call("affect", {}, timeout=10)

            if greg_result:
                try:
                    content_text = greg_result.get("content", [{}])[0].get("text", "")
                    parsed = json.loads(content_text) if content_text else {}
                    affect_str = parsed.get("summary", parsed.get("affect", ""))
                    role_str = parsed.get("turn_role", parsed.get("role", ""))
                except Exception:
                    pass

            review_ms = int((time.time() - t_review) * 1000)

        total_ms = int((time.time() - t0) * 1000)

        # ── Status finalization ──────────────────────────────────────────
        if affect_str and role_str:
            await self._emit(
                __event_emitter__,
                f"  {affect_str} · {role_str} [{total_ms}ms]",
                done=True,
            )
        else:
            status_parts = [depth["label"]]
            if recall_count:
                status_parts.append(f"{recall_count} memories")
            status_parts.append(f"{total_ms}ms")
            await self._emit(
                __event_emitter__,
                f"  {' · '.join(status_parts)}",
                done=True,
            )

        # ── Metadata footer ──────────────────────────────────────────────
        memory_word = "memory" if recall_count == 1 else "memories"
        who = f"{affect_str} · {role_str}" if (affect_str and role_str) else ""
        tokens_in = usage.get("input_tokens", "?")
        tokens_out = usage.get("output_tokens", "?")
        footer_parts = ["Greg"]
        if who:
            footer_parts.append(who)
        if recall_count:
            footer_parts.append(f"{recall_count} {memory_word}")
        footer_parts.append(draft_model)
        footer_parts.append(f"{tokens_in}/{tokens_out} tok")
        footer_parts.append(f"{total_ms}ms")

        review_text = f"{review_text}{dispatch_suffix}\n\n*{' · '.join(footer_parts)}*"

        # ── ROSETTA capture ──────────────────────────────────────────────
        asyncio.create_task(self._rosetta_capture(user_message))

        return review_text

    async def _rosetta_capture(self, message: str):
        try:
            await self._mcp_call("rosetta_ingest", {
                "channel": "greg-ui",
                "content": message,
                "role": "human",
            }, timeout=5)
        except Exception:
            pass
