"""OpenData FS — informační seznamy (IČ DPH / DIČ pro slovenské subjekty podle IČO).

API: https://iz.opendata.financnasprava.sk/ — hlavička ``key`` (viz env ``OPENDATA_FS``).
Vyhledání v seznamu registrovaných plátců DPH: ``GET /api/data/{slug}/search``."""

from __future__ import annotations

import re
from typing import Any, Optional

import httpx

IZ_BASE = "https://iz.opendata.financnasprava.sk/api"

# Cache slug + sloupec IČO po prvním úspěchu (proces žije déle než jeden request)
_vat_list_slug: Optional[str] = None
_ico_search_column: Optional[str] = None


def _digits(s: str) -> str:
    return "".join(ch for ch in s.strip() if ch.isdigit())


def _normalize_dic(raw: str) -> Optional[str]:
    """Vrátí DIČ jako 10 číslic nebo None."""
    d = _digits(raw)
    if len(d) == 10:
        return d
    return None


def _dic_from_row(row: dict[str, Any]) -> Optional[str]:
    """Najde DIČ v řádku (různé názvy sloupců z datasetu FS)."""
    for key, val in row.items():
        kl = str(key).lower()
        if val is None:
            continue
        s = str(val).strip()
        if not s:
            continue
        if "dic" in kl or "ic_dph" in kl or "icdph" in kl:
            n = _normalize_dic(s)
            if n:
                return n
        if re.fullmatch(r"SK\d{10}", s.replace(" ", ""), re.I):
            return _normalize_dic(s[2:])
    for key, val in row.items():
        if val is None:
            continue
        kl = str(key).lower()
        if "ico" in kl and "dic" not in kl:
            continue
        n = _normalize_dic(str(val).strip())
        if n:
            return n
    return None


def _pick_vat_list_slug(lists_payload: dict[str, Any]) -> Optional[str]:
    """Vybere slug seznamu „registrovaní pro DPH“ podle názvu."""
    for slug, meta in lists_payload.items():
        if slug in ("message", "error", "detail"):
            continue
        if not isinstance(meta, dict):
            continue
        name = (meta.get("name") or "").lower()
        slug_l = str(slug).lower()
        if "registrovan" in name and "dph" in name:
            return str(meta.get("slug") or slug)
        if "registrovan" in slug_l and "dph" in slug_l:
            return str(meta.get("slug") or slug)
        if "taxpayers registered" in name and "vat" in name:
            return str(meta.get("slug") or slug)
    return None


def _pick_ico_column(searchable: list[Any]) -> Optional[str]:
    """Vybere název sloupce pro vyhledání podle IČO."""
    if not searchable:
        return None
    for col in searchable:
        c = str(col).strip()
        cl = c.lower()
        if "ico" in cl or "ičo" in cl or "identifik" in cl:
            return c
    return str(searchable[0]).strip() if searchable else None


def _normalize_lists_payload(data: Any) -> dict[str, Any]:
    """API vrací objekt slug→meta; někdy může být vnoření nebo pole."""
    if isinstance(data, list):
        out: dict[str, Any] = {}
        for item in data:
            if isinstance(item, dict) and item.get("slug"):
                out[str(item["slug"])] = item
        return out
    if not isinstance(data, dict):
        return {}
    inner = data.get("lists")
    if isinstance(inner, dict):
        return inner
    inner = data.get("data")
    if isinstance(inner, dict) and all(isinstance(v, dict) for v in inner.values()):
        return inner
    return data


async def fetch_lists(api_key: str) -> Optional[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{IZ_BASE}/lists", headers={"key": api_key})
        if r.status_code != 200:
            return None
        raw = r.json()
        normalized = _normalize_lists_payload(raw)
        return normalized if normalized else None


async def fetch_list_detail(api_key: str, slug: str) -> Optional[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{IZ_BASE}/lists/{slug}", headers={"key": api_key})
        if r.status_code != 200:
            return None
        data = r.json()
        return data if isinstance(data, dict) else None


async def search_list_page(
    api_key: str,
    slug: str,
    column: str,
    search: str,
    page: int = 1,
) -> Optional[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{IZ_BASE}/data/{slug}/search",
            headers={"key": api_key},
            params={"column": column, "search": search, "page": page},
        )
        if r.status_code != 200:
            return None
        return r.json() if isinstance(r.json(), dict) else None


async def lookup_dic_by_ico(api_key: str, ico: str) -> Optional[str]:
    """
    Vrátí DIČ (10 číslic) z registra plátců DPH, pokud je subjekt s daným IČO mezi registrovanými.
    Při chybě API nebo nenalezení vrátí None.
    """
    global _vat_list_slug, _ico_search_column

    digits = _digits(ico)
    if len(digits) < 5:
        return None

    slug = _vat_list_slug
    if not slug:
        lists_payload = await fetch_lists(api_key)
        if not lists_payload:
            return None
        slug = _pick_vat_list_slug(lists_payload)
        if not slug:
            return None
        _vat_list_slug = slug

    col = _ico_search_column
    if not col:
        detail = await fetch_list_detail(api_key, slug)
        if not detail:
            return None
        searchable = detail.get("searchable") or []
        if not isinstance(searchable, list):
            return None
        col = _pick_ico_column(searchable)
        if not col:
            return None
        _ico_search_column = col

    data = await search_list_page(api_key, slug, col, digits, page=1)
    if not data:
        return None
    rows = data.get("data") or []
    if not isinstance(rows, list):
        return None

    for row in rows:
        if not isinstance(row, dict):
            continue
        dic = _dic_from_row(row)
        if dic:
            return dic
    return None


async def verify_api_key(api_key: str) -> tuple[bool, str]:
    """Ověří klíč (GET /lists). Vrací (úspěch, krátká zpráva)."""
    lists_payload = await fetch_lists(api_key)
    if lists_payload is None:
        return False, "lists request failed (check key or network)"
    if lists_payload.get("message"):
        return False, str(lists_payload.get("message"))
    n = len([k for k in lists_payload.keys() if k not in ("message", "error", "detail")])
    if n == 0:
        return False, "empty lists response"
    return True, f"ok, {n} list(s)"
