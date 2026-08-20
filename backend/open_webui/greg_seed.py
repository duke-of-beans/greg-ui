"""
Greg function seeder — registers pipe, filter, and tools in Open WebUI's database.

Runs at container startup (called from start.sh) AFTER the database is initialized
but BEFORE uvicorn starts. Idempotent — skips functions that already exist.

This is the canonical way Greg's cognitive pipeline ships with the image.
No admin panel pasting. No manual configuration. The fork IS the product.
"""

import asyncio
import os
import sys
import time
import importlib.util
from pathlib import Path

# Add backend to path so we can import Open WebUI modules
sys.path.insert(0, str(Path(__file__).parent.parent))


GREG_FUNCTIONS_DIR = Path(__file__).parent / "greg"

# Function definitions: id → metadata
GREG_FUNCTIONS = [
    {
        "id": "cortex_pipe",
        "name": "CORTEX",
        "type": "pipe",
        "file": "cortex_pipe.py",
        "description": "Greg's cognitive pipeline — brain recall, AI Gateway draft, Greg review",
        "is_active": True,
        "is_global": False,
    },
    {
        "id": "brain_context_filter",
        "name": "Brain Context",
        "type": "filter",
        "file": "brain_context_filter.py",
        "description": "Inlet: brain.db context injection. Outlet: ROSETTA capture.",
        "is_active": True,
        "is_global": True,
    },
    {
        "id": "sprint_tool",
        "name": "Sprint Management",
        "type": "action",
        "file": "sprint_tool.py",
        "description": "List, queue, hold, and manage sprints from conversation",
        "is_active": True,
        "is_global": False,
    },
    {
        "id": "lifelog_tool",
        "name": "Lifelog",
        "type": "action",
        "file": "lifelog_tool.py",
        "description": "Journal entries, on-this-day lookback, how-long-since queries",
        "is_active": True,
        "is_global": False,
    },
]


async def seed_functions():
    """Register Greg functions in Open WebUI's database. Idempotent."""
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.functions import Function, Functions
    from sqlalchemy import select

    print("[greg-seed] Checking Greg functions...")
    seeded = 0
    updated = 0

    async with get_async_db_context() as db:
        for func_def in GREG_FUNCTIONS:
            func_file = GREG_FUNCTIONS_DIR / func_def["file"]
            if not func_file.exists():
                print(f"[greg-seed] WARNING: {func_def['file']} not found, skipping")
                continue

            content = func_file.read_text(encoding="utf-8")
            now = int(time.time())

            # Check if function exists
            result = await db.execute(
                select(Function).where(Function.id == func_def["id"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update content if changed
                if existing.content != content:
                    existing.content = content
                    existing.is_active = func_def["is_active"]
                    existing.is_global = func_def["is_global"]
                    existing.updated_at = now
                    existing.meta = {
                        "description": func_def["description"],
                        "manifest": {},
                    }
                    updated += 1
                    print(f"[greg-seed] Updated: {func_def['id']} ({func_def['name']})")
            else:
                # Create new function
                new_func = Function(
                    id=func_def["id"],
                    user_id="",  # system-created
                    name=func_def["name"],
                    type=func_def["type"],
                    content=content,
                    meta={
                        "description": func_def["description"],
                        "manifest": {},
                    },
                    is_active=func_def["is_active"],
                    is_global=func_def["is_global"],
                    updated_at=now,
                    created_at=now,
                )
                db.add(new_func)
                seeded += 1
                print(f"[greg-seed] Created: {func_def['id']} ({func_def['name']})")

        await db.commit()

    print(f"[greg-seed] Done: {seeded} created, {updated} updated, {len(GREG_FUNCTIONS) - seeded - updated} unchanged")


if __name__ == "__main__":
    asyncio.run(seed_functions())
