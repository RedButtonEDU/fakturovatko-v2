"""Shared ops/admin link builders and alert formatting."""

from __future__ import annotations

from typing import Optional

from app.config import get_settings
from app.models import Order
from app.services.order_errors import order_error_label, sanitize_error_for_ops


def public_base_url() -> str:
    return get_settings().public_base_url.rstrip("/")


def admin_order_url(order: Order) -> str:
    return f"{public_base_url()}/admin/orders/{order.public_id}"


def allfred_proforma_url(proforma_id: Optional[str]) -> Optional[str]:
    if not proforma_id or str(proforma_id).startswith("mock-"):
        return None
    s = get_settings()
    return f"https://{s.allfred_workspace}.allfred.io/outgoing-proforma-invoices/{proforma_id}"


def allfred_final_invoice_url(invoice_id: Optional[str]) -> Optional[str]:
    if not invoice_id or str(invoice_id).startswith("mock-"):
        return None
    s = get_settings()
    return f"https://{s.allfred_workspace}.allfred.io/outgoing-invoices/{invoice_id}"


def tito_release_url(release_slug: Optional[str]) -> Optional[str]:
    if not release_slug:
        return None
    s = get_settings()
    return (
        f"https://ti.to/{s.tito_account_slug}/{s.tito_event_slug}/"
        f"releases/{release_slug}/edit"
    )


def build_workflow_alert_body(
    order: Order,
    *,
    step: str,
    detail: str,
    invoice_no: Optional[str] = None,
) -> str:
    label = order_error_label(order.error_code) or step
    code = order.error_code or "—"
    safe_detail = sanitize_error_for_ops(detail)
    lines = [
        f"Opravit v adminu:",
        admin_order_url(order),
        "",
        f"Typ chyby: {label} [{code}]",
        f"Krok: {step}",
        f"Detail: {safe_detail}",
        "",
        f"Objednávka: {order.public_id} ({order.created_at.date().isoformat()}, stav: {order.status})",
        f"Zákazník: {order.full_name} <{order.email}>",
        f"Počet vstupenek: {order.ticket_quantity}",
    ]
    if order.allfred_proforma_id:
        proforma_line = f"Allfred proforma: {order.allfred_proforma_id}"
        if invoice_no:
            proforma_line += f" ({invoice_no})"
        pf_url = allfred_proforma_url(order.allfred_proforma_id)
        if pf_url:
            proforma_line += f" → {pf_url}"
        lines.append(proforma_line)
    if order.tito_release_slug:
        tito_line = f"Ti.to release: {order.tito_release_title} ({order.tito_release_slug})"
        t_url = tito_release_url(order.tito_release_slug)
        if t_url:
            tito_line += f" → {t_url}"
        lines.append(tito_line)
    if order.tito_invoice_release_slug:
        inv_line = f"Ti.to invoice klon: {order.tito_invoice_release_slug}"
        t_url = tito_release_url(order.tito_invoice_release_slug)
        if t_url:
            inv_line += f" → {t_url}"
        lines.append(inv_line)
    return "\n".join(lines)
