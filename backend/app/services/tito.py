"""Ti.to Admin API v3 helpers."""

import logging
import re
import secrets
import string
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import get_settings

TITO_BASE = "https://api.tito.io/v3"
logger = logging.getLogger(__name__)

_INVOICE_SUFFIX_RE = re.compile(r"\s*-?\s*invoice\s*$", re.IGNORECASE)


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Token token={api_key}",
    }


def _parse_tito_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def release_is_available(rel: dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """
    Ti.to může vrátit state_name=on_sale i u release s budoucím start_at (upcoming=true).
    Pro formulář bereme jen skutečně koupitelné release.
    """
    moment = now or datetime.now(timezone.utc)

    if rel.get("upcoming") is True:
        return False
    if rel.get("expired") is True:
        return False
    if rel.get("sold_out") is True:
        return False

    start_at = _parse_tito_datetime(rel.get("start_at"))
    if start_at is not None and start_at > moment:
        return False

    end_at = _parse_tito_datetime(rel.get("end_at"))
    if end_at is not None and end_at < moment:
        return False

    return True


def release_title_is_invoice_clone(rel: dict[str, Any]) -> bool:
    return "invoice" in str(rel.get("title") or "").lower()


def release_base_title(title: str) -> str:
    return _INVOICE_SUFFIX_RE.sub("", title.strip()).strip()


def find_invoice_clone_release(
    public_release: dict[str, Any],
    all_releases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pair public release with its secret invoice clone (title contains 'invoice')."""
    public_title = (public_release.get("title") or "").strip()
    public_id = public_release.get("id")
    matches: list[dict[str, Any]] = []
    for rel in all_releases:
        if rel.get("id") == public_id:
            continue
        title = str(rel.get("title") or "")
        if not release_title_is_invoice_clone(rel):
            continue
        if release_base_title(title) == public_title:
            matches.append(rel)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one Ti.to invoice clone for {public_title!r}, found {len(matches)}"
        )
    return matches[0]


async def fetch_all_releases_raw(account: str, event_slug: str, api_key: str) -> list[dict[str, Any]]:
    """All releases including secret — for pairing and quantity PATCH."""
    url = f"{TITO_BASE}/{account}/{event_slug}/releases"
    params = {"version": "3.1"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers=_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()
    releases = data.get("releases") or []
    return [rel for rel in releases if isinstance(rel, dict)]


async def fetch_release(
    account: str,
    event_slug: str,
    api_key: str,
    release_slug: str,
) -> dict[str, Any]:
    url = f"{TITO_BASE}/{account}/{event_slug}/releases/{release_slug}"
    params = {"version": "3.1"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers=_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()
    rel = data.get("release")
    if not isinstance(rel, dict):
        raise RuntimeError(f"Ti.to release {release_slug!r} not found")
    return rel


async def patch_release_quantity(
    account: str,
    event_slug: str,
    api_key: str,
    release_slug: str,
    quantity: int,
) -> dict[str, Any]:
    url = f"{TITO_BASE}/{account}/{event_slug}/releases/{release_slug}"
    params = {"version": "3.1"}
    body = {"release": {"quantity": int(quantity)}}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.patch(
            url,
            headers={**_headers(api_key), "Content-Type": "application/json"},
            params=params,
            json=body,
        )
        if r.is_error:
            snippet = (r.text or "")[:2500]
            raise RuntimeError(f"Ti.to PATCH release {release_slug} {r.status_code}: {snippet}") from None
        data = r.json()
    rel = data.get("release")
    if not isinstance(rel, dict):
        raise RuntimeError(f"Ti.to PATCH release {release_slug!r} returned no release")
    logger.info(
        "Ti.to release quantity patched slug=%s quantity=%s tickets_count=%s",
        release_slug,
        rel.get("quantity"),
        rel.get("tickets_count"),
    )
    return rel


async def adjust_release_quantity(
    account: str,
    event_slug: str,
    api_key: str,
    release_slug: str,
    delta: int,
) -> tuple[int, int]:
    """Read-modify-write release.quantity by delta. Returns (before, after)."""
    rel = await fetch_release(account, event_slug, api_key, release_slug)
    raw_q = rel.get("quantity")
    if raw_q is None or raw_q == "":
        raise RuntimeError(f"Ti.to release {release_slug!r} has unlimited quantity — cannot adjust")
    before = int(raw_q)
    sold = int(rel.get("tickets_count") or 0)
    after = before + int(delta)
    if after < sold:
        raise RuntimeError(
            f"Ti.to release {release_slug!r}: quantity {after} would be below tickets_count {sold}"
        )
    if after < 0:
        raise RuntimeError(f"Ti.to release {release_slug!r}: quantity {after} would be negative")
    await patch_release_quantity(account, event_slug, api_key, release_slug, after)
    return before, after


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
        if release_title_is_invoice_clone(rel):
            continue
        if rel.get("off_sale") is True:
            continue
        sn = (rel.get("state_name") or rel.get("state") or "").lower()
        if sn == "off_sale":
            continue
        if sn and sn != "on_sale":
            continue
        if not release_is_available(rel):
            continue
        out.append(rel)
    return out


def release_order_limits(rel: dict[str, Any]) -> dict[str, Optional[int]]:
    """Ti.to release: zbývající kusy (jen při limitu quantity) a min/max na objednávku."""
    remaining: Optional[int] = None
    q = rel.get("quantity")
    if q is not None and q != "":
        try:
            total = int(q)
            sold = int(rel.get("tickets_count") or 0)
            remaining = max(0, total - sold)
        except (TypeError, ValueError):
            remaining = None

    def _pos(v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            n = int(v)
            return n if n > 0 else None
        except (TypeError, ValueError):
            return None

    return {
        "quantity_remaining": remaining,
        "min_per_order": _pos(rel.get("min_tickets_per_person")),
        "max_per_order": _pos(rel.get("max_tickets_per_person")),
    }


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
    Faktura na firmu: FAKT-<název firmy ASCII, max 10 znaků>-<počet vstupenek>-<5 náhodných A–Z0–9>.
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
        return f"FAKT-{slug}-{qty}-{_random_suffix(5)}"
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
