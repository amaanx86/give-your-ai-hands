"""Current air quality, via open-meteo."""

from __future__ import annotations

import logging
from typing import Any, Final

from strands import tool

from ..config import settings
from ..errors import ToolExecutionError, UpstreamError, failure_from
from ..geo import resolve_city
from ..http import get_json
from .scales import band_us_aqi

logger = logging.getLogger(__name__)

AIR_QUALITY_URL: Final = "https://air-quality-api.open-meteo.com/v1/air-quality"
SOURCE: Final = "open-meteo air-quality"

_CURRENT_FIELDS: Final = (
    "us_aqi",
    "pm2_5",
    "pm10",
    "nitrogen_dioxide",
    "ozone",
    "carbon_monoxide",
)


@tool
def get_air_quality(city: str = "Karachi") -> dict[str, Any]:
    """Get the current air quality for a city.

    Use this for questions about pollution, smog, AQI, haze, whether the air is
    safe to exercise or walk in, or whether someone with asthma should go out.
    Returns a live reading.

    Args:
        city: City name, e.g. "Karachi", "Lahore". Defaults to Karachi when the
            user does not name a city.

    Returns:
        On success, a mapping with ``ok: true``, the resolved place, and:
        ``us_aqi`` (0-500+), ``category`` (Good through Hazardous), ``guidance``
        (what a person should actually do), plus ``pm2_5``, ``pm10``,
        ``nitrogen_dioxide``, ``ozone`` and ``carbon_monoxide`` in ug/m3. Prefer
        quoting ``category`` and ``guidance`` over raw concentrations. On failure,
        ``ok: false`` and an ``error``, so never estimate an AQI yourself.
    """
    config = settings()
    try:
        place = resolve_city(city or config.default_city, timeout=config.http_timeout)
        payload = get_json(
            AIR_QUALITY_URL,
            {
                "latitude": place.latitude,
                "longitude": place.longitude,
                "current": ",".join(_CURRENT_FIELDS),
                "timezone": place.timezone,
            },
            timeout=config.http_timeout,
            source=SOURCE,
        )
    except ToolExecutionError as exc:
        logger.info("get_air_quality(%r) failed: %s", city, exc)
        return failure_from(exc)

    current = payload.get("current")
    if not isinstance(current, dict):
        return failure_from(
            UpstreamError("response had no `current` block", kind="bad_payload", source=SOURCE)
        )

    us_aqi = _as_float(current.get("us_aqi"))
    category, guidance = band_us_aqi(us_aqi)

    return {
        "ok": True,
        "city": place.name,
        "country": place.country,
        "timezone": place.timezone,
        "observed_at": current.get("time"),
        "us_aqi": us_aqi,
        "category": category,
        "guidance": guidance,
        "pm2_5": current.get("pm2_5"),
        "pm10": current.get("pm10"),
        "nitrogen_dioxide": current.get("nitrogen_dioxide"),
        "ozone": current.get("ozone"),
        "carbon_monoxide": current.get("carbon_monoxide"),
        "units": "ug/m3 for all pollutant concentrations",
        "source": SOURCE,
        **({"coordinates_are_approximate": True} if place.approximate else {}),
    }


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
