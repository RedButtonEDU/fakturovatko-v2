"""Branded HTML e-mail layout — Exponential Summit v3 (aligned with frontend App.css)."""

from __future__ import annotations

import html as html_module
import re
from typing import Literal

from app.config import get_settings
from app.services.ops_links import tito_discount_url

# Exponential Summit v3 tokens (frontend/src/App.css)
_BG = "#1a1a1a"
_CARD = "#272727"
_CARD_BORDER = "rgba(255,255,255,0.1)"
_ACCENT = "#fe1a3f"
_ACCENT_DEEP = "#a11834"
_TEXT = "#babbbd"
_TEXT_MUTED = "#949494"
_TEXT_FOOTER = "#7f7f7f"
_WHITE = "#ffffff"
_INK3 = "#393939"

_MAILTO_EMAIL = "dominik@redbuttonedu.cz"
_SUMMIT_HOME = "https://www.exponentialsummit.cz/v3/"
_EMAIL_LOGO = "exponential-summit-logo.png"

_VOUCHER_LINE = re.compile(
    r"^(Slevový kód na Ti\.to:\s*|Ti\.to voucher \(odeslán zákazníkovi\):\s*)(.+)$",
    re.IGNORECASE,
)
_URL_LINE = re.compile(r"^https?://\S+$")
_META_LINE = re.compile(
    r"^(Objednávka|Zákazník|Počet vstupenek|Detail v adminu):\s*(.+)$",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_INLINE = re.compile(r"https?://[^\s<>]+")

_FONT = "'Rubik',Arial,Helvetica,sans-serif"
_FONT_MARKER = "'Permanent Marker','Marker Felt',cursive,Georgia,serif"


def _link_style(*, pill: bool = False) -> str:
    if pill:
        return (
            "display:inline-block;margin:12px 0 4px;padding:10px 18px;"
            f"background:{_ACCENT};color:{_WHITE};font-family:{_FONT};"
            "font-weight:700;font-size:13px;line-height:1.2;border-radius:999px;"
            "text-decoration:none;"
        )
    return f"color:{_ACCENT};text-decoration:underline;"


def _mailto_link(email: str) -> str:
    esc = html_module.escape(email)
    return f'<a href="mailto:{esc}" style="{_link_style()}">{esc}</a>'


def _url_button(url: str) -> str:
    esc_url = html_module.escape(url, quote=True)
    label = "Otevřít odkaz"
    if "allfred.io" in url and "proforma" in url:
        label = "Otevřít proformu v Allfredu"
    elif "/admin/orders/" in url:
        label = "Detail v adminu"
    return f'<a href="{esc_url}" style="{_link_style(pill=True)}">{label}</a>'


def _linkify_inline(text: str) -> str:
    """Escape plain text and turn e-mails / URLs into styled links."""
    parts: list[str] = []
    pos = 0
    for m in _EMAIL_RE.finditer(text):
        parts.append(html_module.escape(text[pos : m.start()]))
        parts.append(_mailto_link(m.group(0)))
        pos = m.end()
    tail = html_module.escape(text[pos:])
    tail = _URL_INLINE.sub(
        lambda m: f'<a href="{html_module.escape(m.group(0), quote=True)}" style="{_link_style()}">'
        f"{html_module.escape(m.group(0))}</a>",
        tail,
    )
    parts.append(tail)
    return "".join(parts)


def _price_box(content_html: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:12px 0 16px;background:{_INK3};border:1px solid {_CARD_BORDER};'
        f'border-left:3px solid {_ACCENT};border-radius:4px;">'
        f'<tr><td style="padding:14px 16px;font-family:{_FONT};font-size:16px;'
        f'line-height:1.5;color:{_WHITE};font-weight:800;">'
        f"{content_html}</td></tr></table>"
    )


def _paragraph(text_html: str) -> str:
    return (
        f'<p style="margin:0 0 14px;font-family:{_FONT};font-size:15px;'
        f'line-height:1.6;color:{_TEXT};">{text_html}</p>'
    )


def _meta_row(label: str, value_html: str) -> str:
    return (
        f'<tr><td style="padding:6px 0;font-family:{_FONT};font-size:14px;'
        f'line-height:1.5;color:{_TEXT_MUTED};vertical-align:top;width:38%;">'
        f"{html_module.escape(label)}</td>"
        f'<td style="padding:6px 0;font-family:{_FONT};font-size:14px;'
        f'line-height:1.5;color:{_TEXT};vertical-align:top;">{value_html}</td></tr>'
    )


def _voucher_code_html(code: str, *, link_for_customer: bool) -> str:
    raw = code.strip()
    esc = html_module.escape(raw)
    if not link_for_customer or raw.startswith("("):
        return esc
    url = tito_discount_url(raw)
    if not url:
        return esc
    href = html_module.escape(url, quote=True)
    style = f"color:{_WHITE};text-decoration:underline;font-weight:800;"
    return f'<a href="{href}" style="{style}">{esc}</a>'


def _plain_line_to_html(line: str, *, variant: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""

    m = _VOUCHER_LINE.match(stripped)
    if m:
        raw_code = m.group(2).strip()
        label = html_module.escape(m.group(1).strip().rstrip(":"))
        code_html = _voucher_code_html(
            raw_code,
            link_for_customer=variant == "customer" and m.group(1).lower().startswith("slevový kód"),
        )
        return _paragraph(f"{label}:") + _price_box(code_html)

    if _URL_LINE.match(stripped):
        return _url_button(stripped)

    m = _META_LINE.match(stripped)
    if m and variant == "ops":
        return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 8px;">{_meta_row(m.group(1), _linkify_inline(m.group(2).strip()))}</table>'

    if stripped.startswith("Tým Red Button"):
        return (
            f'<p style="margin:20px 0 0;padding-top:16px;border-top:1px solid {_CARD_BORDER};'
            f'font-family:{_FONT};font-size:14px;line-height:1.5;color:{_TEXT_MUTED};">'
            f"{_linkify_inline(stripped)}</p>"
        )

    return _paragraph(_linkify_inline(stripped))


def _plain_to_inner_html(plain: str, *, variant: str) -> str:
    blocks: list[str] = []

    for para in re.split(r"\n\s*\n", plain.strip()):
        lines = [ln for ln in para.splitlines() if ln.strip()]
        if not lines:
            continue

        # Ops meta block: consecutive "Label: value" lines → one table
        if variant == "ops" and all(_META_LINE.match(ln.strip()) for ln in lines):
            rows = "".join(
                _meta_row(m.group(1), _linkify_inline(m.group(2).strip()))
                for ln in lines
                if (m := _META_LINE.match(ln.strip()))
            )
            blocks.append(
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="margin:0 0 16px;">{rows}</table>'
            )
            continue

        for line in lines:
            html = _plain_line_to_html(line, variant=variant)
            if html:
                blocks.append(html)

    return "\n".join(blocks)


def _subject_title(subject: str | None, *, variant: str) -> str | None:
    if not subject:
        return None
    title = subject.strip()
    if variant == "ops":
        title = re.sub(r"^\[Fakturovatko\]\s*", "", title, flags=re.I)
    for sep in (" – ", " - "):
        if sep in title:
            title = title.split(sep, 1)[1].strip()
            break
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
    return title or None


def _preheader_from_plain(plain: str) -> str:
    for line in plain.splitlines():
        s = line.strip()
        if s and not s.lower().startswith(("ahoj", "dobrý den", "dobry den")):
            return s[:120]
    return plain.strip()[:120]


def wrap_branded_email(
    inner_html: str,
    *,
    preheader: str = "",
    variant: Literal["customer", "ops"] = "customer",
    subject: str | None = None,
) -> str:
    s = get_settings()
    base = s.public_base_url.rstrip("/")
    logo_url = f"{base}/assets/{_EMAIL_LOGO}"
    title = _subject_title(subject, variant=variant)
    pre = html_module.escape(preheader)

    if variant == "customer":
        header_extra = (
            f'<p style="margin:14px 0 0;font-family:{_FONT_MARKER};font-size:15px;'
            f'line-height:1.3;color:{_ACCENT};">Exponential Summit</p>'
        )
    else:
        header_extra = (
            f'<p style="margin:14px 0 0;font-family:{_FONT};font-size:11px;font-weight:600;'
            f'letter-spacing:0.08em;text-transform:uppercase;color:{_TEXT_MUTED};">'
            f"Fakturovatko · ops</p>"
        )

    title_block = ""
    if title:
        title_block = (
            f'<h1 style="margin:0 0 20px;font-family:{_FONT};font-weight:800;font-size:22px;'
            f'line-height:1.25;letter-spacing:-0.02em;color:{_WHITE};">{html_module.escape(title)}</h1>'
        )

    return (
        "<!DOCTYPE html>"
        '<html lang="cs"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="dark">'
        '<meta name="supported-color-schemes" content="dark">'
        f'<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;600;700;800'
        f"&family=Permanent+Marker&display=swap\" rel=\"stylesheet\">"
        f"<title>{html_module.escape(subject or 'Exponential Summit')}</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background:{_BG};">'
        f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{pre}&nbsp;</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{_BG};padding:32px 16px;">'
        "<tr><td align=\"center\">"
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;">'
        # Header
        f'<tr><td style="padding:0 0 20px;text-align:center;">'
        f'<a href="{_SUMMIT_HOME}" style="text-decoration:none;">'
        f'<img src="{html_module.escape(logo_url, quote=True)}" width="200" alt="Exponential Summit by Red Button" '
        'style="display:block;margin:0 auto;max-width:200px;height:auto;border:0;" />'
        f"</a>{header_extra}</td></tr>"
        # Card
        f'<tr><td style="background:{_CARD};border:1px solid {_CARD_BORDER};border-radius:4px;'
        f'border-top:3px solid {_ACCENT};box-shadow:-3px 7px 41px rgba(0,0,0,0.23);">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td style="padding:28px 24px 24px;">{title_block}{inner_html}</td></tr>'
        "</table></td></tr>"
        # Footer
        f'<tr><td style="padding:24px 8px 0;text-align:center;font-family:{_FONT};'
        f'font-size:12px;line-height:1.6;color:{_TEXT_FOOTER};">'
        f'<a href="{_SUMMIT_HOME}" style="color:{_TEXT};text-decoration:none;">exponentialsummit.cz</a>'
        f" · Red Button EDU</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def plain_body_to_html(
    plain: str,
    *,
    subject: str | None = None,
    variant: Literal["customer", "ops"] = "customer",
) -> str:
    """Convert plain-text body to branded HTML matching the order form site."""
    inner = _plain_to_inner_html(plain, variant=variant)
    preheader = _preheader_from_plain(plain)
    return wrap_branded_email(
        inner,
        preheader=preheader,
        variant=variant,
        subject=subject,
    )
