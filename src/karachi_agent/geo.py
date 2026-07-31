"""City name to coordinates and timezone, cached and shared by all tools."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Final

from .errors import CityNotFoundError, InvalidInputError, UpstreamError
from .http import get_json

logger = logging.getLogger(__name__)

GEOCODE_URL: Final = "https://geocoding-api.open-meteo.com/v1/search"
SOURCE: Final = "open-meteo geocoding"

_MAX_CITY_LENGTH: Final = 80
_WHITESPACE = re.compile(r"\s+")

# Last-resort coordinates, used only when geocoding itself is unreachable.
_FALLBACK_GAZETTEER: Final[dict[str, tuple[float, float, str, str]]] = {
    "karachi": (24.8607, 67.0011, "Pakistan", "Asia/Karachi"),
    "lahore": (31.5204, 74.3587, "Pakistan", "Asia/Karachi"),
    "islamabad": (33.6844, 73.0479, "Pakistan", "Asia/Karachi"),
}


@dataclass(frozen=True, slots=True)
class Place:
    """A resolved location."""

    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    region: str | None = None
    approximate: bool = False

    @property
    def label(self) -> str:
        return f"{self.name}, {self.country}"


def normalise_city(city: str) -> str:
    """Validate and tidy a city name arriving from the model."""
    if not isinstance(city, str):
        raise InvalidInputError("city must be a string")
    cleaned = _WHITESPACE.sub(" ", city).strip().strip(",")
    if not cleaned:
        raise InvalidInputError("city name is empty")
    if len(cleaned) > _MAX_CITY_LENGTH:
        raise InvalidInputError(f"city name is longer than {_MAX_CITY_LENGTH} characters")
    return cleaned


def resolve_city(city: str, *, timeout: float) -> Place:
    """Resolve a city to coordinates and an IANA timezone.

    Raises:
        InvalidInputError: the name is unusable.
        CityNotFoundError: geocoding succeeded but matched nothing.
        UpstreamError: geocoding is unreachable and no fallback exists.
    """
    return _resolve_cached(normalise_city(city), timeout)


@lru_cache(maxsize=256)
def _resolve_cached(city: str, timeout: float) -> Place:
    # lru_cache does not memoise exceptions, so transient failures are retried.
    try:
        payload = get_json(
            GEOCODE_URL,
            {"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=timeout,
            source=SOURCE,
        )
    except UpstreamError:
        fallback = _fallback(city)
        if fallback is None:
            raise
        logger.warning("Geocoding unavailable, using built-in coordinates for %s", city)
        return fallback

    results = payload.get("results") or []
    if not results:
        raise CityNotFoundError(city)
    return _to_place(results[0])


def _to_place(result: dict[str, Any]) -> Place:
    try:
        return Place(
            name=str(result["name"]),
            country=str(result.get("country") or "Unknown"),
            latitude=float(result["latitude"]),
            longitude=float(result["longitude"]),
            timezone=str(result.get("timezone") or "UTC"),
            region=str(result["admin1"]) if result.get("admin1") else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamError(
            "returned a result without usable coordinates", kind="bad_payload", source=SOURCE
        ) from exc


def _fallback(city: str) -> Place | None:
    entry = _FALLBACK_GAZETTEER.get(city.casefold())
    if entry is None:
        return None
    latitude, longitude, country, timezone = entry
    return Place(
        name=city.title(),
        country=country,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        approximate=True,
    )
