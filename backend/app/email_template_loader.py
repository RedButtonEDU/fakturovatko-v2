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
    """Z plain textu HTML v barvách Exponential Summit v3 (e-mail klienty)."""
    esc = html_module.escape(plain)
    link = f'<a href="mailto:{_MAILTO_EMAIL}" style="color:#fe1a3f;text-decoration:none;">{_MAILTO_EMAIL}</a>'
    esc = esc.replace(_MAILTO_EMAIL, link)
    inner = esc.replace("\n", "<br>\n")
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="margin:0;padding:0;background:#1a1a1a;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#1a1a1a;padding:32px 16px;">'
        '<tr><td align="center">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#272727;border:1px solid rgba(255,255,255,0.1);'
        'border-radius:4px;border-top:3px solid #fe1a3f;">'
        '<tr><td style="padding:28px 24px;font-family:Rubik,Arial,sans-serif;'
        'font-size:15px;line-height:1.55;color:#babbbd;">'
        f"{inner}"
        "</td></tr></table>"
        '<p style="margin:24px 0 0;font-family:Rubik,Arial,sans-serif;font-size:12px;'
        'color:#7f7f7f;text-align:center;">Red Button EDU · Exponential Summit</p>'
        "</td></tr></table></body></html>"
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
