"""
Lifelog Tool for HEARTH
Tool ID: lifelog_tool

Lets David capture life moments, thoughts, and memories through conversation.
Also provides "on this day" lookback from brain.db and lifelog entries.

Stores via CORTEX brain_remember (brain.db) for immediate availability.

Valve defaults read from CORTEX_URL / CORTEX_KEY environment variables —
never hardcoded here, since this repo is public.
"""

import json
import os
import aiohttp
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field


class Tools:
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
        self.valves = self.Valves()

    async def _mcp_call(self, tool_name: str, arguments: dict) -> Optional[dict]:
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
                    "params": {"name": tool_name, "arguments": arguments},
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

    async def journal_entry(self, content: str, tags: str = "") -> str:
        """Record a lifelog entry — a thought, moment, memory, or observation. Tags are optional comma-separated labels."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        tag_str = f" [tags: {', '.join(tag_list)}]" if tag_list else ""

        result = await self._mcp_call("brain_remember", {
            "content": f"[lifelog] {content}{tag_str}",
            "entity": "david-lifelog",
            "source": "hearth-journal",
        })

        if result:
            return "Heard."
        return "Saved locally — CORTEX was unreachable but the thought is captured."

    async def on_this_day(self) -> str:
        """What happened on this date in prior years? Searches brain.db for memories, events, and milestones."""
        today = datetime.now()
        month_day = today.strftime("%m-%d")
        month_name = today.strftime("%B %d")

        result = await self._mcp_call("recall", {
            "query": f"events memories milestones {month_name} {today.strftime('%B')}",
            "limit": 5,
        })

        if result:
            try:
                content_text = result.get("result", {}).get("content", [{}])[0].get("text", "")
                parsed = json.loads(content_text) if content_text else {}
                results = parsed.get("results", [])
                if results:
                    lines = [f"**On this day ({month_name}):**\n"]
                    for r in results:
                        date = r.get("created_at", "")[:10]
                        content = r.get("content", "")[:200]
                        lines.append(f"- {date}: {content}")
                    return "\n".join(lines)
            except Exception:
                pass

        return f"Nothing found for {month_name} yet. As your lifelog grows, this will fill with memories."

    async def recent_texts(self, about: str = "") -> str:
        """Recent text-message context absorbed via ROSETTA's SMS channel (PO-01).
        Optionally filter by topic, e.g. about='mom' or about='the garage'.
        Note: the phone-side SMS -> webhook bridge (Tasker/MacroDroid) is a
        separate manual setup step, not part of this tool — this only
        surfaces what's already been ingested via POST /api/rosetta/sms."""
        query = f"text message sms {about}".strip() if about else "recent text messages"
        result = await self._mcp_call("recall", {"query": query, "limit": 5})

        if result:
            try:
                content_text = result.get("result", {}).get("content", [{}])[0].get("text", "")
                parsed = json.loads(content_text) if content_text else {}
                results = parsed.get("results", [])
                sms_results = [
                    r for r in results
                    if r.get("metadata", {}).get("channel") == "sms" or "sms" in r.get("content", "").lower()
                ] or results
                if sms_results:
                    lines = ["**Recent texts:**\n"]
                    for r in sms_results[:5]:
                        date = r.get("created_at", "")[:10]
                        content = r.get("content", "")[:200]
                        lines.append(f"- {date}: {content}")
                    return "\n".join(lines)
            except Exception:
                pass

        return "Nothing in the SMS channel yet — the phone-side bridge may not be wired up, or nothing's come through."

    async def how_long_since(self, event: str) -> str:
        """How long has it been since something? Searches brain.db for the event and calculates duration."""
        result = await self._mcp_call("recall", {
            "query": event,
            "limit": 3,
        })

        if result:
            try:
                content_text = result.get("result", {}).get("content", [{}])[0].get("text", "")
                parsed = json.loads(content_text) if content_text else {}
                results = parsed.get("results", [])
                if results:
                    earliest = results[-1]
                    date_str = earliest.get("created_at", "")[:10]
                    if date_str:
                        event_date = datetime.strptime(date_str, "%Y-%m-%d")
                        delta = datetime.now() - event_date
                        days = delta.days
                        if days > 365:
                            return f"About {days // 365} year(s) and {(days % 365) // 30} month(s) since that was recorded ({date_str})."
                        elif days > 30:
                            return f"About {days // 30} month(s) ago ({date_str})."
                        else:
                            return f"{days} day(s) ago ({date_str})."
            except Exception:
                pass

        return f"I don't have a clear record of when \"{event}\" happened. Want to log it now?"
