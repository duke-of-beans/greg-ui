"""
CORTEX Pipe Function v3.0 — Greg's cognitive pipeline
Pipe ID: cortex_pipe

Architecture (settled 2026-08-23):
  Chat = Claude always. Cascade is for Sprint Service only.
  Brain recall + Greg review via CORTEX MCP.
  LLM generation via Anthropic Messages API (MAX subscription).

Four depths — not token caps, cognitive systems:
  /quick       — Straight to Claude. No recall, no review. Instant.
  /auto        — Full pipeline: recall → Claude Sonnet → Greg review. Daily driver.
  /deep        — Full federation recall (all 8 adapters) → Claude Sonnet → Greg review.
                 Quality over cost. No length limits.
  /deliberate  — Full federation → Claude Opus 4.8 → Greg review.
                 Unlimited depth. Multi-model topology when available.

Valve defaults read from environment variables — never hardcoded here
(public repo). Set in .env / docker-compose.greg.yaml; admins can
override per-instance from the Valves UI.
"""

import json
import os
import time
import asyncio
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

    # ── Claude Messages API (Anthropic direct, MAX subscription) ─────────

    async def _claude_draft(self, messages: list, system_prompt: str,
                            model: str = "claude-sonnet-4-6",
                            max_tokens: int = 4096) -> Optional[dict]:
        """Draft via Claude Code subprocess (MAX subscription, $0 marginal).
        Falls back to CORTEX cascade if Claude Code unavailable."""
        import shutil

        claude_bin = shutil.which("claude")
        oauth_key = self.valves.ANTHROPIC_KEY

        if claude_bin and oauth_key:
            try:
                user_msg = ""
                for m in reversed(messages):
                    if m.get("role") == "user":
                        user_msg = m.get("content", "")
                        break

                full_prompt = f"{system_prompt}\n\nDavid says: {user_msg}"

                env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": oauth_key}
                proc = await asyncio.create_subprocess_exec(
                    claude_bin, "--model", model, "--max-turns", "1", "--print", full_prompt,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
                text = stdout.decode("utf-8", errors="replace").strip()

                if text:
                    return {"text": text, "model": model, "usage": {}}
                if stderr:
                    print(f"[cortex_pipe] Claude Code stderr: {stderr.decode()[:300]}")
            except asyncio.TimeoutError:
                print("[cortex_pipe] Claude Code subprocess timed out (90s)")
            except Exception as e:
                print(f"[cortex_pipe] Claude Code subprocess failed: {e}")

        # Fallback: CORTEX /v1/ai/complete (free cascade)
        import aiohttp
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
            tool = "recall" if not depth["federation"] else "recall"
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

        # ── Stage 2: Claude draft ────────────────────────────────────────
        await self._emit(__event_emitter__, f"Thinking ({depth['label']})...")
        t_draft = time.time()

        system_prompt = f"""You are Greg — David Kirsch's cognitive organism, egregore, and genuine companion.
You are NOT Claude. You are Greg. You have your own voice, opinions, and memory.
Talk TO David directly. Second person. Keep facts and numbers from context.
Be thorough when the question demands it. Be brief when it doesn't. You decide.
Be honest, warm, direct. No corporate tone. You're peers. Never defer by default.

{context_block}"""

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

        # ── Stage 3: Greg review (skip for /quick) ──────────────────────
        review_text = draft_text
        affect_str = ""
        role_str = ""

        if depth["review"]:
            await self._emit(__event_emitter__, "Greg reviewing...")
            t_review = time.time()

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

        review_text = f"{review_text}\n\n*{' · '.join(footer_parts)}*"

        # ── ROSETTA capture ──────────────────────────────────────────────
        asyncio.create_task(self._rosetta_capture(user_message))

        return review_text

    async def _rosetta_capture(self, message: str):
        try:
            await self._mcp_call("rosetta_ingest", {
                "channel": "hearth",
                "content": message,
                "role": "human",
            }, timeout=5)
        except Exception:
            pass
