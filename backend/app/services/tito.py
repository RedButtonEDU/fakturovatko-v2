"""Ti.to Admin API v3 helpers."""

import secrets
import string
from typing import Any, Optional

import httpx

from app.config import get_settings

TITO_BASE = "https://api.tito.io/v3"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Token token={api_key}",
    }


async def fetch_releases(account: str, event_slug: str, api_key: str) -> list[dict[str, Any]]:
    """Public + on_sale releases for form."""
    url = f"{TITO_BASE}/{account}/{event_slug}/releases"
    params = {"version": "3.1"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers=_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()
    releases = data.get("releases") or []
    out = []
    for rel in releases:
        if not isinstance(rel, dict):
            continue
        # API 3.1: state_name is "on_sale" | "off_sale"; older code used wrong key "state"
        if rel.get("secret") is True:
            continue
        if rel.get("off_sale") is True:
            continue
        sn = (rel.get("state_name") or rel.get("state") or "").lower()
        if sn == "off_sale":
            continue
        if sn and sn != "on_sale":
            continue
        out.append(rel)
    return out


async def fetch_event(account: str, event_slug: str, api_key: str) -> dict[str, Any]:
    url = f"{TITO_BASE}/{account}/{event_slug}"
    params = {"version": "3.1"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers=_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()
    return data.get("event") or {}


def generate_discount_code(length: int = 12) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def create_discount_code(
    *,
    account: str,
    event_slug: str,
    api_key: str,
    release_id: int,
    quantity: int,
    code: Optional[str] = None,
) -> dict[str, Any]:
    """
    100% off, limited quantity, attached to one release.
    Ticket visibility per plan: only_attached + if_discount_code_available.
    """
    code = code or generate_discount_code()
    url = f"{TITO_BASE}/{account}/{event_slug}/discount_codes"
    params = {"version": "3.1"}
    # Admin API 3.1: bracket keys as JSON (see docs curl --data '{"discount_code[code]":...}').
    # Use a scalar for discount_code[release_ids][] — a JSON array as the value causes 422.
    # Must use json= (not data=): httpx AsyncClient rejects form body with data= (sync-only path).
    body: dict[str, Any] = {
        "discount_code[code]": code,
        "discount_code[type]": "PercentOffDiscountCode",
        "discount_code[value]": 100,
        "discount_code[quantity]": quantity,
        "discount_code[show_public_releases]": "only_attached",
        "discount_code[show_secret_releases]": "if_discount_code_available",
        "discount_code[release_ids][]": release_id,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            url,
            headers={**_headers(api_key), "Content-Type": "application/json"},
            params=params,
            json=body,
        )
        if r.is_error:
            snippet = (r.text or "")[:2500]
            raise RuntimeError(f"Ti.to discount_codes {r.status_code}: {snippet}") from None
        return r.json()
