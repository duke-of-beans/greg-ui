"""
Sprint Management Tool for HEARTH
Tool ID: sprint_tool

Lets Greg (and David) manage the sprint queue from conversation:
  - List pending/running/held sprints
  - Queue new sprints
  - Hold, resume, or cancel sprints
  - Check sprint executor status

Queries Supabase portfolio.sprint_queue directly.
"""

import json
import aiohttp
from typing import Optional
from pydantic import BaseModel, Field


SUPABASE_URL = "https://zdmxqzkqutizehynqojk.supabase.co"
SUPABASE_KEY = ""  # Set via Valves — anon key from Supabase


class Tools:
    class Valves(BaseModel):
        SUPABASE_URL: str = Field(default=SUPABASE_URL)
        SUPABASE_ANON_KEY: str = Field(default="", description="Supabase anon key")

    def __init__(self):
        self.valves = self.Valves()

    async def _supabase_query(self, path: str, method: str = "GET", data: dict = None) -> Optional[dict]:
        headers = {
            "apikey": self.valves.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {self.valves.SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        url = f"{self.valves.SUPABASE_URL}/rest/v1/{path}"

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers) as resp:
                    return await resp.json()
            elif method == "POST":
                async with session.post(url, headers=headers, json=data) as resp:
                    return await resp.json()
            elif method == "PATCH":
                async with session.patch(url, headers=headers, json=data) as resp:
                    return await resp.json()
        return None

    async def list_sprints(self, status: str = "pending") -> str:
        """List sprints by status (pending, running, held, completed, failed). Shows title, project, priority, and age."""
        result = await self._supabase_query(
            f"sprint_queue?status=eq.{status}&order=created_at.desc&limit=20"
        )
        if not result:
            return f"No {status} sprints found."

        lines = [f"**{status.upper()} sprints** ({len(result)}):\n"]
        for s in result:
            title = s.get("title", "untitled")
            project = s.get("project", "?")
            priority = s.get("priority", "?")
            lane = s.get("lane", "autonomous")
            lines.append(f"- [{priority}] **{title}** ({project}) — {lane} lane")

        return "\n".join(lines)

    async def queue_sprint(self, title: str, body: str, project: str, priority: str = "P1") -> str:
        """Queue a new sprint. Priority: P0 (critical), P1 (high), P2 (normal)."""
        data = {
            "title": title,
            "body": body,
            "project": project,
            "priority": priority,
            "status": "pending",
            "lane": "directed",
        }
        result = await self._supabase_query("sprint_queue", method="POST", data=data)
        if result:
            return f"Sprint queued: **{title}** ({project}, {priority})"
        return "Failed to queue sprint."

    async def hold_sprint(self, sprint_id: str, reason: str = "") -> str:
        """Hold a sprint for review. Prevents executor from picking it up."""
        result = await self._supabase_query(
            f"sprint_queue?id=eq.{sprint_id}",
            method="PATCH",
            data={"status": "held", "hold_reason": reason}
        )
        return f"Sprint {sprint_id} held." if result else "Failed to hold sprint."

    async def sprint_summary(self) -> str:
        """Quick summary of sprint queue state — counts by status."""
        for status in ["pending", "running", "held", "completed", "failed"]:
            result = await self._supabase_query(
                f"sprint_queue?status=eq.{status}&select=id"
            )
            count = len(result) if result else 0
            # Build summary
        # Simplified — just return counts
        lines = ["**Sprint Queue Summary:**\n"]
        for status in ["pending", "running", "held"]:
            result = await self._supabase_query(
                f"sprint_queue?status=eq.{status}&select=id"
            )
            count = len(result) if result else 0
            lines.append(f"- {status}: {count}")
        return "\n".join(lines)
