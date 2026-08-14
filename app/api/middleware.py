"""Request body size cap, enforced before FastAPI ever parses the body.

Pydantic's `max_length` on InvoiceIntakeRequest.text (see
app/models/schemas.py) rejects an oversized *text field* with a clean
422, but only after the whole JSON body has already been read and
parsed into memory. This middleware rejects an oversized body outright
based on the Content-Length header, before any parsing happens -- the
real defense against a large-payload DoS.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class MaxBodySizeMiddleware:
    """Raw ASGI middleware: rejects requests whose Content-Length exceeds
    `max_bytes` with 413, without reading the body. A request with no
    Content-Length header (e.g. chunked transfer-encoding) is not caught
    here -- see the Known limitations note in README.md."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                content_length = int(raw_length)
            except ValueError:
                content_length = None
            if content_length is not None and content_length > self.max_bytes:
                response = JSONResponse(
                    {"detail": f"Request body exceeds the {self.max_bytes}-byte limit."},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
