"""Tool failure contract, so a tool returns an error instead of raising."""

from __future__ import annotations

from typing import Any, Literal

ErrorKind = Literal[
    "invalid_input",
    "city_not_found",
    "timeout",
    "network_error",
    "http_error",
    "bad_payload",
]

# Kinds where an immediate retry is plausibly useful.
RETRYABLE: frozenset[str] = frozenset({"timeout", "network_error", "http_error"})


class ToolExecutionError(Exception):
    """Base for anything that stops a tool producing an answer."""

    def __init__(self, message: str, *, kind: ErrorKind, source: str | None = None) -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind
        self.source = source

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


class InvalidInputError(ToolExecutionError):
    """The model called a tool with arguments we will not act on."""

    def __init__(self, message: str) -> None:
        super().__init__(message, kind="invalid_input")


class CityNotFoundError(ToolExecutionError):
    """Geocoding succeeded and matched nothing."""

    def __init__(self, city: str) -> None:
        super().__init__(
            f"no place matched {city!r}, ask the user to confirm the spelling or "
            "give a nearby larger city",
            kind="city_not_found",
        )


class UpstreamError(ToolExecutionError):
    """An upstream data API did not give a usable answer."""


def failure(kind: ErrorKind, message: str) -> dict[str, Any]:
    """Build the payload a tool returns instead of raising."""
    return {
        "ok": False,
        "error": {"kind": kind, "message": message, "retryable": kind in RETRYABLE},
    }


def failure_from(exc: ToolExecutionError) -> dict[str, Any]:
    """Translate an exception into the failure payload."""
    detail = f"{exc.source} {exc}" if exc.source else str(exc)
    return failure(exc.kind, detail)


def is_failure(payload: Any) -> bool:
    """True if the payload is a tool failure envelope."""
    return isinstance(payload, dict) and payload.get("ok") is False
