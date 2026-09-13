"""
Canonical greg-backend (Railway executor) REST client for Greg's Open WebUI
backend.

Sprint 10 (Capacity Governor + Sprint Control Surface). GREG_BACKEND_API_URL /
GREG_BACKEND_API_KEY are read from environment variables only — never
hardcoded in source, since this repo is public. Mirrors greg_cortex_client.py's
pattern: exactly one place these credentials live server-side, exactly one
place to rotate them.

Renamed 2026-09-13 from GREG_HOME_API_URL/KEY (this repo, greg-backend, and
GregLite were all "Home" or "Hearth" at various points — none of those names
were ever approved; David: "no homes or hearths survive").

NOTE (2026-08-20): as of this writing, greg-backend's /api/surface/* routes
do not check GREG_BACKEND_API_KEY yet — that check needs to be added on the
greg-backend side (see HOME_CAPACITY_INTEGRATION.md §6b in that repo, drafted
separately since it was mid-sprint when this was written). This client sends
the header regardless, so no code change is needed here once that lands.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

BACKEND_API_URL = os.getenv('GREG_BACKEND_API_URL', 'https://executor-production-f8aa.up.railway.app')
BACKEND_API_KEY = os.getenv('GREG_BACKEND_API_KEY', '')


async def home_api_call(
    method: str,
    path: str,
    json_body: Optional[dict] = None,
    timeout: int = 15,
) -> Optional[dict]:
    """Call a greg-backend /api/surface/* REST endpoint. Returns the parsed
    JSON body, or None on any failure (network error, non-200, timeout) so
    callers can fall back gracefully — same contract as
    greg_cortex_client.mcp_call(). Function name kept as home_api_call for
    now (see the router that calls this) -- the client and its variable
    names are renamed here; the call-site rename is a separate, larger pass
    tracked alongside the /home route path itself."""
    headers = {'Content-Type': 'application/json'}
    if BACKEND_API_KEY:
        headers['X-Home-Api-Key'] = BACKEND_API_KEY

    url = f'{BACKEND_API_URL}{path}'
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.request(method, url, headers=headers, json=json_body) as resp:
                if resp.status != 200:
                    log.warning('greg-backend API %s %s returned status %s', method, path, resp.status)
                    return None
                return await resp.json()
    except Exception as e:
        log.warning('greg-backend API %s %s failed: %s', method, path, e)
        return None
