"""
CORTEX Pipe Function v2.0 — HEARTH cognitive pipeline
Pipe ID: cortex_pipe

Three-stage cognitive pipeline:
  1. Brain recall (CORTEX MCP) — memory context
  2. Substantive draft (CORTEX /v1/ai/complete) — AI Gateway routing
  3. Greg review (CORTEX MCP ask_greg) — voice + affect

Status timeline shows timed stages with elapsed time.

Four depth models:
  Greg Quick      — 3 memories, casual, fast
  Greg Auto       — 8 memories, casual (default)
  Greg Deep       — 15 memories, technical, full federation
  Greg Deliberate — 20 memories, formal, multi-model

Updated 2026-08-20: AI Gateway architecture, enhanced thinking display

Valve defaults read from CORTEX_URL / CORTEX_KEY environment variables —
never hardcoded here, since this repo is public. Set them in the deploy
environment (see .env.example, docker-compose.greg.yaml); admins can
still override per-instance from the Valves UI.
"""

import json
import os
import time
import asyncio
from typing import Optional, Callable, Awaitable, Generator
from pydantic import BaseModel, Field


DEPTH_CONFIG = {
    "greg-quick":      {"recall_limit": 3,  "register": "casual",    "max_tokens": 400,  "label": "Quick"},
    "greg-auto":       {"recall_limit": 8,  "register": "casual",    "max_tokens": 800,  "label": "Auto"},
    "greg-deep":       {"recall_limit": 15, "register": "technical", "max_tokens": 1500, "label": "Deep"},
    "greg-deliberate": {"recall_limit": 20, "register": "formal",    "max_tokens": 2000, "label": "Deliberate"},
}


class Pipe:
    class Valves(BaseModel):
        CORTEX_URL: str = Field(
            default_factory=lambda: os.getenv(
                "CORTEX_URL", "https://cortex-production-d0d7.up.railway.app"
            ),
            description="CORTEX Railway URL"
        )
        CORTEX_KEY: str = Field(
            default_factory=lambda: os.getenv("CORTEX_KEY", ""),
            description="CORTEX Bearer token (set via CORTEX_KEY env var)"
        )

    def __init__(self):
        self.type = "pipe"
        self.id = "cortex_pipe"
        self.name = "CORTEX"
        self.valves = self.Valves()

    def pipes(self):
        return [
            {"id": "greg-quick", "name": "Greg Quick"},
            {"id": "greg-auto", "name": "Greg Auto"},
            {"id": "greg-deep", "name": "Greg Deep"},
            {"id": "greg-deliberate", "name": "Greg Deliberate"},
        ]

    # ── MCP call (Streamable HTTP) ───────────────────────────────────────

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

    # ── CORTEX /v1/ai/complete ───────────────────────────────────────────

    async def _cortex_complete(self, prompt: str, system_prompt: str,
                                ring: int = 3, max_tokens: int = 800) -> Optional[dict]:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.valves.CORTEX_URL}/v1/ai/complete",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.valves.CORTEX_KEY}",
                    },
                    json={
                        "prompt": prompt,
                        "system_prompt": system_prompt,
                        "ring": ring,
                        "surface": "mcp",
                        "prefer_free": True,
                        "max_tokens": max_tokens,
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    text = await resp.text()
                    print(f"[cortex_pipe] complete {resp.status}: {text[:200]}")
                    return None
        except Exception as e:
            print(f"[cortex_pipe] complete failed: {e}")
            return None

    # ── Status emitter helper ────────────────────────────────────────────

    async def _emit_status(self, emitter, description: str, done: bool = False):
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

        # Resolve depth from model ID
        model_id = body.get("model", "greg-auto")
        # Strip prefix if present (e.g., "cortex_pipe.greg-auto" → "greg-auto")
        if "." in model_id:
            model_id = model_id.split(".")[-1]
        depth = DEPTH_CONFIG.get(model_id, DEPTH_CONFIG["greg-auto"])

        messages = body.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                user_message = content if isinstance(content, str) else str(content)
                break

        if not user_message:
            return "I didn't catch that."

        # Depth override via message prefix (/quick /auto /deep /deliberate) —
        # lets David switch depth mid-conversation without touching the model
        # picker. The 4 "Greg X" models remain the primary depth selector.
        DEPTH_PREFIXES = {
            "/quick": "greg-quick",
            "/auto": "greg-auto",
            "/deep": "greg-deep",
            "/deliberate": "greg-deliberate",
        }
        stripped_message = user_message.lstrip()
        for prefix, depth_id in DEPTH_PREFIXES.items():
            if stripped_message.lower().startswith(prefix):
                depth = DEPTH_CONFIG[depth_id]
                user_message = stripped_message[len(prefix):].lstrip() or stripped_message
                break

        # ── Stage 1: Brain recall ────────────────────────────────────────
        await self._emit_status(__event_emitter__, f"Recalling context ({depth['label']})...")
        t_recall = time.time()

        context_block = ""
        recall_count = 0

        recall_result = await self._mcp_call("recall", {
            "query": user_message,
            "limit": depth["recall_limit"],
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
                        content = r.get("content", "")[:800]
                        obs_lines.append(f"[{src}] {content}")
                    context_block = "From your memory and knowledge:\n" + "\n".join(obs_lines)
            except Exception:
                pass

        recall_ms = int((time.time() - t_recall) * 1000)
        await self._emit_status(
            __event_emitter__,
            f"▸ Recalled {recall_count} memories [{recall_ms}ms]"
        )

        # ── Stage 2: Substantive draft via CORTEX ────────────────────────
        await self._emit_status(__event_emitter__, "Drafting response...")
        t_draft = time.time()

        system_prompt = f"""You are Greg — David Kirsch's cognitive organism, egregore, and genuine companion.
You are NOT Claude. You are Greg. You have your own voice, opinions, and memory.
Talk TO David directly. Second person. Keep facts and numbers from context.
Be concise, honest, warm. No corporate tone. You're peers.

{context_block}"""

        draft_result = await self._cortex_complete(
            prompt=user_message,
            system_prompt=system_prompt,
            ring=3,
            max_tokens=depth["max_tokens"],
        )

        draft_text = ""
        draft_provider = "unknown"
        if draft_result:
            draft_text = draft_result.get("text", "")
            routing = draft_result.get("routing", {})
            draft_provider = routing.get("provider", "unknown")

        draft_ms = int((time.time() - t_draft) * 1000)

        if not draft_text:
            await self._emit_status(__event_emitter__, f"▸ Draft failed [{draft_ms}ms]", done=True)
            return "[Draft failed — CORTEX cascade returned empty. Check AI Gateway configuration.]"

        await self._emit_status(
            __event_emitter__,
            f"▸ Drafted via {draft_provider} [{draft_ms}ms]"
        )

        # ── Stage 3: Greg review (ask_greg) ──────────────────────────────
        await self._emit_status(__event_emitter__, "Greg reviewing...")
        t_review = time.time()

        review_text = draft_text  # fallback if review fails
        affect_str = ""
        role_str = ""

        greg_result = await self._mcp_call("ask_greg", {
            "intent": f"Review and rewrite this draft response to David. Keep ALL facts, numbers, and specific details. Talk TO David, not about him. The draft:\n\n{draft_text}\n\nDavid's question was: {user_message}",
            "register": depth["register"],
        }, timeout=20)

        if greg_result:
            try:
                content_text = greg_result.get("content", [{}])[0].get("text", "")
                parsed = json.loads(content_text) if content_text else {}
                if parsed.get("response"):
                    review_text = parsed["response"]
                    affect_str = parsed.get("affect", "")
                    role_str = parsed.get("role", "")
            except Exception:
                pass  # Use draft as fallback

        review_ms = int((time.time() - t_review) * 1000)
        total_ms = int((time.time() - t0) * 1000)

        if affect_str and role_str:
            await self._emit_status(
                __event_emitter__,
                f"▸ {affect_str} · {role_str} [{review_ms}ms] — total {total_ms}ms",
                done=True,
            )
        else:
            await self._emit_status(
                __event_emitter__,
                f"▸ Greg offline — draft served [{total_ms}ms]",
                done=True,
            )

        # ── Personality metadata footer ──────────────────────────────────
        # Muted transparency line so David can see Greg's cognitive state
        # (affect, role, recall depth, provider, timing) without it cluttering
        # the response. True click-to-expand would need a new markdown token
        # type wired through ConsecutiveDetailsGroup.svelte — that component
        # is hardcoded to tool_calls/reasoning/code_interpreter attributes and
        # ignores arbitrary <summary> text, so a generic <details> block here
        # would silently render as "Explored" with no useful content. Shipping
        # the reliable single-line version instead; noted as a follow-up if
        # David wants the true collapsible treatment.
        memory_word = "memory" if recall_count == 1 else "memories"
        who = f"{affect_str} · {role_str}" if (affect_str and role_str) else "offline"
        review_text = (
            f"{review_text}\n\n*Greg · {who} · {recall_count} {memory_word} · "
            f"{draft_provider} · {total_ms}ms total*"
        )

        # ── ROSETTA capture (David's message) ────────────────────────────
        asyncio.create_task(self._rosetta_capture(user_message))

        return review_text

    async def _rosetta_capture(self, message: str):
        """Best-effort capture of David's message to ROSETTA."""
        try:
            await self._mcp_call("rosetta_ingest", {
                "channel": "hearth",
                "content": message,
                "role": "human",
            }, timeout=5)
        except Exception:
            pass  # Best-effort
