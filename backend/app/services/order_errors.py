"""Order error codes, admin capability helpers, error sanitization."""

from __future__ import annotations

import enum
import re
from typing import Any, Optional

from app.models import Order, OrderStatus

_TOKEN_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I),
    re.compile(r"(api[_-]?key|token|secret|password)\s*[=:]\s*\S+", re.I),
    re.compile(r"https?://\S+[?&](?:token|key|secret)=[^&\s]+", re.I),
)


class OrderErrorCode(str, enum.Enum):
    tito_hold_failed = "tito_hold_failed"
    tito_invoice_release_missing = "tito_invoice_release_missing"
    tito_pool_credit_failed = "tito_pool_credit_failed"
    tito_voucher_failed = "tito_voucher_failed"
    allfred_final_invoice_failed = "allfred_final_invoice_failed"
    customer_email_failed = "customer_email_failed"
    proforma_email_failed = "proforma_email_failed"
    allfred_proforma_failed = "allfred_proforma_failed"
    workflow_unknown = "workflow_unknown"


ERROR_LABELS: dict[str, str] = {
    OrderErrorCode.tito_hold_failed.value: "Ti.to hold selhal",
    OrderErrorCode.tito_invoice_release_missing.value: "Chybí Ti.to invoice release (hold neproběhl)",
    OrderErrorCode.tito_pool_credit_failed.value: "Ti.to invoice pool — chyba",
    OrderErrorCode.tito_voucher_failed.value: "Ti.to voucher — chyba",
    OrderErrorCode.allfred_final_invoice_failed.value: "Allfred finální faktura — chyba",
    OrderErrorCode.customer_email_failed.value: "E-mail zákazníkovi — chyba",
    OrderErrorCode.proforma_email_failed.value: "Proforma e-mail — chyba",
    OrderErrorCode.allfred_proforma_failed.value: "Allfred proforma — chyba",
    OrderErrorCode.workflow_unknown.value: "Neznámá chyba workflow",
}


def order_error_label(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return ERROR_LABELS.get(code, code)


def sanitize_error_for_storage(message: str, *, max_len: int = 2000) -> str:
    text = (message or "").strip()
    for pat in _TOKEN_PATTERNS:
        text = pat.sub("[redacted]", text)
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text


def sanitize_error_for_ops(message: Optional[str], *, max_len: int = 500) -> str:
    return sanitize_error_for_storage(message or "", max_len=max_len)


def clear_order_error(order: Order) -> None:
    order.error_code = None
    order.error_step = None
    order.last_error = None


def set_order_error(order: Order, *, code: OrderErrorCode | str, step: str, error: Exception | str) -> None:
    order.error_code = code.value if isinstance(code, OrderErrorCode) else str(code)
    order.error_step = step
    order.last_error = sanitize_error_for_storage(str(error))


def partial_failure_hint(order: Order) -> Optional[str]:
    if (
        order.tito_discount_code
        and order.paid_customer_email_sent_at is None
        and order.status != OrderStatus.completed.value
    ):
        return "voucher_without_email"
    return None


def compute_admin_capabilities(order: Order) -> dict[str, Any]:
    hint = partial_failure_hint(order)
    retry_blocked_reason: Optional[str] = None
    can_retry = False
    can_edit = False

    if order.status == OrderStatus.paid_processing.value:
        retry_blocked_reason = "Workflow právě běží — počkejte na dokončení."
    elif order.status == OrderStatus.completed.value:
        retry_blocked_reason = "Objednávka je dokončená — workflow nelze znovu spustit."
    elif hint == "voucher_without_email":
        retry_blocked_reason = (
            "Voucher byl vystaven, ale e-mail zákazníkovi neodešel — "
            "řešte ručně (odeslat kód, kontaktovat zákazníka). Workflow nelze znovu spustit."
        )
        can_edit = True
    elif order.tito_discount_code and order.paid_customer_email_sent_at:
        retry_blocked_reason = "Voucher a e-mail zákazníkovi jsou hotové — workflow nelze znovu spustit."
    elif order.tito_discount_code:
        retry_blocked_reason = "Voucher byl vystaven — workflow nelze znovu spustit."
    elif order.paid_customer_email_sent_at:
        retry_blocked_reason = "E-mail zákazníkovi už byl odeslán — workflow nelze znovu spustit."
    else:
        fixable = order.status == OrderStatus.error.value or (
            order.status == OrderStatus.awaiting_payment.value and bool(order.error_code)
        )
        if fixable:
            can_retry = True
            can_edit = True

    return {
        "can_edit": can_edit,
        "can_retry_workflow": can_retry,
        "retry_blocked_reason": retry_blocked_reason,
        "partial_failure_hint": hint,
    }


def needs_legacy_hold_repair(order: Order) -> bool:
    return order.tito_quantity_held_at is None and order.tito_invoice_release_id is None
