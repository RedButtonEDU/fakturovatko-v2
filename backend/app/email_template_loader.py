"""Load system e-mail subject + body from Markdown files in ``app/email_templates/``.

Soubory se kopírují do image při ``Dockerfile`` (``COPY backend/app``). Upravujte
``*.md`` v repu a znovu sestavte image.

Každý soubor musí začínat jední řádkem ``Subject: …``, prázdným řádkem a pak tělem
zprávy. Placeholdery: ``string.Template`` s ``$jmeno`` (např. ``$public_id``,
``$discount_code``). Literální znak ``$`` zapište jako ``$$``.

Kontaktní e-mail ``dominik@redbuttonedu.cz`` pište v šabloně jako prostý text (bez Markdown
odkazu); HTML část s ``mailto:`` odkazem se doplní automaticky při odeslání.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from string import Template

from app.email_brand import plain_body_to_html

_TEMPLATE_DIR = Path(__file__).resolve().parent / "email_templates"

_SUBJECT_BODY = re.compile(
    r"^Subject:\s*([^\n]+)\n\r?\n(.*)$",
    re.DOTALL | re.MULTILINE,
)


@lru_cache(maxsize=16)
def _load_parsed(name: str) -> tuple[str, str]:
    path = _TEMPLATE_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"E-mail template missing: {path}")
    raw = path.read_text(encoding="utf-8")
    m = _SUBJECT_BODY.match(raw.strip())
    if not m:
        raise ValueError(
            f"E-mail template {path.name} must start with 'Subject: …', blank line, then body."
        )
    return m.group(1).strip(), m.group(2).strip()


def _ticket_quantity_label(quantity: int) -> str:
    n = max(1, int(quantity))
    if n == 1:
        return "1 vstupenku"
    if 2 <= n <= 4:
        return f"{n} vstupenky"
    return f"{n} vstupenek"


def render_order_proforma(*, public_id: str) -> tuple[str, str, str]:
    """Subject, plain text, HTML body (pro zálohová faktura / objednávka)."""
    subj_t, body_t = _load_parsed("order_proforma")
    ctx = {"public_id": public_id}
    subject = Template(subj_t).substitute(ctx)
    plain = Template(body_t).substitute(ctx)
    return subject, plain, plain_body_to_html(plain, subject=subject, variant="customer")


def render_order_paid_voucher(*, discount_code: str, ticket_quantity: int) -> tuple[str, str, str]:
    """Subject, plain text, HTML body (po zaplacení — Ti.to voucher, bez finální faktury)."""
    subj_t, body_t = _load_parsed("order_paid_invoice")
    ctx = {
        "discount_code": discount_code,
        "ticket_quantity_label": _ticket_quantity_label(ticket_quantity),
    }
    subject = Template(subj_t).substitute(ctx)
    plain = Template(body_t).substitute(ctx)
    return subject, plain, plain_body_to_html(plain, subject=subject, variant="customer")


def _optional_contact_field(value: str | None) -> str:
    v = (value or "").strip()
    return v if v else "—"


def render_manual_final_invoice_request(
    *,
    customer_name: str,
    customer_email: str,
    company_name: str | None,
    company_registration: str | None,
    billing_address: str,
    proforma_url: str,
    ticket_quantity: int,
) -> tuple[str, str, str]:
    """E-mail pro ruční vystavení finální faktury (ops / účetní)."""
    subj_t, body_t = _load_parsed("manual_final_invoice_request")
    ctx = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "company_name": _optional_contact_field(company_name),
        "company_registration": _optional_contact_field(company_registration),
        "billing_address": billing_address or "—",
        "proforma_url": proforma_url,
        "ticket_quantity_label": _ticket_quantity_label(ticket_quantity),
    }
    plain = Template(body_t).substitute(ctx)
    subject = Template(subj_t).substitute(ctx)
    return subject, plain, plain_body_to_html(plain, subject=subject, variant="ops")


# Backward-compatible alias
render_order_paid_invoice = render_order_paid_voucher
