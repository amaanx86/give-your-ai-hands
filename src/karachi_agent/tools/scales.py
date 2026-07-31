"""Published lookup tables, so the model never interprets a raw code itself."""

from __future__ import annotations

from typing import Final

# WMO 4677 present-weather codes, as returned by open-meteo.
WMO_CODES: Final[dict[int, str]] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def describe_weather_code(code: int | None) -> str:
    """Translate a WMO code into plain language."""
    if code is None:
        return "unknown"
    return WMO_CODES.get(code, f"unrecognised WMO code {code}")


# US EPA AQI breakpoints as inclusive upper bound, category, guidance.
_AQI_BANDS: Final[tuple[tuple[int, str, str], ...]] = (
    (50, "Good", "Air quality is fine. No precautions needed."),
    (
        100,
        "Moderate",
        "Acceptable for most people. Anyone unusually sensitive to air pollution "
        "may want to limit long, strenuous time outdoors.",
    ),
    (
        150,
        "Unhealthy for Sensitive Groups",
        "People with asthma or heart or lung conditions, children, and older adults "
        "should cut back on strenuous outdoor activity. Everyone else is fine.",
    ),
    (
        200,
        "Unhealthy",
        "Everyone should reduce strenuous outdoor activity. Sensitive groups should "
        "stay indoors where they can. A well-fitted mask helps outdoors.",
    ),
    (
        300,
        "Very Unhealthy",
        "Avoid outdoor exertion. Keep windows shut, run a purifier if available, "
        "and wear an N95 outdoors.",
    ),
)

_HAZARDOUS: Final = (
    "Hazardous",
    "Stay indoors with windows shut. Avoid all outdoor exertion. Seek medical "
    "advice for any breathing difficulty.",
)


def band_us_aqi(aqi: float | None) -> tuple[str, str]:
    """Return the category and guidance for a US AQI value."""
    if aqi is None:
        return "Unknown", "No AQI reading was available for this location."
    for upper, category, guidance in _AQI_BANDS:
        if aqi <= upper:
            return category, guidance
    return _HAZARDOUS
