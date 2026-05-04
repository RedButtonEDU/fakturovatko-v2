"""HTTP security headers on every response (Audits HTTP surface, variant A — app layer)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Built SPA + same-origin API; index.html loads Montserrat from Google Fonts.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline headers; HSTS only when ``hsts_max_age > 0`` and request is HTTPS."""

    def __init__(self, app, *, hsts_max_age: int = 0) -> None:
        super().__init__(app)
        self._hsts_max_age = max(0, hsts_max_age)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = _CSP
        if self._hsts_max_age > 0:
            # After ProxyHeadersMiddleware, ``url.scheme`` reflects HTTPS from X-Forwarded-Proto.
            proto = (
                request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
            ).lower()
            first = proto.split(",", maxsplit=1)[0].strip()
            if first == "https":
                response.headers["Strict-Transport-Security"] = f"max-age={self._hsts_max_age}"
        return response
