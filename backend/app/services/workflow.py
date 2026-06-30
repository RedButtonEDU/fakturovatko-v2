"""Background: detect paid proformas, create Ti.to discount, email, Pipedrive."""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.address_utils import billing_address_one_line
from app.models import Order, OrderStatus
from app.email_template_loader import render_order_paid_invoice
from app.services import allfred as allfred_svc
from app.services import email as email_svc
from app.services import pipedrive as pd_svc
from app.services import tito as tito_svc
from app.services.pdf_mock import MOCK_PDF_BYTES
from app.services.tito_inventory import (
    alert_workflow_failure,
    credit_invoice_release_pool,
    restore_public_release_hold,
)

logger = logging.getLogger(__name__)


def _proforma_paid(pf: dict[str, Any]) -> bool:
    return bool(pf.get("paid_at"))


def _proforma_fake_paid_from_config(pf: dict[str, Any], s: Settings) -> bool:
    """True pokud id nebo invoice_no proformy je v ALLFRED_FAKE_PAID_PROFORMA_REFS (viz Settings)."""
    raw = (s.allfred_fake_paid_proforma_refs or "").strip()
    if not raw:
        return False
    refs = {x.strip() for x in raw.split(",") if x.strip()}
    pid = str(pf.get("id") or "")
    ino = str(pf.get("invoice_no") or "")
    return pid in refs or ino in refs


def _find_invoice_for_project(
    invoices: list[dict[str, Any]],
    project_ids: set[str],
) -> Optional[dict[str, Any]]:
    for inv in invoices:
        pids = allfred_svc.find_project_ids(inv)
        if project_ids & set(pids):
            return inv
    return None


async def _process_voided_proformas(
    db: Session,
    orders: list[Order],
    pf_by_id: dict[str, dict[str, Any]],
) -> int:
    """Restore Ti.to public quantity when Allfred proforma was deleted/cancelled."""
    restored = 0
    for order in orders:
        if order.status != OrderStatus.awaiting_payment.value:
            continue
        if order.tito_quantity_held_at is None or order.tito_quantity_released_at is not None:
            continue
        pf_id = order.allfred_proforma_id
        if not pf_id or str(pf_id).startswith("mock-"):
            continue
        pf = pf_by_id.get(str(pf_id))
        if not allfred_svc.proforma_is_voided(pf):
            continue
        try:
            await restore_public_release_hold(order)
            order.status = OrderStatus.cancelled.value
            order.last_error = "proforma voided in Allfred — Ti.to hold restored"
            db.commit()
            restored += 1
            logger.info("Order %s cancelled — proforma voided, Ti.to hold restored", order.public_id[:8])
        except Exception as e:
            logger.exception("Restore hold failed for order %s: %s", order.public_id, e)
            order.last_error = f"tito_restore: {e}"
            db.commit()
            alert_workflow_failure(order, "Ti.to hold restore (proforma storno)", e)
    return restored


async def process_paid_orders(db: Session) -> dict[str, Any]:
    """Poll Allfred for orders awaiting payment; complete flow."""
    s = get_settings()
    processed = 0
    errors = 0
    skipped = 0
    restored = 0
    last_errors: list[str] = []

    orders = (
        db.query(Order)
        .filter(Order.status == OrderStatus.awaiting_payment.value)
        .all()
    )
    if not orders:
        return {
            "checked": 0,
            "completed": 0,
            "errors": 0,
            "skipped": 0,
            "restored": 0,
            "last_errors": [],
        }

    def _needs_allfred_fetch(o: Order) -> bool:
        pid = o.allfred_proforma_id
        return bool(pid) and not str(pid).startswith("mock-")

    needs_allfred = any(_needs_allfred_fetch(o) for o in orders)

    proformas: list[dict[str, Any]] = []
    invoices: list[dict[str, Any]] = []
    if needs_allfred:
        if not s.allfred_api_key:
            logger.error("Orders with real Allfred proforma IDs require ALLFRED_API_KEY")
            return {
                "checked": len(orders),
                "completed": 0,
                "errors": len(orders),
                "skipped": 0,
                "restored": 0,
                "last_errors": ["ALLFRED_API_KEY required for non-mock proforma IDs"],
            }
        try:
            proformas = await allfred_svc.fetch_all_proformas()
            invoices = await allfred_svc.fetch_all_invoices()
        except Exception as e:
            logger.exception("Allfred fetch failed: %s", e)
            return {
                "checked": len(orders),
                "completed": 0,
                "errors": len(orders),
                "skipped": 0,
                "restored": 0,
                "last_errors": [f"Allfred fetch: {e!s}"[:500]],
            }

    pf_by_id = {str(p.get("id")): p for p in proformas if p.get("id")}
    restored = await _process_voided_proformas(db, orders, pf_by_id)

    for order in orders:
        if order.status != OrderStatus.awaiting_payment.value:
            continue
        try:
            pf_id = order.allfred_proforma_id
            if not pf_id or str(pf_id).startswith("mock-"):
                if not s.allfred_mock_paid:
                    skipped += 1
                    continue
                paid = True
                project_ids = {order.allfred_project_id or "mock"}
            else:
                pf = pf_by_id.get(str(pf_id))
                if allfred_svc.proforma_is_voided(pf):
                    skipped += 1
                    continue
                paid = _proforma_paid(pf)
                if not paid and _proforma_fake_paid_from_config(pf, s):
                    logger.warning(
                        "ALLFRED_FAKE_PAID: proforma id=%s invoice_no=%s — bráno jako zaplacená (paid_at chybí)",
                        pf.get("id"),
                        pf.get("invoice_no"),
                    )
                    paid = True
                if not paid:
                    skipped += 1
                    continue
                project_ids = set(allfred_svc.find_project_ids(pf))

            order.status = OrderStatus.paid_processing.value
            db.commit()

            if not s.tito_api_key:
                raise RuntimeError("TITO_API_KEY missing")

            voucher_release_id = order.tito_invoice_release_id
            if not voucher_release_id:
                raise RuntimeError(
                    "tito_invoice_release_id missing — hold was not applied at order time"
                )

            try:
                await credit_invoice_release_pool(order)
                db.commit()
            except Exception as e:
                alert_workflow_failure(order, "Ti.to invoice pool credit", e)
                raise

            discount_code = tito_svc.build_discount_code_label(
                invoice_to_company=order.invoice_to_company,
                company_name=order.company_name,
                full_name=order.full_name,
                ticket_quantity=order.ticket_quantity,
            )
            tito_res = await tito_svc.create_discount_code(
                account=s.tito_account_slug,
                event_slug=s.tito_event_slug,
                api_key=s.tito_api_key,
                release_id=int(voucher_release_id),
                quantity=order.ticket_quantity,
                code=discount_code,
            )
            dc = (tito_res.get("discount_code") or {}) if isinstance(tito_res, dict) else {}
            order.tito_discount_code = dc.get("code")
            order.tito_discount_code_id = dc.get("id")

            final_invoice_id: Optional[str] = None
            pdf_bytes: Optional[bytes] = None

            if allfred_svc.quick_setup_ready():
                try:
                    qsr = await allfred_svc.quick_setup_client_project_invoice(order)
                    oi = (qsr.get("outgoingInvoice") or {}) if isinstance(qsr, dict) else {}
                    if oi.get("id"):
                        final_invoice_id = str(oi["id"])
                        pdf_bytes = await allfred_svc.resolve_outgoing_invoice_pdf_bytes(oi)
                except Exception as e:
                    logger.warning("Allfred quickSetupClientProjectInvoice failed: %s", e)

            if not final_invoice_id and invoices:
                inv = _find_invoice_for_project(invoices, project_ids)
                if inv:
                    final_invoice_id = str(inv.get("id"))
                    pdf_bytes = await allfred_svc.download_outgoing_invoice_pdf_by_id(final_invoice_id)

            if not final_invoice_id:
                final_invoice_id = f"mock-final-{order.public_id[:8]}"
            order.allfred_final_invoice_id = final_invoice_id
            if pdf_bytes is None:
                pdf_bytes = MOCK_PDF_BYTES

            db.commit()

            paid_subject, body, body_html = render_order_paid_invoice(
                discount_code=order.tito_discount_code or "(chyba)",
            )
            if s.gmail_refresh_token:
                email_svc.send_email(
                    order.email,
                    paid_subject,
                    body,
                    body_html=body_html,
                    attachment_bytes=pdf_bytes,
                    attachment_name=f"faktura-{order.public_id[:8]}.pdf",
                )

            if s.pipedrive_api_token:
                pid, oid = await pd_svc.ensure_person_and_org(
                    email=order.email,
                    full_name=order.full_name,
                    invoice_to_company=order.invoice_to_company,
                    company_name=order.company_name,
                    ico=order.company_registration,
                    dic=order.vat_id,
                    address=billing_address_one_line(order) or None,
                )
                order.pipedrive_person_id = pid
                order.pipedrive_org_id = oid

            order.status = OrderStatus.completed.value
            db.commit()
            processed += 1
        except Exception as e:
            logger.exception("Order %s failed: %s", order.public_id, e)
            msg = str(e)
            order.last_error = msg
            order.status = OrderStatus.error.value
            db.commit()
            errors += 1
            last_errors.append(f"{order.public_id[:8]}…: {msg[:400]}")
            alert_workflow_failure(order, "paid order workflow", e)

    return {
        "checked": len(orders),
        "completed": processed,
        "errors": errors,
        "skipped": skipped,
        "restored": restored,
        "last_errors": last_errors,
    }
