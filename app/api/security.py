"""Bearer-token authentication for the /brain-os/* API surface.

Reads the expected token from the existing Settings/config system
(`BRAIN_OS_API_TOKEN`) rather than introducing a second configuration
mechanism. Uses FastAPI's `HTTPBearer` security scheme so the
requirement is correctly reflected in the OpenAPI schema and Swagger's
"Authorize" button at /docs, and FastAPI returns a spec-correct 401 with
a `WWW-Authenticate: Bearer` header on failure.
"""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.utils.config import Settings, get_settings

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token from the BRAIN_OS_API_TOKEN environment variable.",
)


def _unauthorized() -> HTTPException:
    # Same generic message for every failure mode (missing header, wrong
    # scheme, wrong token, unconfigured token) so the response never hints
    # at which case applies or what the expected token is.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_api_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """Router-level dependency guarding every /brain-os/* endpoint.

    Fails closed: if BRAIN_OS_API_TOKEN is unset or blank, every request
    is rejected -- an unconfigured token must never be treated as "no
    auth required."
    """
    expected = settings.brain_os_api_token
    if not expected:
        raise _unauthorized()
    if credentials is None:
        raise _unauthorized()
    if not hmac.compare_digest(credentials.credentials, expected):
        raise _unauthorized()
