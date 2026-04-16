"""ČNB kurzy — pro fakturaci v EUR z částek v Kč (střední kurz devizového trhu)."""

from dataclasses import dataclass
from datetime import date

import httpx


@dataclass(frozen=True)
class CnbEurFixing:
    """Platnost kurzu a kolik Kč za 1 EUR (po vydělení ``amount`` z řádku ČNB)."""

    valid_for: date
    czk_per_one_eur: float


async def fetch_cnb_eur_fixing(for_calendar_date: date) -> CnbEurFixing:
    """Vrátí střední kurz EUR vůči Kč pro den (víkendy vrací ČNB poslední pracovní den v ``valid_for``)."""
    url = f"https://api.cnb.cz/cnbapi/exrates/daily?date={for_calendar_date.isoformat()}&lang=EN"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        payload = r.json()
    rates = payload.get("rates") or []
    for row in rates:
        if row.get("currencyCode") != "EUR":
            continue
        rate = float(row["rate"])
        amount = int(row.get("amount") or 1)
        vf_raw = row.get("validFor")
        if isinstance(vf_raw, str) and len(vf_raw) >= 10:
            vd = date.fromisoformat(vf_raw[:10])
        else:
            vd = for_calendar_date
        czk_per_one = rate / float(amount)
        if czk_per_one <= 0:
            break
        return CnbEurFixing(valid_for=vd, czk_per_one_eur=czk_per_one)
    raise RuntimeError("CNB API: EUR rate not found in daily response")
