"""ARES economic subjects search (CZ + SK)."""

from typing import Any, Optional

import httpx

ARES_BASE = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/vychozi-dotaz"


async def lookup_ico(ico: str, country: str) -> Optional[dict[str, Any]]:
    """
    Look up company by registration number.
    Returns dict with company_name, street, city, zip, vat_id (dic) or None if not found.
    """
    ico = "".join(ch for ch in ico.strip() if ch.isdigit())
    if not ico:
        return None
    country = country.upper()
    # ARES API accepts ico in body; for SK use 8 digits typically
    payload: dict[str, Any] = {"ico": [ico]}
    if country == "SK":
        payload["seznamCiselnikuFiltru"] = ["stavZdrojeVr"]  # optional; API may still work

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            ARES_BASE,
            json=payload,
            headers={"Accept": "application/json"},
        )
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            return None
        data = r.json()

    # Response shape varies — try common keys
    items = (
        data.get("ekonomickySubjekty")
        or data.get("ekonomickySubjekt")
        or data.get("ekonomickéSubjekty")
        or []
    )
    if isinstance(items, dict):
        items = [items]
    if not items:
        return None
    subj = items[0] if isinstance(items[0], dict) else None
    if not subj:
        return None

    # Parse nested ARES structure (simplified)
    def _first_addr(s: dict) -> dict:
        sid = s.get("sidlo") or {}
        if isinstance(sid, dict):
            return sid
        return {}

    ad = _first_addr(subj)
    nazev = subj.get("obchodniJmeno") or subj.get("nazev") or ""
    dic = subj.get("dic")
    if not dic:
        dic = subj.get("dic")
    # CZ format: ico 8 digits
    return {
        "company_name": str(nazev).strip() if nazev else "",
        "street": _format_street(ad),
        "city": ad.get("nazevObce") or ad.get("nazevObce") or "",
        "zip": str(ad.get("psc") or "").replace(" ", ""),
        "vat_id": str(dic).strip() if dic else None,
        "raw": subj,
    }


def _format_street(ad: dict) -> str:
    parts = []
    for key in ("nazevUlice", "cisloDomovni", "cisloOrientacni"):
        v = ad.get(key)
        if v:
            parts.append(str(v))
    return " ".join(parts).strip()
