from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from open_webui.greg_cortex_client import mcp_call, mcp_tool_text
from open_webui.greg_home_api_client import home_api_call
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()

# The /home hearth page used to call CORTEX directly from the browser with
# a hardcoded bearer token, which shipped that token in the public JS
# bundle and git history. Everything here proxies through the backend
# instead, using the same CORTEX credentials (env vars, see
# greg_cortex_client.py) as the cortex_pipe chat Function — the token
# never reaches the client.

FALLBACK_GREETINGS = {
    'morning': 'Good morning, David — here\'s what happened while you were away.',
    'midday': 'Hey.',
    'evening': 'Anything on your mind?',
    'night': "It's late.",
}


class GreetingRequest(BaseModel):
    time_mode: str
    temp: str | None = None
    condition: str | None = None


@router.post('/greeting')
async def get_greeting(form_data: GreetingRequest, user=Depends(get_verified_user)):
    """Mode + weather-aware greeting, generated via CORTEX ask_greg with a
    static per-mode fallback if CORTEX is unreachable."""
    weather_bit = ''
    if form_data.temp and form_data.condition:
        weather_bit = f', weather: {form_data.temp} {form_data.condition}'

    intent = (
        f'Generate a brief greeting for David. Time: {form_data.time_mode}{weather_bit}. '
        'Be natural, not robotic. One sentence.'
    )

    result = await mcp_call('ask_greg', {'intent': intent, 'register': 'casual'})
    text = mcp_tool_text(result)

    if not text:
        return {
            'greeting': FALLBACK_GREETINGS.get(form_data.time_mode, 'Hey.'),
            'fallback': True,
        }

    return {'greeting': text.strip(), 'fallback': False}


# Generic CORTEX MCP proxy for the rest of the /home page (desk metrics,
# while-away, murmuring, journal) and the /face kiosk page (affect,
# ask_greg). Allowlisted to the specific tools these pages need — this is
# not an open CORTEX RPC gateway.
ALLOWED_TOOLS = {'ask_greg', 'recall', 'gaps_queue', 'brain_remember', 'rosetta_ingest', 'affect'}


class McpCallRequest(BaseModel):
    tool: str
    arguments: dict = {}


@router.post('/mcp')
async def call_mcp_tool(form_data: McpCallRequest, user=Depends(get_verified_user)):
    if form_data.tool not in ALLOWED_TOOLS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Tool not allowed: {form_data.tool}')

    result = await mcp_call(form_data.tool, form_data.arguments)
    return {'text': mcp_tool_text(result)}


# ── Sprint 10: Capacity Governor + Sprint Control Surface ──
#
# Proxies to the Home (Railway executor) REST API — same reasoning as the
# CORTEX proxy above: the browser never talks to Home directly (no CORTEX-
# style bearer token to leak here, but keeping the credential and the base
# URL server-side only is the same posture). See greg_home_api_client.py.
#
# NOTE: Home's /api/home/* routes don't check an API key yet as of this
# sprint (see HOME_CAPACITY_INTEGRATION.md §6b in the Home repo) — this
# proxy sends X-Home-Api-Key regardless so no client change is needed once
# that lands.

FALLBACK_CAPACITY_STATE = {
    'cycle_start': None,
    'cycle_end': None,
    'estimated_remaining_pct': None,
    'tokens_used_by_greg': 0,
    'tokens_used_by_david': 0,
    'mode': 'unknown',
    'claude_code_enabled': None,
}


@router.get('/home/capacity')
async def get_capacity(user=Depends(get_verified_user)):
    """Capacity governor state, read from Home's desk endpoint (GET /api/home
    nests capacity_state under .desk — there is no standalone /api/home/desk
    route). Falls back to an 'unknown' state (not a fabricated 'abundant')
    if Home is unreachable, so the UI can show it honestly instead of lying
    about capacity."""
    result = await home_api_call('GET', '/api/home')
    capacity_state = (result or {}).get('desk', {}).get('capacity_state')
    if not capacity_state:
        return {'capacity_state': FALLBACK_CAPACITY_STATE, 'reachable': False}
    return {'capacity_state': capacity_state, 'reachable': True}


@router.get('/home/sprints')
async def get_sprints(user=Depends(get_verified_user)):
    """Last 5 sprints with status, for the Sprint Control Surface."""
    result = await home_api_call('GET', '/api/home/sprints')
    if not result:
        return {'sprints': [], 'reachable': False}
    return {'sprints': result.get('sprints', []), 'reachable': True}


class SprintActionRequest(BaseModel):
    sprint_id: str
    action: str  # 'hold' | 'cancel'


@router.patch('/home/sprints/action')
async def patch_sprint_action(form_data: SprintActionRequest, user=Depends(get_verified_user)):
    if form_data.action not in ('hold', 'cancel'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action must be 'hold' or 'cancel'")

    result = await home_api_call(
        'PATCH',
        '/api/home/sprints/action',
        json_body={'sprint_id': form_data.sprint_id, 'action': form_data.action},
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Home service unreachable')
    if result.get('error'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result['error'])
    return result
