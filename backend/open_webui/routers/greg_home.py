from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from open_webui.greg_cortex_client import mcp_call, mcp_tool_text
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
# while-away, murmuring, journal). Allowlisted to the specific tools this
# page needs — this is not an open CORTEX RPC gateway.
ALLOWED_TOOLS = {'ask_greg', 'recall', 'gaps_queue', 'brain_remember', 'rosetta_ingest'}


class McpCallRequest(BaseModel):
    tool: str
    arguments: dict = {}


@router.post('/mcp')
async def call_mcp_tool(form_data: McpCallRequest, user=Depends(get_verified_user)):
    if form_data.tool not in ALLOWED_TOOLS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Tool not allowed: {form_data.tool}')

    result = await mcp_call(form_data.tool, form_data.arguments)
    return {'text': mcp_tool_text(result)}
