"""Settings resolved from the environment, with working defaults."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)

# The global prefix lets Bedrock route to whichever region has capacity.
DEFAULT_MODEL_ID: Final = "global.anthropic.claude-sonnet-4-6"
DEFAULT_REGION: Final = "us-west-2"
DEFAULT_TEMPERATURE: Final = 0.2
DEFAULT_HTTP_TIMEOUT: Final = 8.0
DEFAULT_CITY: Final = "Karachi"
DEFAULT_PRAYER_METHOD: Final = 1

USER_AGENT: Final = "karachi-city-agent/0.1 (+https://github.com/amaanx86/give-your-ai-hands)"


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable settings snapshot."""

    model_id: str = DEFAULT_MODEL_ID
    region: str = DEFAULT_REGION
    temperature: float = DEFAULT_TEMPERATURE
    http_timeout: float = DEFAULT_HTTP_TIMEOUT
    default_city: str = DEFAULT_CITY
    prayer_method: int = DEFAULT_PRAYER_METHOD

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Read settings from the environment."""
        source = os.environ if env is None else env
        return cls(
            model_id=source.get("KARACHI_AGENT_MODEL_ID") or DEFAULT_MODEL_ID,
            # AgentCore Runtime injects AWS_REGION, so the explicit override wins.
            region=(
                source.get("KARACHI_AGENT_REGION")
                or source.get("AWS_REGION")
                or source.get("AWS_DEFAULT_REGION")
                or DEFAULT_REGION
            ),
            temperature=_env_float(source, "KARACHI_AGENT_TEMPERATURE", DEFAULT_TEMPERATURE),
            http_timeout=_env_float(source, "KARACHI_AGENT_HTTP_TIMEOUT", DEFAULT_HTTP_TIMEOUT),
            default_city=source.get("KARACHI_AGENT_DEFAULT_CITY") or DEFAULT_CITY,
            prayer_method=_env_int(source, "KARACHI_AGENT_PRAYER_METHOD", DEFAULT_PRAYER_METHOD),
        )


def _env_float(env: Mapping[str, str], key: str, fallback: float) -> float:
    raw = env.get(key)
    if not raw:
        return fallback
    try:
        return float(raw)
    except ValueError:
        logger.warning("Ignoring non-numeric %s=%r, using %s", key, raw, fallback)
        return fallback


def _env_int(env: Mapping[str, str], key: str, fallback: int) -> int:
    raw = env.get(key)
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError:
        logger.warning("Ignoring non-integer %s=%r, using %s", key, raw, fallback)
        return fallback


_SETTINGS: Settings | None = None


def settings() -> Settings:
    """Return the process-wide settings, reading the environment once."""
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings.from_env()
    return _SETTINGS
