"""Bedrock AgentCore Runtime entrypoint."""

from __future__ import annotations

import logging
import os
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

from .agent import build_agent, build_model
from .config import settings

logging.basicConfig(
    level=os.environ.get("KARACHI_AGENT_LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Implements the runtime contract, POST /invocations and GET /ping on port 8080.
app = BedrockAgentCoreApp()

# Built at import, not per request, so cold starts do not pay for boto3 setup.
_settings = settings()
_model = build_model(_settings)

# One agent per session, because an Agent accumulates conversation history. A
# single shared agent would leak one caller's history into another's context.
_MAX_SESSIONS = 128
_agents: OrderedDict[str, Agent] = OrderedDict()


def _agent_for(session_id: str) -> Agent:
    """Return this session's agent, evicting the least recently used past the cap."""
    existing = _agents.get(session_id)
    if existing is not None:
        _agents.move_to_end(session_id)
        return existing
    if len(_agents) >= _MAX_SESSIONS:
        evicted, _ = _agents.popitem(last=False)
        logger.info("Evicted session %s from the agent cache", evicted)
    agent = build_agent(_settings, model=_model)
    _agents[session_id] = agent
    return agent


@app.entrypoint
async def invoke(payload: dict[str, Any], context: Any = None) -> AsyncIterator[Any]:
    """Stream the agent's answer as text chunks, or one dict if the request is bad.

    Only text deltas are forwarded. Strands also emits lifecycle events carrying
    metrics and trace objects, which are internals the caller should not receive.
    """
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        yield {"error": "Request body must include a non-empty 'prompt'."}
        return

    session_id = str(getattr(context, "session_id", None) or "default-session")
    agent = _agent_for(session_id)
    logger.info("Invoking agent (session=%s, prompt_chars=%d)", session_id, len(prompt))

    async for event in agent.stream_async(prompt):
        chunk = event.get("data") if isinstance(event, dict) else None
        if chunk:
            yield chunk


if __name__ == "__main__":
    app.run()
