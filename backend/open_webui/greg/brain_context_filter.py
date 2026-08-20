"""
Brain Context Filter — inlet/outlet pipeline for HEARTH
Filter ID: brain_context_filter

Inlet:  Skips brain.db recall for pipe models (CORTEX pipe handles its own recall)
Outlet: Captures David's messages to ROSETTA for voice corpus + brain.db ingestion

Updated 2026-08-20

Valve defaults read from CORTEX_URL / CORTEX_KEY environment variables —
never hardcoded here, since this repo is public.
"""

import json
import os
import asyncio
from typing import Optional, Callable, Awaitable
from pydantic import BaseModel, Field


PIPE_MODEL_PREFIXES = ["cortex_pipe.", "greg-"]


class Filter:
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
        self.type = "filter"
        self.id = "brain_context_filter"
        self.name = "Brain Context"
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
    ) -> dict:
        """Skip brain context injection for pipe models — they handle their own recall."""
        model = body.get("model", "")
        is_pipe = any(model.startswith(prefix) for prefix in PIPE_MODEL_PREFIXES)

        if is_pipe:
            # Pipe function does its own CORTEX recall — don't double up
            return body

        # For non-pipe models, inject brain.db context into system prompt
        messages = body.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                user_message = content if isinstance(content, str) else str(content)
                break

        if user_message:
            context = await self._recall(user_message)
            if context and messages:
                # Prepend context to system message
                system_msg = {"role": "system", "content": context}
                body["messages"] = [system_msg] + messages

        return body

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
    ) -> dict:
        """Capture David's messages to ROSETTA on every response.

        Skipped for pipe models (cortex_pipe.*, greg-*): cortex_pipe.py
        captures David's message itself at the start of its own pipe(),
        because Open WebUI does not reliably call outlet() for pipe-model
        responses. Capturing here too would double-ingest into ROSETTA for
        every HEARTH chat turn.
        """
        model = body.get("model", "")
        if any(model.startswith(prefix) for prefix in PIPE_MODEL_PREFIXES):
            return body

        # Only capture admin (David) messages, not Greg's
        if __user__ and __user__.get("role") == "admin":
            messages = body.get("messages", [])
            # Find the last user message
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str) and content.strip():
                        asyncio.create_task(self._rosetta_ingest(content))
                    break
        return body

    async def _recall(self, query: str, limit: int = 8) -> Optional[str]:
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
                        "jsonrpc": "2.0", "id": 1,
                        "method": "tools/call",
                        "params": {"name": "recall", "arguments": {"query": query, "limit": limit}},
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    result = data.get("result", {})
                    content_text = result.get("content", [{}])[0].get("text", "")
                    parsed = json.loads(content_text) if content_text else {}
                    results = parsed.get("results", [])
                    if results:
                        lines = [f"[{r.get('source', '?')}] {r.get('content', '')[:500]}" for r in results]
                        return "Context from brain.db:\n" + "\n".join(lines)
                    return None
        except Exception:
            return None

    async def _rosetta_ingest(self, message: str):
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self.valves.CORTEX_URL}/mcp",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.valves.CORTEX_KEY}",
                    },
                    json={
                        "jsonrpc": "2.0", "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "rosetta_ingest",
                            "arguments": {"channel": "hearth", "content": message, "role": "human"},
                        },
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception:
            pass
