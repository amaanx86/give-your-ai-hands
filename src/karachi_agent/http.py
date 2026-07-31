"""One pooled, timeout-bounded HTTP client shared by every tool."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import USER_AGENT
from .errors import UpstreamError

logger = logging.getLogger(__name__)

# Transport retries cover connection failures only, never a completed request.
_CONNECT_RETRIES = 2

# Keyed by timeout so a caller with a tighter budget gets its own pool.
_clients: dict[float, httpx.Client] = {}


def _client(timeout: float) -> httpx.Client:
    existing = _clients.get(timeout)
    if existing is not None and not existing.is_closed:
        return existing
    client = httpx.Client(
        timeout=httpx.Timeout(timeout, connect=min(timeout, 3.0)),
        transport=httpx.HTTPTransport(retries=_CONNECT_RETRIES),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        # Aladhan redirects its by-city endpoints.
        follow_redirects=True,
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
    )
    _clients[timeout] = client
    return client


def close_clients() -> None:
    """Close pooled clients and release sockets."""
    while _clients:
        _, client = _clients.popitem()
        client.close()


def get_json(
    url: str,
    params: dict[str, Any],
    *,
    timeout: float,
    source: str,
) -> dict[str, Any]:
    """GET the URL and return the decoded JSON object.

    Raises:
        UpstreamError: on timeout, transport failure, non-2xx status, or a body
            that is not a JSON object.
    """
    try:
        response = _client(timeout).get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise UpstreamError(f"timed out after {timeout:g}s", kind="timeout", source=source) from exc
    except httpx.HTTPStatusError as exc:
        raise UpstreamError(
            f"returned HTTP {exc.response.status_code}", kind="http_error", source=source
        ) from exc
    except httpx.RequestError as exc:
        raise UpstreamError(f"unreachable ({exc})", kind="network_error", source=source) from exc
    except ValueError as exc:
        raise UpstreamError(
            "sent a body that is not valid JSON", kind="bad_payload", source=source
        ) from exc

    if not isinstance(payload, dict):
        raise UpstreamError(
            f"sent {type(payload).__name__}, expected a JSON object",
            kind="bad_payload",
            source=source,
        )
    logger.debug("%s responded in %s", source, response.elapsed)
    return payload
