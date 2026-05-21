"""Simple in-memory rate limiting for public lookup endpoints."""

from __future__ import annotations

from collections import defaultdict
from time import time

from fastapi import HTTPException, Request

_store: dict[str, list[float]] = defaultdict(list)
_WINDOW_S = 60.0


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def enforce_per_minute(request: Request, *, limit: int, scope: str) -> None:
    """Raise 429 when more than ``limit`` requests per minute from one client."""
    if limit <= 0:
        return
    key = f"{scope}:{_client_ip(request)}"
    now = time()
    _store[key] = [t for t in _store[key] if now - t < _WINDOW_S]
    if len(_store[key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many lookup requests — try again in a moment.",
        )
    _store[key].append(now)
