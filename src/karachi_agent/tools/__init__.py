"""The agent's three tools."""

from __future__ import annotations

from .air_quality import get_air_quality
from .prayer_times import get_prayer_times
from .weather import get_weather

# Ordered by how often the agent should reach for them.
ALL_TOOLS = [get_weather, get_air_quality, get_prayer_times]

__all__ = ["ALL_TOOLS", "get_air_quality", "get_prayer_times", "get_weather"]
