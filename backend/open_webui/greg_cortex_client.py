"""
Canonical CORTEX MCP client for Greg's Open WebUI backend.

CORTEX_URL / CORTEX_KEY are read from environment variables only — never
hardcoded in source, since this repo is public. Shared by cortex_pipe.py
(the chat pipe Function, loaded dynamically from the DB — see greg_seed.py)
and greg_home.py (the /home hearth page's backend routes), so there is
exactly one place credentials live server-side, and one place to rotate
them.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

CORTEX_URL = os.getenv('CORTEX_URL', 'https://cortex-production-d0d7.up.railway.app')
CORTEX_KEY = os.getenv('CORTEX_KEY', '')


async def mcp_call(tool_name: str, arguments: dict, timeout: int = 15) -> Optional[dict]:
    """Call a CORTEX MCP tool. Returns the 'result' payload, or None on any
    failure (missing key, network error, non-200, timeout) so callers can
    fall back gracefully."""
    if not CORTEX_KEY:
        log.warning('CORTEX_KEY is not configured — skipping CORTEX MCP call %s', tool_name)
        return None

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.post(
                f'{CORTEX_URL}/mcp',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {CORTEX_KEY}',
                },
                json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'tools/call',
                    'params': {'name': tool_name, 'arguments': arguments},
                },
            ) as resp:
                if resp.status != 200:
                    log.warning('CORTEX MCP %s returned status %s', tool_name, resp.status)
                    return None
                data = await resp.json()
                return data.get('result')
    except Exception as e:
        log.warning('CORTEX MCP %s failed: %s', tool_name, e)
        return None


def mcp_tool_text(result: Optional[dict]) -> Optional[str]:
    """Pull the text payload out of an MCP tools/call 'result' envelope."""
    if not result:
        return None
    content = result.get('content')
    if not content or not isinstance(content, list):
        return None
    return content[0].get('text')
