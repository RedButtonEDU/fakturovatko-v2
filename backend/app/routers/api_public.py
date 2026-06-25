"""Public API: releases, countries, ARES lookup."""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.config import get_settings
from app.countries import get_country_options
from app.rate_limit import enforce_per_minute
from app.schemas import AresLookupOut, CountryOut, ReleaseOut
from app.services import tito as tito_svc
from app.services.ares import lookup_ico

logger = logging.getLogger(__name__)

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
        limits = tito_svc.release_order_limits(rel)
        out.append(
            ReleaseOut(
                id=rid,
                slug=str(rel.get("slug") or ""),
                title=str(rel.get("title") or rel.get("name") or ""),
                price=pu,
                state=str(rel.get("state_name") or rel.get("state") or ""),
                secret=bool(rel.get("secret")) if rel.get("secret") is not None else False,
                quantity_remaining=limits["quantity_remaining"],
                min_per_order=limits["min_per_order"],
                max_per_order=limits["max_per_order"],
            )
        )
    return out


@router.get("/countries", response_model=list[CountryOut])
def list_countries():
    return [CountryOut(**c) for c in get_country_options()]


def _ares_rate_limit(request: Request) -> None:
    enforce_per_minute(
        request,
        limit=get_settings().ares_rate_limit_per_minute,
        scope="ares-lookup",
    )


@router.get("/ares/lookup", response_model=AresLookupOut)
async def ares_lookup(
    request: Request,
    ico: str = Query(..., min_length=3),
    country: str = Query("CZ", min_length=2, max_length=2),
    _rate: None = Depends(_ares_rate_limit),
):
    try:
        data = await lookup_ico(ico, country)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Register lookup timed out — try again in a moment.",
        ) from None
    except httpx.RequestError as e:
        logger.warning("ares lookup upstream error: %s", e)
        raise HTTPException(
            status_code=502,
            detail="Register lookup failed — try again later.",
        ) from None
    if not data:
        raise HTTPException(404, "Company not found for this registration number")
    return data
