"""Public API: releases, countries, ARES lookup."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.countries import get_country_options
from app.schemas import CountryOut, ReleaseOut
from app.services import tito as tito_svc
from app.services.ares import lookup_ico

router = APIRouter(prefix="/api", tags=["api"])


def _release_unit_price(rel: dict) -> Optional[float]:
    """Ti.to někdy vrací jen ``display_price`` nebo ``suggested_donation`` místo ``price``."""
    for key in ("price", "display_price"):
        v = rel.get(key)
        if v is None or v == "":
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    sd = rel.get("suggested_donation")
    if sd is not None and str(sd).strip():
        try:
            return float(str(sd).replace(",", "."))
        except ValueError:
            return None
    return None


@router.get("/event")
async def event_meta():
    """Ti.to event flags for price display (ex tax vs inc tax)."""
    s = get_settings()
    if not s.tito_api_key:
        raise HTTPException(503, "TITO_API_KEY not configured")
    ev = await tito_svc.fetch_event(s.tito_account_slug, s.tito_event_slug, s.tito_api_key)
    return {
        "show_prices_ex_tax": bool(ev.get("show_prices_ex_tax")),
        "currency": ev.get("currency") or "CZK",
    }


@router.get("/releases", response_model=list[ReleaseOut])
async def list_releases():
    s = get_settings()
    if not s.tito_api_key:
        raise HTTPException(503, "TITO_API_KEY not configured")
    raw = await tito_svc.fetch_releases(s.tito_account_slug, s.tito_event_slug, s.tito_api_key)
    out: list[ReleaseOut] = []
    for rel in raw:
        try:
            rid = int(rel.get("id"))
        except (TypeError, ValueError):
            continue
        pu = _release_unit_price(rel)
        out.append(
            ReleaseOut(
                id=rid,
                slug=str(rel.get("slug") or ""),
                title=str(rel.get("title") or rel.get("name") or ""),
                price=pu,
                state=str(rel.get("state_name") or rel.get("state") or ""),
                secret=bool(rel.get("secret")) if rel.get("secret") is not None else False,
            )
        )
    return out


@router.get("/countries", response_model=list[CountryOut])
def list_countries():
    return [CountryOut(**c) for c in get_country_options()]


@router.get("/ares/lookup")
async def ares_lookup(ico: str = Query(..., min_length=3), country: str = Query("CZ", min_length=2, max_length=2)):
    data = await lookup_ico(ico, country)
    if not data:
        raise HTTPException(404, "Company not found for this registration number")
    return data
