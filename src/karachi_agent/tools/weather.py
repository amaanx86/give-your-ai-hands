"""Current weather, via open-meteo."""

from __future__ import annotations

import logging
from typing import Any, Final

from strands import tool

from ..config import settings
from ..errors import ToolExecutionError, UpstreamError, failure_from
from ..geo import resolve_city
from ..http import get_json
from .scales import describe_weather_code

logger = logging.getLogger(__name__)

FORECAST_URL: Final = "https://api.open-meteo.com/v1/forecast"
SOURCE: Final = "open-meteo forecast"

_CURRENT_FIELDS: Final = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "weather_code",
    "wind_speed_10m",
    "precipitation",
)


@tool
def get_weather(city: str = "Karachi") -> dict[str, Any]:
    """Get the current weather for a city.

    Use this for anything about temperature, how hot or humid it feels, wind,
    rain right now, or whether it is a good time to be outside. Returns a live
    reading, not a forecast.

    Args:
        city: City name, e.g. "Karachi", "Lahore", "Hyderabad". Defaults to
            Karachi when the user does not name a city.

    Returns:
        On success, a mapping with ``ok: true``, the resolved place, the
        observation's local timestamp, and: ``temperature_c``, ``feels_like_c``,
        ``humidity_pct``, ``wind_kph``, ``precipitation_mm``, and a plain-language
        ``condition``. On failure, ``ok: false`` and an ``error`` describing what
        went wrong, which you should report rather than guessing a value.
    """
    config = settings()
    try:
        place = resolve_city(city or config.default_city, timeout=config.http_timeout)
        payload = get_json(
            FORECAST_URL,
            {
                "latitude": place.latitude,
                "longitude": place.longitude,
                "current": ",".join(_CURRENT_FIELDS),
                "timezone": place.timezone,
                "wind_speed_unit": "kmh",
            },
            timeout=config.http_timeout,
            source=SOURCE,
        )
    except ToolExecutionError as exc:
        logger.info("get_weather(%r) failed: %s", city, exc)
        return failure_from(exc)

    current = payload.get("current")
    if not isinstance(current, dict):
        return failure_from(
            UpstreamError("response had no `current` block", kind="bad_payload", source=SOURCE)
        )

    return {
        "ok": True,
        "city": place.name,
        "country": place.country,
        "timezone": place.timezone,
        "observed_at": current.get("time"),
        "condition": describe_weather_code(_as_int(current.get("weather_code"))),
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "wind_kph": current.get("wind_speed_10m"),
        "precipitation_mm": current.get("precipitation"),
        "source": SOURCE,
        **({"coordinates_are_approximate": True} if place.approximate else {}),
    }


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
