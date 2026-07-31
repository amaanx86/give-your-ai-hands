"""Prayer times and the next upcoming prayer, via aladhan.com."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from strands import tool

from ..config import Settings, settings
from ..errors import ToolExecutionError, UpstreamError, failure_from
from ..geo import Place, resolve_city
from ..http import get_json

logger = logging.getLogger(__name__)

TIMINGS_URL: Final = "https://api.aladhan.com/v1/timings"
SOURCE: Final = "aladhan.com"

# Aladhan also returns Imsak, Midnight and the night thirds, which we drop.
PRAYERS: Final = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")


@tool
def get_prayer_times(city: str = "Karachi") -> dict[str, Any]:
    """Get today's prayer times and the next upcoming prayer for a city.

    Use this for Fajr, Dhuhr, Asr, Maghrib, Isha, sunrise, sunset, iftar or sehri
    timing, "how long until <prayer>", or planning anything around prayer times.

    Args:
        city: City name, e.g. "Karachi", "Lahore". Defaults to Karachi when the
            user does not name a city.

    Returns:
        On success, a mapping with ``ok: true`` and: ``timings`` (the five prayers
        as 24-hour HH:MM local strings), ``sunrise``, ``sunset``, ``date``,
        ``hijri_date``, ``method``, ``local_time`` (the current local clock, which
        you should use instead of assuming what time it is), and ``next_prayer``
        with ``name``, ``time``, ``in_minutes`` and ``is_tomorrow``. On failure,
        ``ok: false`` and an ``error``, so never state a prayer time you did not
        get from this tool.
    """
    config = settings()
    try:
        place = resolve_city(city or config.default_city, timeout=config.http_timeout)
        tzinfo = _zone(place)
        now = datetime.now(tzinfo)
        today = _fetch_timings(place, now.date(), config.prayer_method, config.http_timeout)
        timings = _extract_timings(today)
        next_prayer = _next_prayer(timings, now, tzinfo, place, config)
    except ToolExecutionError as exc:
        logger.info("get_prayer_times(%r) failed: %s", city, exc)
        return failure_from(exc)

    return {
        "ok": True,
        "city": place.name,
        "country": place.country,
        "timezone": place.timezone,
        "local_time": now.strftime("%H:%M"),
        "date": now.date().isoformat(),
        "hijri_date": _hijri(today),
        "method": _method_name(today),
        "timings": {name: timings[name] for name in PRAYERS if name in timings},
        "sunrise": timings.get("Sunrise"),
        "sunset": timings.get("Sunset"),
        "next_prayer": next_prayer,
        "source": SOURCE,
        **({"coordinates_are_approximate": True} if place.approximate else {}),
    }


def _fetch_timings(place: Place, on: date, method: int, timeout: float) -> dict[str, Any]:
    payload = get_json(
        f"{TIMINGS_URL}/{on.strftime('%d-%m-%Y')}",
        {"latitude": place.latitude, "longitude": place.longitude, "method": method},
        timeout=timeout,
        source=SOURCE,
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise UpstreamError("response had no `data` block", kind="bad_payload", source=SOURCE)
    return data


def _extract_timings(data: dict[str, Any]) -> dict[str, str]:
    raw = data.get("timings")
    if not isinstance(raw, dict) or not raw:
        raise UpstreamError("response had no `timings`", kind="bad_payload", source=SOURCE)
    # Aladhan sometimes suffixes a zone, e.g. "04:35 (PKT)".
    return {str(name): str(value).split(" ")[0] for name, value in raw.items()}


def _hijri(data: dict[str, Any]) -> str | None:
    hijri = (data.get("date") or {}).get("hijri")
    if not isinstance(hijri, dict):
        return None
    day, month, year = hijri.get("day"), (hijri.get("month") or {}).get("en"), hijri.get("year")
    if not (day and month and year):
        return None
    return f"{day} {month} {year} AH"


def _method_name(data: dict[str, Any]) -> str | None:
    method = ((data.get("meta") or {}).get("method") or {}).get("name")
    return str(method) if method else None


def _zone(place: Place) -> ZoneInfo:
    try:
        return ZoneInfo(place.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise UpstreamError(
            f"gave an unknown timezone {place.timezone!r}", kind="bad_payload", source=SOURCE
        ) from exc


def _parse_clock(value: str) -> time | None:
    try:
        hour, minute = (int(part) for part in value.split(":")[:2])
        return time(hour=hour, minute=minute)
    except (ValueError, TypeError):
        return None


def _next_prayer(
    timings: dict[str, str],
    now: datetime,
    tzinfo: ZoneInfo,
    place: Place,
    config: Settings,
) -> dict[str, Any] | None:
    """Return the first prayer still ahead today, else tomorrow's Fajr."""
    for name in PRAYERS:
        clock = _parse_clock(timings.get(name, ""))
        if clock is None:
            continue
        moment = datetime.combine(now.date(), clock, tzinfo=tzinfo)
        if moment > now:
            return _describe(name, moment, now, is_tomorrow=False)

    # Past Isha, and tomorrow's Fajr differs from today's by about a minute.
    tomorrow = now.date() + timedelta(days=1)
    try:
        fajr_clock = _parse_clock(
            _extract_timings(
                _fetch_timings(place, tomorrow, config.prayer_method, config.http_timeout)
            ).get("Fajr", "")
        )
    except ToolExecutionError as exc:
        logger.info("Could not resolve tomorrow's Fajr: %s", exc)
        return None
    if fajr_clock is None:
        return None
    return _describe(
        "Fajr", datetime.combine(tomorrow, fajr_clock, tzinfo=tzinfo), now, is_tomorrow=True
    )


def _describe(name: str, moment: datetime, now: datetime, *, is_tomorrow: bool) -> dict[str, Any]:
    return {
        "name": name,
        "time": moment.strftime("%H:%M"),
        "in_minutes": int((moment - now).total_seconds() // 60),
        "is_tomorrow": is_tomorrow,
    }
