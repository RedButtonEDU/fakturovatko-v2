"""Pipedrive REST API — search/create person & org, set custom fields."""

from typing import Any, Optional

import httpx

from app.config import get_settings


async def _get(path: str, params: Optional[dict] = None) -> dict[str, Any]:
    s = get_settings()
    if not s.pipedrive_api_token:
        raise RuntimeError("PIPEDRIVE_API_TOKEN is not set")
    q: dict[str, Any] = {"api_token": s.pipedrive_api_token}
    if params:
        q.update(params)
    url = f"{s.pipedrive_base_url.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, params=q)
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict) -> dict[str, Any]:
    s = get_settings()
    if not s.pipedrive_api_token:
        raise RuntimeError("PIPEDRIVE_API_TOKEN is not set")
    url = f"{s.pipedrive_base_url.rstrip('/')}/{path.lstrip('/')}"
    params = {"api_token": s.pipedrive_api_token}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, params=params, json=body)
        r.raise_for_status()
        return r.json()


async def _put(path: str, body: dict) -> dict[str, Any]:
    s = get_settings()
    if not s.pipedrive_api_token:
        raise RuntimeError("PIPEDRIVE_API_TOKEN is not set")
    url = f"{s.pipedrive_base_url.rstrip('/')}/{path.lstrip('/')}"
    params = {"api_token": s.pipedrive_api_token}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.put(url, params=params, json=body)
        r.raise_for_status()
        return r.json()


async def search_person_by_email(email: str) -> Optional[int]:
    data = await _get(
        "persons/search",
        {"term": email.strip(), "fields": "email", "exact_match": True},
    )
    items = (data.get("data") or {}).get("items") or []
    if not items:
        return None
    it = items[0].get("item") if isinstance(items[0], dict) else None
    if it and it.get("id"):
        return int(it["id"])
    return None


async def search_org_by_ico_field(ico: str) -> Optional[int]:
    """Search organizations by term=ico, then verify custom field IČO."""
    s = get_settings()
    ico_clean = "".join(ch for ch in ico if ch.isdigit())
    if not ico_clean:
        return None
    data = await _get(
        "organizations/search",
        {"term": ico_clean, "fields": "custom_fields"},
    )
    items = (data.get("data") or {}).get("items") or []
    field_key = s.pipedrive_org_field_ico
    for row in items:
        item = row.get("item") if isinstance(row, dict) else None
        if not item or not item.get("id"):
            continue
        oid = int(item["id"])
        detail = await _get(f"organizations/{oid}")
        d = detail.get("data") or {}
        stored = d.get(field_key)
        if stored is None:
            continue
        if str(stored).replace(" ", "") == ico_clean:
            return oid
    return None


async def create_organization(
    name: str,
    *,
    ico: Optional[str] = None,
    dic: Optional[str] = None,
    address: Optional[str] = None,
) -> int:
    s = get_settings()
    payload: dict[str, Any] = {"name": name}
    if ico:
        payload[s.pipedrive_org_field_ico] = ico
    if dic:
        payload[s.pipedrive_org_field_dic] = dic
    if address:
        payload["address"] = address
    data = await _post("organizations", payload)
    return int(data["data"]["id"])


async def create_person(
    name: str,
    email: str,
    org_id: Optional[int] = None,
) -> int:
    payload: dict[str, Any] = {"name": name, "email": [{"value": email, "primary": True}]}
    if org_id:
        payload["org_id"] = org_id
    data = await _post("persons", payload)
    return int(data["data"]["id"])


async def update_person_hw_live(person_id: int, year_option: str = "2026") -> None:
    s = get_settings()
    await _put(
        f"persons/{person_id}",
        {s.pipedrive_person_field_hw_live: year_option},
    )


async def ensure_person_and_org(
    *,
    email: str,
    full_name: str,
    invoice_to_company: bool,
    company_name: Optional[str],
    ico: Optional[str],
    dic: Optional[str],
    address: Optional[str],
) -> tuple[int, Optional[int]]:
    """
    Find or create organization (by IČO) and person (by email).
    Returns (person_id, org_id).
    """
    person_id = await search_person_by_email(email)
    org_id: Optional[int] = None

    if invoice_to_company and ico:
        org_id = await search_org_by_ico_field(ico)
        if org_id is None and company_name:
            org_id = await create_organization(
                company_name,
                ico=ico,
                dic=dic,
                address=address,
            )

    if person_id is None:
        person_id = await create_person(full_name, email, org_id=org_id)
    elif org_id:
        await _put(f"persons/{person_id}", {"org_id": org_id})

    await update_person_hw_live(person_id)
    return person_id, org_id
