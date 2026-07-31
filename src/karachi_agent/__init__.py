"""A Karachi city agent with three live-data tools."""

from __future__ import annotations

from .agent import build_agent, build_model, tool_specs
from .config import Settings, settings
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS, get_air_quality, get_prayer_times, get_weather

__version__ = "0.1.0"

__all__ = [
    "ALL_TOOLS",
    "SYSTEM_PROMPT",
    "Settings",
    "__version__",
    "build_agent",
    "build_model",
    "get_air_quality",
    "get_prayer_times",
    "get_weather",
    "settings",
    "tool_specs",
]
