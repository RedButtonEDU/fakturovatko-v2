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

import html as html_module
import re
from functools import lru_cache
from pathlib import Path
from string import Template

_TEMPLATE_DIR = Path(__file__).resolve().parent / "email_templates"
_MAILTO_EMAIL = "dominik@redbuttonedu.cz"

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


def plain_body_to_html(plain: str) -> str:
    """Z plain textu udělá jednoduché HTML; ``dominik@redbuttonedu.cz`` → klikací mailto odkaz."""
    esc = html_module.escape(plain)
    link = f'<a href="mailto:{_MAILTO_EMAIL}">{_MAILTO_EMAIL}</a>'
    esc = esc.replace(_MAILTO_EMAIL, link)
    inner = esc.replace("\n", "<br>\n")
    return (
        '<div style="font-family: sans-serif; font-size: 14px; line-height: 1.45; color: #222;">'
        f"{inner}</div>"
    )


def render_order_proforma(*, public_id: str) -> tuple[str, str, str]:
    """Subject, plain text, HTML body (pro zálohová faktura / objednávka)."""
    subj_t, body_t = _load_parsed("order_proforma")
    ctx = {"public_id": public_id}
    plain = Template(body_t).substitute(ctx)
    return Template(subj_t).substitute(ctx), plain, plain_body_to_html(plain)


def render_order_paid_invoice(*, discount_code: str) -> tuple[str, str, str]:
    """Subject, plain text, HTML body (po zaplacení — finální faktura + slevový kód)."""
    subj_t, body_t = _load_parsed("order_paid_invoice")
    ctx = {"discount_code": discount_code}
    plain = Template(body_t).substitute(ctx)
    return Template(subj_t).substitute(ctx), plain, plain_body_to_html(plain)
