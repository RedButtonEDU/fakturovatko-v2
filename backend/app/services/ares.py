"""ARES — ekonomické subjekty (MFČR REST API v3).

Dokumentace: https://ares.gov.cz/swagger-ui.html (ekonomicke-subjekty-v-be)
"""

from typing import Any, Optional

import httpx

BASE = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest"


def _digits_only(s: str) -> str:
    return "".join(ch for ch in s.strip() if ch.isdigit())


def _cz_ico_8(digits: str) -> Optional[str]:
    """IČO pro CZ musí být přesně 8 číslic (API pattern ^\\d{8}$)."""
    if not digits:
        return None
    if len(digits) > 8:
        digits = digits[-8:]
    if len(digits) < 8:
        digits = digits.zfill(8)
    return digits if len(digits) == 8 else None


def _format_street(ad: dict[str, Any]) -> str:
    ulice = ad.get("nazevUlice")
    cd = ad.get("cisloDomovni")
    co = ad.get("cisloOrientacni")
    if ulice:
        ulice_s = str(ulice).strip()
        if cd is not None:
            if co is not None:
                return f"{ulice_s} {cd}/{co}".strip()
            return f"{ulice_s} {cd}".strip()
        return ulice_s
    tv = ad.get("textovaAdresa")
    if tv:
        return str(tv).split(",")[0].strip()
    return ""


def _psc_str(ad: dict[str, Any]) -> str:
    psc = ad.get("psc")
    if psc is None:
        return ""
    return str(int(psc)) if isinstance(psc, (int, float)) else str(psc).replace(" ", "")


def _parse_subject(subj: dict[str, Any]) -> dict[str, Any]:
    ad = subj.get("sidlo")
    if not isinstance(ad, dict):
        ad = {}
    nazev = subj.get("obchodniJmeno") or ""
    dic = subj.get("dic")
    street = _format_street(ad)
    city = str(ad.get("nazevObce") or "").strip()
    return {
        "company_name": str(nazev).strip() if nazev else "",
        "street": street,
        "city": city,
        "zip": _psc_str(ad),
        "vat_id": str(dic).strip() if dic else None,
        "raw": subj,
    }


async def _get_json(client: httpx.AsyncClient, url: str) -> Optional[dict[str, Any]]:
    r = await client.get(url, headers={"Accept": "application/json"})
    if r.status_code == 404:
        return None
    if r.status_code >= 400:
        return None
    data = r.json()
    if isinstance(data, dict) and data.get("kod"):
        return None
    return data if isinstance(data, dict) else None


async def lookup_ico(ico: str, country: str) -> Optional[dict[str, Any]]:
    """
    Vyhledání podle IČO. CZ: GET /ekonomicke-subjekty/{ico}.
    SK: pokus GET /ekonomicke-subjekty-vr/{ico}, jinak POST /ekonomicke-subjekty/vyhledat.
    """
    country = country.upper()
    digits = _digits_only(ico)
    if not digits:
        return None

    async with httpx.AsyncClient(timeout=60.0) as client:
        if country == "CZ":
            code = _cz_ico_8(digits)
            if not code:
                return None
            url = f"{BASE}/ekonomicke-subjekty/{code}"
            subj = await _get_json(client, url)
            return _parse_subject(subj) if subj else None

        if country == "SK":
            code = _cz_ico_8(digits)
            if not code:
                return None
            subj = await _get_json(client, f"{BASE}/ekonomicke-subjekty-vr/{code}")
            if subj:
                return _parse_subject(subj)
            r = await client.post(
                f"{BASE}/ekonomicke-subjekty/vyhledat",
                json={"ico": [code]},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            if r.status_code >= 400:
                return None
            data = r.json()
            items = data.get("ekonomickeSubjekty") or []
            if not items:
                return None
            first = items[0]
            return _parse_subject(first) if isinstance(first, dict) else None

    return None
