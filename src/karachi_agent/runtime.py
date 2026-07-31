"""Bedrock AgentCore Runtime entrypoint."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from .agent import build_agent
from .config import settings

logging.basicConfig(
    level=os.environ.get("KARACHI_AGENT_LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Implements the runtime contract, POST /invocations and GET /ping on port 8080.
app = BedrockAgentCoreApp()

# Built at import, not per request, so cold starts do not pay for boto3 setup.
_agent = build_agent(settings())


@app.entrypoint
async def invoke(payload: dict[str, Any]) -> AsyncIterator[Any]:
    """Stream the agent's answer as text chunks, or one dict if the request is bad.

    Only text deltas are forwarded. Strands also emits lifecycle events carrying
    metrics and trace objects, which are internals the caller should not receive.
    """
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        yield {"error": "Request body must include a non-empty 'prompt'."}
        return

    logger.info("Invoking agent (prompt_chars=%d)", len(prompt))
    async for event in _agent.stream_async(prompt):
        chunk = event.get("data") if isinstance(event, dict) else None
        if chunk:
            yield chunk


if __name__ == "__main__":
    app.run()
