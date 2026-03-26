"""Background: detect paid proformas, create Ti.to discount, email, Pipedrive."""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.address_utils import billing_address_one_line
from app.models import Order, OrderStatus
from app.services import allfred as allfred_svc
from app.services import email as email_svc
from app.services import pipedrive as pd_svc
from app.services import tito as tito_svc
from app.services.pdf_mock import MOCK_PDF_BYTES
from app.debug_ndjson import log as _dbg

logger = logging.getLogger(__name__)


def _proforma_paid(pf: dict[str, Any]) -> bool:
    return bool(pf.get("paid_at"))


def _find_invoice_for_project(
    invoices: list[dict[str, Any]],
    project_ids: set[str],
) -> Optional[dict[str, Any]]:
    for inv in invoices:
        pids = allfred_svc.find_project_ids(inv)
        if project_ids & set(pids):
            return inv
    return None


async def process_paid_orders(db: Session) -> dict[str, Any]:
    """Poll Allfred for orders awaiting payment; complete flow."""
    s = get_settings()
    processed = 0
    errors = 0
    skipped = 0
    last_errors: list[str] = []

    orders = (
        db.query(Order)
        .filter(Order.status == OrderStatus.awaiting_payment.value)
        .all()
    )
    # region agent log
    _dbg(
        hypothesis_id="H4",
        location="workflow.py:process_paid_orders",
        message="queue_loaded",
        data={"awaiting_count": len(orders)},
    )
    # endregion
    if not orders:
        return {"checked": 0, "completed": 0, "errors": 0, "skipped": 0, "last_errors": []}

    def _needs_allfred_fetch(o: Order) -> bool:
        pid = o.allfred_proforma_id
        return bool(pid) and not str(pid).startswith("mock-")

    needs_allfred = any(_needs_allfred_fetch(o) for o in orders)
    # region agent log
    _dbg(
        hypothesis_id="H4",
        location="workflow.py:process_paid_orders",
        message="allfred_fetch_needed",
        data={"needs_allfred": needs_allfred},
    )
    # endregion

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
                "last_errors": [f"Allfred fetch: {e!s}"[:500]],
            }

    pf_by_id = {str(p.get("id")): p for p in proformas if p.get("id")}

    for order in orders:
        try:
            pf_id = order.allfred_proforma_id
            if not pf_id or str(pf_id).startswith("mock-"):
                if not s.allfred_mock_paid:
                    skipped += 1
                    # region agent log
                    _dbg(
                        hypothesis_id="H4",
                        location="workflow.py:process_paid_orders",
                        message="skip_mock_no_mock_paid",
                        data={"order_prefix": order.public_id[:8]},
                    )
                    # endregion
                    continue
                paid = True
                project_ids = {order.allfred_project_id or "mock"}
            else:
                pf = pf_by_id.get(str(pf_id))
                if not pf:
                    skipped += 1
                    # region agent log
                    _dbg(
                        hypothesis_id="H4",
                        location="workflow.py:process_paid_orders",
                        message="skip_proforma_not_in_allfred",
                        data={"order_prefix": order.public_id[:8]},
                    )
                    # endregion
                    continue
                paid = _proforma_paid(pf)
                if not paid:
                    skipped += 1
                    # region agent log
                    _dbg(
                        hypothesis_id="H4",
                        location="workflow.py:process_paid_orders",
                        message="skip_proforma_unpaid",
                        data={"order_prefix": order.public_id[:8]},
                    )
                    # endregion
                    continue
                project_ids = set(allfred_svc.find_project_ids(pf))

            # region agent log
            _dbg(
                hypothesis_id="H5",
                location="workflow.py:process_paid_orders",
                message="order_processing_start",
                data={
                    "order_prefix": order.public_id[:8],
                    "mock_proforma": bool(not pf_id or str(pf_id).startswith("mock-")),
                },
            )
            # endregion

            order.status = OrderStatus.paid_processing.value
            db.commit()

            # Ti.to discount
            if not s.tito_api_key:
                raise RuntimeError("TITO_API_KEY missing")
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
                release_id=order.tito_release_id,
                quantity=order.ticket_quantity,
                code=discount_code,
            )
            dc = (tito_res.get("discount_code") or {}) if isinstance(tito_res, dict) else {}
            order.tito_discount_code = dc.get("code")
            order.tito_discount_code_id = dc.get("id")
            # region agent log
            _dbg(
                hypothesis_id="H1",
                location="workflow.py:process_paid_orders",
                message="tito_discount_parsed",
                data={
                    "order_prefix": order.public_id[:8],
                    "has_code": bool(dc.get("code")),
                    "has_dc_id": dc.get("id") is not None,
                },
            )
            # endregion

            # Final invoice (mock or match)
            inv = None
            if invoices:
                inv = _find_invoice_for_project(invoices, project_ids)
            if inv:
                order.allfred_final_invoice_id = str(inv.get("id"))
            else:
                order.allfred_final_invoice_id = f"mock-final-{order.public_id[:8]}"

            db.commit()

            # region agent log
            _dbg(
                hypothesis_id="H2",
                location="workflow.py:process_paid_orders",
                message="before_email",
                data={
                    "order_prefix": order.public_id[:8],
                    "gmail_configured": bool(s.gmail_refresh_token),
                },
            )
            # endregion

            # Email
            body = (
                f"Dobrý den,\n\n"
                f"v příloze je finální faktura k vaší objednávce.\n"
                f"Slevový kód na Ti.to: {order.tito_discount_code or '(chyba)'}\n\n"
                f"Exponential Summit tým"
            )
            if s.gmail_refresh_token:
                email_svc.send_email(
                    order.email,
                    "Exponential Summit – faktura a slevový kód",
                    body,
                    attachment_bytes=MOCK_PDF_BYTES,
                    attachment_name=f"faktura-{order.public_id[:8]}.pdf",
                )
            # region agent log
            _dbg(
                hypothesis_id="H2",
                location="workflow.py:process_paid_orders",
                message="after_email",
                data={"order_prefix": order.public_id[:8]},
            )
            # endregion

            # Pipedrive
            # region agent log
            _dbg(
                hypothesis_id="H3",
                location="workflow.py:process_paid_orders",
                message="before_pipedrive",
                data={
                    "order_prefix": order.public_id[:8],
                    "pipedrive_configured": bool(s.pipedrive_api_token),
                },
            )
            # endregion
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
            # region agent log
            _dbg(
                hypothesis_id="H5",
                location="workflow.py:process_paid_orders",
                message="order_completed",
                data={"order_prefix": order.public_id[:8]},
            )
            # endregion
        except Exception as e:
            logger.exception("Order %s failed: %s", order.public_id, e)
            msg = str(e)
            # region agent log
            _dbg(
                hypothesis_id="H2",
                location="workflow.py:process_paid_orders",
                message="order_failed",
                data={
                    "order_prefix": order.public_id[:8],
                    "exc_type": type(e).__name__,
                    "msg_preview": msg[:300],
                },
            )
            # endregion
            order.last_error = msg
            order.status = OrderStatus.error.value
            db.commit()
            errors += 1
            last_errors.append(f"{order.public_id[:8]}…: {msg[:400]}")

    return {
        "checked": len(orders),
        "completed": processed,
        "errors": errors,
        "skipped": skipped,
        "last_errors": last_errors,
    }
