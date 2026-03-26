"""Ti.to Admin API v3 helpers."""

import secrets
import string
import unicodedata
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.debug_ndjson import log as _dbg

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


def _random_suffix(length: int = 5) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _strip_diacritics_to_ascii_alnum_upper(s: str) -> str:
    """Remove diacritics; keep only A–Z and 0–9, uppercase."""
    if not s:
        return ""
    nfd = unicodedata.normalize("NFD", s)
    no_marks = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return "".join(c.upper() for c in no_marks if c.isalnum())


def _surname_from_full_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if not parts:
        return ""
    return parts[-1]


def build_discount_code_label(
    *,
    invoice_to_company: bool,
    company_name: Optional[str],
    full_name: str,
    ticket_quantity: int,
) -> str:
    """
    Faktura na firmu: FAKT-<název firmy ASCII, bez mezer, max 10 znaků>.
    Jinak: <příjmení ASCII>-<počet vstupenek>-<5 náhodných znaků A–Z0–9>.
    """
    qty = max(1, min(50, int(ticket_quantity)))
    if invoice_to_company:
        raw = (company_name or "").strip()
        slug = _strip_diacritics_to_ascii_alnum_upper(raw)[:10]
        if not slug:
            slug = _strip_diacritics_to_ascii_alnum_upper(_surname_from_full_name(full_name))[:10]
        if not slug:
            slug = "X"
        return f"FAKT-{slug}"
    sur = _strip_diacritics_to_ascii_alnum_upper(_surname_from_full_name(full_name))
    if not sur:
        sur = _strip_diacritics_to_ascii_alnum_upper(full_name)[:20] or "X"
    return f"{sur}-{qty}-{_random_suffix(5)}"


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
    # JSON requests must use a nested `discount_code` object (Rails strong params).
    # Flat keys like "discount_code[code]" work in curl --data strings but not as JSON keys — Ti.to
    # then returns 422 "param is missing: discount_code". release_ids: integer array (API 3.1).
    body: dict[str, Any] = {
        "discount_code": {
            "code": code,
            "type": "PercentOffDiscountCode",
            "value": 100,
            "quantity": quantity,
            "show_public_releases": "only_attached",
            "show_secret_releases": "if_discount_code_available",
            "release_ids": [release_id],
        }
    }
    # region agent log
    _dbg(
        hypothesis_id="H1",
        location="tito.py:create_discount_code",
        message="pre_post",
        data={
            "account": account,
            "event_slug": event_slug,
            "release_id": release_id,
            "quantity": quantity,
            "url_path": f"/v3/{account}/{event_slug}/discount_codes",
        },
    )
    # endregion
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            url,
            headers={**_headers(api_key), "Content-Type": "application/json"},
            params=params,
            json=body,
        )
        # region agent log
        _dbg(
            hypothesis_id="H1",
            location="tito.py:create_discount_code",
            message="post_response",
            data={"status_code": r.status_code, "ok": r.is_success},
        )
        # endregion
        if r.is_error:
            snippet = (r.text or "")[:2500]
            raise RuntimeError(f"Ti.to discount_codes {r.status_code}: {snippet}") from None
        return r.json()
