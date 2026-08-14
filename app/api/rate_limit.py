"""Per-caller rate limiting for the /brain-os/* API surface.

A valid bearer token stops unauthenticated abuse but not a legitimate
caller retrying too aggressively -- each request does real SQLite
writes, a Chroma query, and optionally a paid Anthropic call. This adds
a simple fixed-window limit keyed by the caller's token, enforced as a
FastAPI dependency that runs *after* auth (see routes.py), so a request
that fails authentication never consumes another caller's quota.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.security import bearer_scheme


class RateLimiter:
    """In-memory fixed-window limiter, keyed by caller token.

    Process-local by design: correct for the single-worker/single-instance
    deployment this app currently documents (see PRODUCTION_READINESS.md).
    A multi-instance deployment needs a shared store (e.g. Redis) instead,
    since each process would otherwise track its own independent window.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def check(self, key: str) -> Optional[float]:
        """Records one request for `key`. Returns None if allowed, or
        seconds-until-the-window-resets if the caller is over the limit."""
        now = time.monotonic()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            if now - window_start >= self._window_seconds:
                window_start, count = now, 0
            count += 1
            self._windows[key] = (window_start, count)
            if count > self._max_requests:
                return self._window_seconds - (now - window_start)
        return None


def enforce_rate_limit(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    """Router-level dependency; must be listed after require_api_token so
    an invalid token is rejected by auth before ever reaching this check."""
    limiter: RateLimiter = request.app.state.rate_limiter
    key = credentials.credentials if credentials is not None else "anonymous"

    retry_after = limiter.check(key)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(max(1, int(retry_after) + 1))},
        )
