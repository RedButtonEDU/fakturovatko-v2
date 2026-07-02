"""Google OAuth admin session (domain-restricted, no RBAC)."""

from __future__ import annotations

import logging
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = logging.getLogger(__name__)

oauth = OAuth()


def register_oauth() -> None:
    s = get_settings()
    if not s.google_client_id or not s.google_client_secret:
        return
    oauth.register(
        name="google",
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def get_redirect_uri() -> str:
    s = get_settings()
    if s.google_redirect_uri:
        return s.google_redirect_uri.strip()
    base = s.public_base_url.rstrip("/")
    return f"{base}/auth/callback"


def allowed_domain_set() -> set[str]:
    s = get_settings()
    return {d.strip().lower() for d in s.allowed_domains.split(",") if d.strip()}


def google_hosted_domain_hint() -> str:
    """Google `hd` accepts a single domain; with multiple allowed domains use '*'.

    Server-side validate_domain still enforces the full allowlist.
    """
    domains = allowed_domain_set()
    if len(domains) == 1:
        return next(iter(domains))
    return "*"


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_domain(email: str) -> None:
    email = normalize_email(email)
    if email.count("@") != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email format.")
    domain = email.split("@")[-1].lower()
    if domain not in allowed_domain_set():
        logger.warning("validate_domain: rejecting %s", email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email domain not allowed.")


def require_admin_session(request: Request) -> str:
    email = normalize_email(str(request.session.get("admin_email") or ""))
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    try:
        validate_domain(email)
    except HTTPException:
        request.session.clear()
        raise
    return email


async def oauth_userinfo(request: Request, token: dict) -> dict:
    user_info = None
    if token.get("id_token"):
        try:
            user_info = await oauth.google.parse_id_token(request, token)
        except KeyError:
            user_info = None
    if not user_info:
        userinfo_response = await oauth.google.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            token=token,
        )
        user_info = userinfo_response.json()
    return user_info or {}


def assert_email_verified(user_info: dict) -> str:
    if not user_info.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google email not verified.")
    email = normalize_email(str(user_info.get("email") or ""))
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email missing from Google profile.")
    validate_domain(email)
    return email
