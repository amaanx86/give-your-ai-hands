"""Agent assembly: a model, a prompt, and three Python functions."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from strands import Agent
from strands.models import BedrockModel

from .config import Settings, settings
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)


def build_model(config: Settings | None = None) -> BedrockModel:
    """Construct the Bedrock model provider using the standard AWS credential chain."""
    config = config or settings()
    logger.debug("Using Bedrock model %s in %s", config.model_id, config.region)
    return BedrockModel(
        model_id=config.model_id,
        region_name=config.region,
        temperature=config.temperature,
    )


def build_agent(
    config: Settings | None = None,
    *,
    tools: Sequence[Any] | None = None,
    system_prompt: str | None = None,
    model: BedrockModel | None = None,
) -> Agent:
    """Build a ready-to-invoke agent.

    Args:
        config: Settings override, defaulting to the process settings.
        tools: Tool override, for a cut-down demo.
        system_prompt: Prompt override, for comparing prompt changes live.
        model: Share one model provider across agents instead of building one
            per agent, which would mean a boto3 client per session.
    """
    config = config or settings()
    return Agent(
        model=model or build_model(config),
        system_prompt=system_prompt or SYSTEM_PROMPT,
        tools=list(tools) if tools is not None else list(ALL_TOOLS),
        # A library should not write to stdout, so the caller renders output.
        callback_handler=None,
    )


def tool_specs(tools: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    """Return the JSON tool specs Strands generated from the Python signatures."""
    specs: list[dict[str, Any]] = []
    for candidate in tools if tools is not None else ALL_TOOLS:
        spec = getattr(candidate, "tool_spec", None)
        if spec is None:
            logger.warning("Tool %r exposes no tool_spec", candidate)
            continue
        specs.append(dict(spec))
    return specs
