"""
Greg function seeder — registers pipe, filter, and tools in Open WebUI's database.

Runs at container startup (called from start.sh) AFTER the database is initialized
but BEFORE uvicorn starts. Idempotent — skips functions that already exist.

This is the canonical way Greg's cognitive pipeline ships with the image.
No admin panel pasting. No manual configuration. The fork IS the product.

The pipe (cortex_pipe) is CREATE-ONLY. Once its row exists, ops/open-webui/install_pipe.py
(Gregore-private) is its only writer. The copy baked into the image is just a first-install
bootstrap and goes stale, so overwriting the row from it on every start silently reverted
the live pipe (2026-10-02: v6.44 -> v6.11 on a container recreate).
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
# create_only: never touch the row once it exists (something else owns its content).
GREG_FUNCTIONS = [
    {
        "id": "cortex_pipe",
        "name": "CORTEX",
        "type": "pipe",
        "file": "cortex_pipe.py",
        "description": "Greg's cognitive pipeline — brain recall, AI Gateway draft, Greg review",
        "is_active": True,
        "is_global": False,
        "create_only": True,
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



# Community plugins, vendored after a source read (see greg/community/README.md for source commit and review notes).
# keep_settings: on a content change only the code is updated, so toggles David makes in the admin panel survive.
COMMUNITY_DIR = GREG_FUNCTIONS_DIR / "community"


def _community(id, name, type, description, is_active=True, is_global=False):
    return {
        "id": id,
        "name": name,
        "type": type,
        "file": f"community/{id}.py",
        "description": description,
        "is_active": is_active,
        "is_global": is_global,
        "keep_settings": True,
    }


GREG_FUNCTIONS += [
    _community("smart_mind_map", "Smart Mind Map", "action", "Turn a reply into an interactive mind map", is_global=True),
    _community("infographic", "Smart Infographic", "action", "Turn a reply into an infographic", is_global=True),
    _community("deep_dive", "Deep Dive", "action", "Structured deep dive on a reply's topic", is_global=True),
    _community("export_word", "Export to Word", "action", "Export a reply to .docx", is_global=True),
    _community("export_excel", "Export to Excel", "action", "Export a reply's tables to .xlsx", is_global=True),
    _community("token_usage", "Token Usage", "filter", "Token count and cost under each reply", is_global=True),
    _community("markdown_normalizer", "Markdown Normalizer", "filter", "Repairs broken markdown in model output"),
    _community("clean_thinking", "Clean Thinking Tags", "filter", "Strips leaked thinking tags from replies"),
    _community("folder_memory", "Folder Memory", "filter", "Keeps a folder's shared facts in its system prompt"),
    _community("vision_bridge", "Vision Bridge", "filter", "Describes images for models that cannot see"),
    _community("doodle_paint", "Doodle Paint", "filter", "Sketch-to-image canvas"),
    # Pipes appear as models: off until configured.
    _community("planner_v3", "Planner Agent", "pipe", "Multi-step planner agent", is_active=False),
    _community("mopidy", "Mopidy", "pipe", "Music control for a Mopidy server", is_active=False),
]

# Tools live in their own table and need their specs computed from the module, as the admin "create tool" route does.
GREG_TOOLS = [
    ("mcp_app_bridge", "MCP App Bridge", "Interactive MCP app UIs inline in chat (needs an MCP server URL valve)"),
    ("inline_visualizer", "Inline Visualizer", "Interactive HTML/SVG visuals inline in chat"),
    ("email_composer", "Email Composer", "Drafts an email card with copy and mailto"),
    ("smart_mind_map_tool", "Smart Mind Map", "Mind maps the model can draw on its own"),
    ("outagedeck", "OutageDeck", "Live status of public services"),
    ("youtube", "YouTube", "Search and embed YouTube videos (needs an API key valve)"),
    ("weather", "Weather", "OpenWeatherMap forecast widget (needs an API key valve)"),
    ("model_3d_viewer", "3D Model Viewer", "Render 3D models inline"),
    ("jellyfin", "Jellyfin", "Browse and play from a Jellyfin server (needs URL and key valves)"),
]


async def seed_tools():
    """Register community tools in the Tool table. Idempotent; content updates keep valves and grants."""
    from open_webui.models.tools import ToolForm, ToolMeta, Tools
    from open_webui.models.users import Users
    from open_webui.utils.plugin import load_tool_module_by_id
    from open_webui.utils.tools import get_tool_specs

    owner = await Users.get_super_admin_user()
    if owner is None:
        print("[greg-seed] Tools skipped: no admin user yet")
        return

    for tool_id, name, description in GREG_TOOLS:
        path = COMMUNITY_DIR / f"{tool_id}.py"
        if not path.exists():
            print(f"[greg-seed] WARNING: community/{tool_id}.py not found, skipping")
            continue
        content = path.read_text(encoding="utf-8")
        existing = await Tools.get_tool_by_id(tool_id)
        if existing and existing.content == content:
            continue
        try:
            # Same steps as the admin create/update tool routes (routers/tools.py): load, read specs, write with history.
            module, frontmatter, _source = await load_tool_module_by_id(tool_id, content=content)
            specs = get_tool_specs(module)
            meta = ToolMeta(description=description, manifest=frontmatter, has_user_valves=hasattr(module, "UserValves"))
            if existing:
                await Tools.update_tool_by_id(
                    tool_id,
                    {"content": content, "specs": specs, "meta": meta.model_dump(), "commit_message": "greg-seed update"},
                    user_id=owner.id,
                    module=module,
                )
                print(f"[greg-seed] Updated tool: {tool_id}")
            else:
                form = ToolForm(id=tool_id, name=name, content=content, meta=meta, access_grants=[], commit_message="greg-seed")
                await Tools.insert_new_tool(owner.id, form, specs, module=module)
                print(f"[greg-seed] Created tool: {tool_id}")
        except Exception as e:
            # One broken plugin must not stop the container from starting.
            print(f"[greg-seed] Tool {tool_id} failed to load: {e}")


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
                if func_def.get("create_only"):
                    # Owned by install_pipe.py; never overwrite from the image copy.
                    continue
                # Update content if changed
                if existing.content != content:
                    existing.content = content
                    if not func_def.get("keep_settings"):
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


async def main():
    await seed_functions()
    await seed_tools()


if __name__ == "__main__":
    asyncio.run(main())
