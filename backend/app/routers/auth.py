"""Google OAuth login for admin UI."""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse, RedirectResponse

from app import auth
from app.config import get_settings
from app.rate_limit import enforce_per_minute

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _public_origin() -> str:
    return get_settings().public_base_url.rstrip("/").lower()


def _request_origin(request: Request) -> Optional[str]:
    try:
        return f"{request.url.scheme}://{request.url.netloc}".lower()
    except Exception:
        return None


def _safe_redirect_url(next_url: str, request: Optional[Request] = None) -> str:
    """Allow relative paths or absolute URLs on PUBLIC_BASE_URL / current host only."""
    base = _public_origin()
    next_url = (next_url or "").strip()
    if not next_url or next_url == "/":
        if request:
            referer = request.headers.get("referer")
            if referer:
                try:
                    parsed = urlparse(referer)
                    origin = f"{parsed.scheme}://{parsed.netloc}".lower()
                    allowed = {base}
                    req_origin = _request_origin(request)
                    if req_origin:
                        allowed.add(req_origin)
                    if origin in allowed:
                        return origin.rstrip("/") + "/"
                except Exception:
                    pass
        return base + "/"
    if next_url.startswith("http://") or next_url.startswith("https://"):
        parsed = urlparse(next_url)
        origin = f"{parsed.scheme}://{parsed.netloc}".lower()
        allowed = {base}
        if request:
            req_origin = _request_origin(request)
            if req_origin:
                allowed.add(req_origin)
        if origin in allowed:
            return next_url
        return base + "/"
    if next_url.startswith("/") and not next_url.startswith("//"):
        return base + next_url
    return base + "/"


@router.get("/login")
async def login(request: Request):
    enforce_per_minute(request, limit=get_settings().auth_rate_limit_per_minute, scope="auth")
    s = get_settings()
    if not s.google_client_id or not s.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured.")
    if not hasattr(auth.oauth, "google"):
        raise HTTPException(status_code=500, detail="Google OAuth is not registered.")

    next_url = (request.query_params.get("next") or "").strip() or "/admin"
    request.session["next_url"] = _safe_redirect_url(next_url, request)

    redirect_uri = auth.get_redirect_uri()
    return await auth.oauth.google.authorize_redirect(
        request,
        redirect_uri,
        hd="redbuttonedu.cz",
    )


@router.get("/callback")
async def callback(request: Request):
    enforce_per_minute(request, limit=get_settings().auth_rate_limit_per_minute, scope="auth")
    if not hasattr(auth.oauth, "google"):
        raise HTTPException(status_code=500, detail="Google OAuth is not registered.")
    try:
        token = await auth.oauth.google.authorize_access_token(request)
    except Exception as e:
        logger.exception("OAuth authorize_access_token failed: %s", e)
        raise HTTPException(status_code=500, detail="Authentication failed.") from e

    user_info = await auth.oauth_userinfo(request, token)
    email = auth.assert_email_verified(user_info)

    next_url = request.session.pop("next_url", "/admin")
    request.session.clear()
    request.session["admin_email"] = email

    redirect_to = _safe_redirect_url(next_url, request)
    return RedirectResponse(redirect_to, headers={"Cache-Control": "no-store"})


@router.get("/me")
async def me(request: Request):
    email = (request.session.get("admin_email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    try:
        auth.validate_domain(email)
    except HTTPException:
        request.session.clear()
        raise
    return {"email": email}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True})
