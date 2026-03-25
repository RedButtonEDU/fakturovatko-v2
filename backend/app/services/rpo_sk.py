"""Slovenský register právnických osob — verejné API ŠÚ SR (vyhľadávanie podľa IČO).

Český ARES (ares.gov.cz) slovenské subjekty touto cestou nevracia — používame oficiálne REST API.
Dokumentácia: https://api.statistics.sk/rpo (search?identifier=…)

DIČ / IČ DPH: odpoveď RPO **neobsahuje** daňové čísla. DIČ (10 číslic) a IČ DPH (SK + tých istých 10 číslic)
**nie sú** matematicky odvodené od IČO — dopĺňajú sa ručne alebo z iného zdroja (OpenData FS, komerčné API).
"""

from typing import Any, Optional

import httpx

STATISTICS_SK_SEARCH = "https://api.statistics.sk/rpo/v1/search"


def _digits(s: str) -> str:
    return "".join(ch for ch in s.strip() if ch.isdigit())


def _current_name(full_names: list[Any]) -> str:
    if not full_names:
        return ""
    for e in reversed(full_names):
        if isinstance(e, dict) and e.get("validTo") is None and e.get("value"):
            return str(e["value"]).strip()
    last = full_names[-1]
    if isinstance(last, dict) and last.get("value"):
        return str(last["value"]).strip()
    return ""


def _current_address(addresses: list[Any]) -> dict[str, Any]:
    if not addresses:
        return {}
    for addr in addresses:
        if isinstance(addr, dict) and addr.get("validTo") is None:
            return addr
    first = addresses[0]
    return first if isinstance(first, dict) else {}


def _format_street_line(addr: dict[str, Any]) -> str:
    street = str(addr.get("street") or "").strip()
    bnum = addr.get("buildingNumber")
    reg = addr.get("regNumber")
    parts = []
    if street:
        parts.append(street)
    if bnum is not None and str(bnum).strip():
        if reg is not None and reg != 0:
            parts.append(f"{reg}/{bnum}")
        else:
            parts.append(str(bnum).strip())
    return " ".join(parts).strip()


def _parse_result(row: dict[str, Any]) -> dict[str, Any]:
    names = row.get("fullNames") or []
    addrs = row.get("addresses") or []
    ad = _current_address(addrs)
    muni = ad.get("municipality") if isinstance(ad.get("municipality"), dict) else {}
    city = str(muni.get("value") or "").strip()
    pcs = ad.get("postalCodes") or []
    zip_s = ""
    if isinstance(pcs, list) and pcs:
        zip_s = str(pcs[0]).replace(" ", "")
    return {
        "company_name": _current_name(names),
        "street": _format_street_line(ad),
        "city": city,
        "zip": zip_s,
        "vat_id": None,
        "raw": row,
    }


async def lookup_sk_ico(ico: str) -> Optional[dict[str, Any]]:
    digits = _digits(ico)
    if not digits:
        return None
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            STATISTICS_SK_SEARCH,
            params={"identifier": digits},
            headers={"Accept": "application/json"},
        )
        if r.status_code >= 400:
            return None
        data = r.json()
    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    return _parse_result(first)
