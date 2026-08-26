"""
Sprint Management Tool for Gregore
Tool ID: sprint_tool

Lets Greg (and David) manage the sprint queue from conversation:
  - List pending/running/held sprints
  - Queue new sprints
  - Hold, resume, or cancel sprints
  - Check sprint executor status

Queries Supabase portfolio.sprint_queue via the REST API with the
Accept-Profile: portfolio header (required since sprint_queue lives in
the portfolio schema, not public). Requires the service_role key
(not anon) — set via Valves in the admin panel.
"""

import json
import aiohttp
from typing import Optional
from pydantic import BaseModel, Field


SUPABASE_URL = "https://zdmxqzkqutizehynqojk.supabase.co"


class Tools:
    class Valves(BaseModel):
        SUPABASE_URL: str = Field(default=SUPABASE_URL)
        SUPABASE_SERVICE_KEY: str = Field(
            default="",
            description="Supabase service_role key (required for portfolio schema access — anon key won't work)"
        )

    def __init__(self):
        self.valves = self.Valves()

    async def _supabase_query(self, path: str, method: str = "GET", data: dict = None) -> Optional[list | dict]:
        """Query Supabase REST API against the portfolio schema."""
        key = self.valves.SUPABASE_SERVICE_KEY
        if not key:
            return None
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
            "Accept-Profile": "portfolio",
            "Content-Profile": "portfolio",
        }
        url = f"{self.valves.SUPABASE_URL}/rest/v1/{path}"

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        return {"error": f"HTTP {resp.status}: {body[:200]}"}
                    return await resp.json()
            elif method in ("POST", "PATCH"):
                fn = session.post if method == "POST" else session.patch
                async with fn(url, headers=headers, json=data) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        return {"error": f"HTTP {resp.status}: {body[:200]}"}
                    return await resp.json()
        return None

    async def list_sprints(self, status: str = "pending") -> str:
        """List sprints by status (pending, running, completed, failed, deferred). Shows title, project, priority, and lane."""
        result = await self._supabase_query(
            f"sprint_queue?status=eq.{status}&order=created_at.desc&limit=20"
        )
        if isinstance(result, dict) and "error" in result:
            return f"Error querying sprints: {result['error']}"
        if not result:
            return f"No {status} sprints found."

        lines = [f"**{status.upper()} sprints** ({len(result)}):\n"]
        for s in result:
            title = s.get("title", "untitled")
            project = s.get("project", "?")
            priority = s.get("priority", "?")
            lane = s.get("lane", "autonomous")
            sid = s.get("sprint_id", "?")
            lines.append(f"- [{priority}] **{title}** ({project}) — {lane} lane — `{sid}`")

        return "\n".join(lines)

    async def queue_sprint(self, title: str, body: str, project: str, priority: str = "P1") -> str:
        """Queue a new sprint for the executor. Priority: P0 (critical), P1 (high), P2 (normal)."""
        import uuid
        from datetime import datetime

        sprint_id = f"GREG-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        data = {
            "sprint_id": sprint_id,
            "title": title,
            "body": body,
            "project": project,
            "priority": priority,
            "status": "pending",
            "lane": "directed",
            "tier": 2,
            "confidence": 0.8,
            "source": "gregore_tool",
            "model_preference": "sonnet",
        }
        result = await self._supabase_query("sprint_queue", method="POST", data=data)
        if isinstance(result, dict) and "error" in result:
            return f"Failed to queue sprint: {result['error']}"
        if isinstance(result, list) and len(result) > 0:
            return f"Sprint queued: **{title}** ({project}, {priority}) — `{sprint_id}`"
        return f"Sprint queued: **{title}** — `{sprint_id}`"

    async def hold_sprint(self, sprint_id: str, reason: str = "") -> str:
        """Hold a pending sprint — prevents the executor from picking it up."""
        result = await self._supabase_query(
            f"sprint_queue?sprint_id=eq.{sprint_id}&status=eq.pending",
            method="PATCH",
            data={"status": "deferred", "abort_reason": reason or "Held by Greg"}
        )
        if isinstance(result, dict) and "error" in result:
            return f"Failed to hold sprint: {result['error']}"
        return f"Sprint `{sprint_id}` held."

    async def cancel_sprint(self, sprint_id: str) -> str:
        """Cancel a pending or running sprint."""
        from datetime import datetime
        result = await self._supabase_query(
            f"sprint_queue?sprint_id=eq.{sprint_id}&status=in.(pending,running)",
            method="PATCH",
            data={
                "status": "failed",
                "abort_reason": "Cancelled by Greg",
                "abort_reason_category": "cancelled",
                "completed_at": datetime.utcnow().isoformat() + "Z",
            }
        )
        if isinstance(result, dict) and "error" in result:
            return f"Failed to cancel sprint: {result['error']}"
        return f"Sprint `{sprint_id}` cancelled."

    async def sprint_summary(self) -> str:
        """Quick summary of sprint queue state — counts by status and recent activity."""
        lines = ["**Sprint Queue Summary:**\n"]
        for status in ["running", "pending", "completed", "failed", "deferred"]:
            result = await self._supabase_query(
                f"sprint_queue?status=eq.{status}&select=sprint_id&limit=500"
            )
            count = len(result) if isinstance(result, list) else 0
            emoji = {"running": "🟢", "pending": "🔵", "completed": "✅", "failed": "❌", "deferred": "⏸️"}.get(status, "·")
            lines.append(f"- {emoji} {status}: **{count}**")

        # Recent completions
        recent = await self._supabase_query(
            "sprint_queue?status=eq.completed&order=completed_at.desc&limit=3&select=sprint_id,title,project,completed_at"
        )
        if isinstance(recent, list) and recent:
            lines.append("\n**Recent completions:**")
            for s in recent:
                lines.append(f"- {s.get('title', '?')} ({s.get('project', '?')})")

        return "\n".join(lines)
