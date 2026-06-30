"""Ti.to quantity hold / release for Fakturovatko orders."""

import logging
from datetime import datetime
from typing import Optional

from app.config import Settings, get_settings
from app.models import Order
from app.services import tito as tito_svc
from app.services.ops_alert import notify_ops
from app.services.ops_links import build_workflow_alert_body
from app.services.order_errors import OrderErrorCode, order_error_label, set_order_error

logger = logging.getLogger(__name__)


def _tito_settings(s: Optional[Settings] = None) -> tuple[Settings, str, str, str]:
    cfg = s or get_settings()
    key = cfg.tito_api_key
    if not key:
        raise RuntimeError("TITO_API_KEY missing")
    return cfg, cfg.tito_account_slug, cfg.tito_event_slug, key


async def apply_public_release_hold(order: Order) -> None:
    """
    After successful proforma + e-mail: decrement public release quantity,
    resolve and store invoice clone release id.
    """
    if order.tito_quantity_held_at is not None:
        return

    s, account, event_slug, api_key = _tito_settings()
    all_releases = await tito_svc.fetch_all_releases_raw(account, event_slug, api_key)
    public = next((r for r in all_releases if int(r.get("id") or 0) == order.tito_release_id), None)
    if public is None:
        raise RuntimeError(f"Ti.to public release id={order.tito_release_id} not found")

    invoice_clone = tito_svc.find_invoice_clone_release(public, all_releases)
    order.tito_invoice_release_id = int(invoice_clone["id"])
    order.tito_invoice_release_slug = str(invoice_clone.get("slug") or "")

    before, after = await tito_svc.adjust_release_quantity(
        account,
        event_slug,
        api_key,
        order.tito_release_slug,
        delta=-order.ticket_quantity,
    )
    order.tito_public_quantity_before = before
    order.tito_public_quantity_after = after
    order.tito_quantity_held_at = datetime.utcnow()
    logger.info(
        "Ti.to hold order=%s release=%s qty %s→%s (−%s)",
        order.public_id[:8],
        order.tito_release_slug,
        before,
        after,
        order.ticket_quantity,
    )


async def restore_public_release_hold(order: Order) -> None:
    """Return held quantity to public release (proforma deleted/cancelled)."""
    if order.tito_quantity_held_at is None or order.tito_quantity_released_at is not None:
        return

    s, account, event_slug, api_key = _tito_settings()
    before, after = await tito_svc.adjust_release_quantity(
        account,
        event_slug,
        api_key,
        order.tito_release_slug,
        delta=order.ticket_quantity,
    )
    order.tito_quantity_released_at = datetime.utcnow()
    logger.info(
        "Ti.to hold restored order=%s release=%s qty %s→%s (+%s)",
        order.public_id[:8],
        order.tito_release_slug,
        before,
        after,
        order.ticket_quantity,
    )


async def credit_invoice_release_pool(order: Order) -> tuple[int, int]:
    """After payment: increase invoice clone release quantity (idempotent)."""
    if order.tito_invoice_quantity_patched_at is not None:
        before = order.tito_invoice_quantity_before or 0
        after = order.tito_invoice_quantity_after or before
        logger.info(
            "Ti.to invoice pool credit skipped (already patched) order=%s",
            order.public_id[:8],
        )
        return before, after

    if not order.tito_invoice_release_slug:
        raise RuntimeError(f"Order {order.public_id} has no tito_invoice_release_slug")

    s, account, event_slug, api_key = _tito_settings()
    before, after = await tito_svc.adjust_release_quantity(
        account,
        event_slug,
        api_key,
        order.tito_invoice_release_slug,
        delta=order.ticket_quantity,
    )
    order.tito_invoice_quantity_before = before
    order.tito_invoice_quantity_after = after
    order.tito_invoice_quantity_patched_at = datetime.utcnow()
    logger.info(
        "Ti.to invoice pool credited order=%s release=%s qty %s→%s (+%s)",
        order.public_id[:8],
        order.tito_invoice_release_slug,
        before,
        after,
        order.ticket_quantity,
    )
    return before, after


def alert_hold_failure(order: Order, error: Exception) -> None:
    set_order_error(
        order,
        code=OrderErrorCode.tito_hold_failed,
        step="Ti.to hold",
        error=error,
    )
    label = order_error_label(OrderErrorCode.tito_hold_failed.value) or "Ti.to hold selhal"
    body = build_workflow_alert_body(
        order,
        step="Ti.to hold",
        detail=str(error),
    )
    notify_ops(
        subject=f"[Fakturovatko] {label} — objednávka {order.public_id[:8]}",
        body=body,
    )


def alert_workflow_failure(order: Order, step: str, error: Exception) -> None:
    if not order.error_code:
        set_order_error(
            order,
            code=OrderErrorCode.workflow_unknown,
            step=step,
            error=error,
        )
    label = order_error_label(order.error_code) or step
    body = build_workflow_alert_body(
        order,
        step=step,
        detail=str(error),
    )
    notify_ops(
        subject=f"[Fakturovatko] {label} — objednávka {order.public_id[:8]}",
        body=body,
    )
