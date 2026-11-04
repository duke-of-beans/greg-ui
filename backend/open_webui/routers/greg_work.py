"""
Gregore work panel backend (Gregore-private docs/GREGORE_WORK_PANEL_SPEC.md).

The right-hand panel in a chat shows the work orders that chat started and where each one is, proven by order events.
The browser never talks to CORTEX: these two routes forward to CORTEX's owner-only work endpoints with the server-side
CORTEX_KEY (greg_cortex_client.py), the same posture as greg_home.py.

  GET /api/v1/greg/work/chat?id=<chat id>             -> CORTEX GET /v1/work/chat (that chat's orders as panel cards)
  GET /api/v1/greg/work/events?chat=<chat id>&since=  -> CORTEX GET /v1/work/orders/events (Server-Sent Events, passed through)

Admin only: the panel shows David's portfolio work.
"""

from __future__ import annotations

import logging
import re
from typing import AsyncIterator, Optional

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from open_webui.greg_cortex_client import CORTEX_KEY, CORTEX_URL
from open_webui.utils.auth import get_admin_user

log = logging.getLogger(__name__)

router = APIRouter()

# CORTEX_URL is set to the MCP endpoint on Sentinel (docker-compose.greg.yaml default: .../mcp). The work routes live at the
# service root, so use the root whether or not the configured URL ends in /mcp.
CORTEX_BASE = re.sub(r'/mcp/?$', '', CORTEX_URL.rstrip('/'))

MAX_CHAT_ID = 200


def _chat_id(raw: Optional[str]) -> str:
    chat = (raw or '').strip()
    if not chat or len(chat) > MAX_CHAT_ID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='a chat id (1-200 characters) is required')
    return chat


def _headers(extra: Optional[dict] = None) -> dict:
    if not CORTEX_KEY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='CORTEX_KEY is not configured')
    return {'Authorization': f'Bearer {CORTEX_KEY}', **(extra or {})}


@router.get('/work/chat')
async def get_chat_work(id: str, user=Depends(get_admin_user)):
    """One chat's orders as panel cards. Upstream errors come back as 502 with CORTEX's message, never as an empty panel."""
    chat = _chat_id(id)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(f'{CORTEX_BASE}/v1/work/chat', params={'id': chat}, headers=_headers()) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200:
                    detail = (body or {}).get('error') if isinstance(body, dict) else None
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail or f'CORTEX returned {resp.status}')
                return body
    except HTTPException:
        raise
    except Exception as e:
        log.warning('work panel: CORTEX /v1/work/chat failed: %s', e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='CORTEX is unreachable')


@router.get('/work/events')
async def stream_chat_work(request: Request, chat: str, since: Optional[int] = None, user=Depends(get_admin_user)):
    """Order events for one chat, live. Resumes from `since` or the browser's Last-Event-ID, like CORTEX's own feed."""
    chat_id = _chat_id(chat)
    params = {'chat': chat_id}
    if since is not None and since >= 0:
        params['since'] = str(since)
    extra = {'Accept': 'text/event-stream'}
    last_id = request.headers.get('last-event-id')
    if last_id and 'since' not in params:
        extra['Last-Event-ID'] = last_id
    headers = _headers(extra)

    # Open upstream before answering, so a refused or unreachable CORTEX is an error status, not an empty stream.
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=60))
    try:
        resp = await session.get(f'{CORTEX_BASE}/v1/work/orders/events', params=params, headers=headers)
    except Exception as e:
        await session.close()
        log.warning('work panel: CORTEX order stream failed to open: %s', e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='CORTEX is unreachable')
    if resp.status != 200:
        code = resp.status
        resp.release()
        await session.close()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f'CORTEX order stream returned {code}')

    async def relay() -> AsyncIterator[bytes]:
        try:
            # CORTEX sends a keepalive every 15s, so a 60s read timeout only trips on a dead upstream; the browser's
            # EventSource then reconnects with Last-Event-ID and loses nothing.
            async for chunk in resp.content.iter_any():
                if await request.is_disconnected():
                    break
                yield chunk
        except Exception as e:
            log.info('work panel: order stream ended: %s', e)
        finally:
            resp.release()
            await session.close()

    return StreamingResponse(
        relay(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
