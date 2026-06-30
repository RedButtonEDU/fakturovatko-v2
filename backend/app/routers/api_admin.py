"""Admin API — orders list, detail, patch, retry workflow."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import asc, desc, nulls_last
from sqlalchemy.orm import Session

from app import auth
from app.db import get_db
from app.models import AdminAuditLog, Order, OrderStatus
from app.rate_limit import enforce_per_hour
from app.schemas import (
    AdminAuditEntryOut,
    OrderAdminListItem,
    OrderAdminListOut,
    OrderAdminOut,
    OrderAdminPatch,
    OrderRetryWorkflowIn,
    OrderRetryWorkflowOut,
)
from app.config import get_settings
from app.services import allfred as allfred_svc
from app.services.order_errors import (
    compute_admin_capabilities,
    needs_legacy_hold_repair,
    order_error_label,
)
from app.services.ops_links import (
    admin_order_url,
    allfred_final_invoice_url,
    allfred_proforma_url,
    tito_discount_url,
    tito_release_url,
)
from app.services.tito_inventory import apply_public_release_hold
from app.services.workflow import is_proforma_paid_for_order, process_single_paid_order

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_ORDER_LIST_SORT_COLUMNS: dict[str, Any] = {
    "created_at": Order.created_at,
    "full_name": Order.full_name,
    "status": Order.status,
    "error_code": Order.error_code,
    "allfred_proforma_id": Order.allfred_proforma_id,
}


def _order_list_sort_clause(sort_by: str, sort_dir: str):
    col = _ORDER_LIST_SORT_COLUMNS.get(sort_by, Order.created_at)
    descending = sort_dir != "asc"
    if sort_by in ("error_code", "allfred_proforma_id"):
        return nulls_last(desc(col) if descending else asc(col))
    return desc(col) if descending else asc(col)


def _trim(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = s.strip()
    return t or None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat() + "Z"


def _write_audit(
    db: Session,
    *,
    admin_email: str,
    order_public_id: str,
    action: str,
    payload: Optional[dict[str, Any]],
    result: str,
) -> None:
    entry = AdminAuditLog(
        admin_email=admin_email,
        order_public_id=order_public_id,
        action=action,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        result=result[:512],
    )
    db.add(entry)
    db.commit()


def _validate_patch(order: Order, patch: OrderAdminPatch) -> None:
    invoice_to_company = (
        patch.invoice_to_company if patch.invoice_to_company is not None else order.invoice_to_company
    )
    address_street = patch.address_street if patch.address_street is not None else order.address_street
    address_city = patch.address_city if patch.address_city is not None else order.address_city
    address_zip = patch.address_zip if patch.address_zip is not None else order.address_zip
    country_code = patch.country_code if patch.country_code is not None else order.country_code
    company_registration = (
        patch.company_registration
        if patch.company_registration is not None
        else order.company_registration
    )
    company_name = patch.company_name if patch.company_name is not None else order.company_name

    def _addr_ok() -> bool:
        return bool(
            (address_street or "").strip()
            and (address_city or "").strip()
            and (address_zip or "").strip()
        )

    if not country_code:
        raise HTTPException(422, "country_code is required")

    if not invoice_to_company:
        if not _addr_ok():
            raise HTTPException(422, "address_street, address_city, address_zip are required")
    else:
        if not (company_registration or "").strip():
            raise HTTPException(422, "company_registration (IČO) is required")
        if not (company_name or "").strip():
            raise HTTPException(422, "company_name is required")
        if not _addr_ok():
            raise HTTPException(422, "address_street, address_city, address_zip are required")


async def _proforma_invoice_no(order: Order) -> Optional[str]:
    pf_id = order.allfred_proforma_id
    if not pf_id or str(pf_id).startswith("mock-"):
        return None
    try:
        for pf in await allfred_svc.fetch_all_proformas():
            if str(pf.get("id")) == str(pf_id):
                ino = pf.get("invoice_no")
                return str(ino) if ino is not None else None
    except Exception as e:
        logger.warning("Could not fetch proforma invoice_no for %s: %s", order.public_id[:8], e)
    return None


def _order_to_admin_out(order: Order, audit: list[AdminAuditLog]) -> OrderAdminOut:
    caps = compute_admin_capabilities(order)
    return OrderAdminOut(
        public_id=order.public_id,
        created_at=_iso(order.created_at) or "",
        updated_at=_iso(order.updated_at) or "",
        full_name=order.full_name,
        email=order.email,
        status=order.status,
        ticket_quantity=order.ticket_quantity,
        tito_release_title=order.tito_release_title,
        tito_release_slug=order.tito_release_slug,
        error_code=order.error_code,
        error_step=order.error_step,
        error_label=order_error_label(order.error_code),
        last_error=order.last_error,
        can_edit=caps["can_edit"],
        can_retry_workflow=caps["can_retry_workflow"],
        retry_blocked_reason=caps["retry_blocked_reason"],
        partial_failure_hint=caps["partial_failure_hint"],
        needs_legacy_hold_repair=needs_legacy_hold_repair(order),
        allfred_proforma_id=order.allfred_proforma_id,
        allfred_final_invoice_id=order.allfred_final_invoice_id,
        tito_discount_code=order.tito_discount_code,
        tito_invoice_release_id=order.tito_invoice_release_id,
        tito_invoice_release_slug=order.tito_invoice_release_slug,
        tito_quantity_held_at=_iso(order.tito_quantity_held_at),
        tito_invoice_quantity_patched_at=_iso(order.tito_invoice_quantity_patched_at),
        paid_customer_email_sent_at=_iso(order.paid_customer_email_sent_at),
        manual_final_invoice_request_sent_at=_iso(order.manual_final_invoice_request_sent_at),
        invoice_to_company=order.invoice_to_company,
        company_name=order.company_name,
        company_registration=order.company_registration,
        vat_id=order.vat_id,
        address_street=order.address_street,
        address_city=order.address_city,
        address_zip=order.address_zip,
        country_code=order.country_code,
        admin_url=admin_order_url(order),
        allfred_proforma_url=allfred_proforma_url(order.allfred_proforma_id),
        allfred_final_invoice_url=allfred_final_invoice_url(order.allfred_final_invoice_id),
        tito_voucher_url=tito_discount_url(order.tito_discount_code),
        tito_invoice_release_url=tito_release_url(order.tito_invoice_release_slug),
        audit_log=[
            AdminAuditEntryOut(
                id=a.id,
                created_at=_iso(a.created_at) or "",
                admin_email=a.admin_email,
                action=a.action,
                payload_json=a.payload_json,
                result=a.result,
            )
            for a in audit
        ],
    )


@router.get("/orders", response_model=OrderAdminListOut)
def list_orders(
    skip: int = 0,
    limit: int = 50,
    sort_by: str = Query("created_at", pattern="^(created_at|full_name|status|error_code|allfred_proforma_id)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin_session),
):
    limit = min(max(limit, 1), 200)
    skip = max(skip, 0)
    q = db.query(Order).order_by(_order_list_sort_clause(sort_by, sort_dir))
    total = q.count()
    rows = q.offset(skip).limit(limit).all()
    items = [
        OrderAdminListItem(
            public_id=o.public_id,
            created_at=_iso(o.created_at) or "",
            full_name=o.full_name,
            email=o.email,
            status=o.status,
            error_code=o.error_code,
            error_label=order_error_label(o.error_code),
            allfred_proforma_id=o.allfred_proforma_id,
            ticket_quantity=o.ticket_quantity,
        )
        for o in rows
    ]
    return OrderAdminListOut(items=items, total=total, skip=skip, limit=limit)


@router.get("/orders/{public_id}", response_model=OrderAdminOut)
async def get_order(
    public_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(auth.require_admin_session),
):
    order = db.query(Order).filter(Order.public_id == public_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    audit = (
        db.query(AdminAuditLog)
        .filter(AdminAuditLog.order_public_id == public_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    out = _order_to_admin_out(order, audit)
    out.allfred_proforma_invoice_no = await _proforma_invoice_no(order)
    return out


@router.patch("/orders/{public_id}", response_model=OrderAdminOut)
async def patch_order(
    public_id: str,
    body: OrderAdminPatch,
    db: Session = Depends(get_db),
    admin_email: str = Depends(auth.require_admin_session),
):
    order = db.query(Order).filter(Order.public_id == public_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    caps = compute_admin_capabilities(order)
    if not caps["can_edit"]:
        raise HTTPException(409, caps["retry_blocked_reason"] or "Edit not allowed")

    patch_data = body.model_dump(exclude_unset=True)
    if not patch_data:
        raise HTTPException(422, "No fields to update")

    merged = OrderAdminPatch(
        full_name=patch_data.get("full_name", order.full_name),
        email=patch_data.get("email", order.email),
        invoice_to_company=patch_data.get("invoice_to_company", order.invoice_to_company),
        address_street=patch_data.get("address_street", order.address_street),
        address_city=patch_data.get("address_city", order.address_city),
        address_zip=patch_data.get("address_zip", order.address_zip),
        country_code=patch_data.get("country_code", order.country_code),
        company_registration=patch_data.get("company_registration", order.company_registration),
        vat_id=patch_data.get("vat_id", order.vat_id),
        company_name=patch_data.get("company_name", order.company_name),
    )
    _validate_patch(order, merged)

    before = {
        k: getattr(order, k)
        for k in (
            "full_name",
            "email",
            "invoice_to_company",
            "address_street",
            "address_city",
            "address_zip",
            "country_code",
            "company_registration",
            "vat_id",
            "company_name",
        )
    }

    if body.full_name is not None:
        order.full_name = body.full_name.strip()
    if body.email is not None:
        order.email = str(body.email).lower().strip()
    if body.invoice_to_company is not None:
        order.invoice_to_company = body.invoice_to_company
    if body.address_street is not None:
        order.address_street = _trim(body.address_street)
    if body.address_city is not None:
        order.address_city = _trim(body.address_city)
    if body.address_zip is not None:
        order.address_zip = _trim(body.address_zip)
    if body.country_code is not None:
        order.country_code = (body.country_code or "").upper() or None
    if body.company_registration is not None:
        order.company_registration = _trim(body.company_registration)
    if body.vat_id is not None:
        order.vat_id = _trim(body.vat_id)
    if body.company_name is not None:
        order.company_name = _trim(body.company_name)
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)

    _write_audit(
        db,
        admin_email=admin_email,
        order_public_id=public_id,
        action="order_patch",
        payload={"before": before, "after": patch_data},
        result="success",
    )

    audit = (
        db.query(AdminAuditLog)
        .filter(AdminAuditLog.order_public_id == public_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    out = _order_to_admin_out(order, audit)
    out.allfred_proforma_invoice_no = await _proforma_invoice_no(order)
    return out


@router.post("/orders/{public_id}/retry-workflow", response_model=OrderRetryWorkflowOut)
async def retry_workflow(
    public_id: str,
    body: OrderRetryWorkflowIn,
    request: Request,
    db: Session = Depends(get_db),
    admin_email: str = Depends(auth.require_admin_session),
):
    s = get_settings()
    order = db.query(Order).filter(Order.public_id == public_id).first()
    if not order:
        raise HTTPException(404, "Order not found")

    caps = compute_admin_capabilities(order)
    if not caps["can_retry_workflow"]:
        raise HTTPException(409, caps["retry_blocked_reason"] or "Retry not allowed")
    if order.status == OrderStatus.paid_processing.value:
        raise HTTPException(409, "Workflow právě běží — počkejte na dokončení.")

    enforce_per_hour(
        request,
        limit=s.admin_retry_rate_limit_per_hour,
        scope=f"admin-retry:{public_id}",
    )
    enforce_per_hour(
        request,
        limit=s.admin_retry_session_rate_limit_per_hour,
        scope=f"admin-retry-session:{admin_email}",
    )

    error_code_before = order.error_code
    order.status = OrderStatus.paid_processing.value
    order.last_error = None
    order.updated_at = datetime.utcnow()
    db.commit()

    try:
        do_hold_repair = body.repair_tito_hold or needs_legacy_hold_repair(order)
        if do_hold_repair and order.tito_quantity_held_at is None:
            await apply_public_release_hold(order)
            db.commit()
            db.refresh(order)

        proforma_paid = await is_proforma_paid_for_order(order)
        if proforma_paid:
            await process_single_paid_order(order, db)
            db.refresh(order)
            if order.status != OrderStatus.completed.value:
                order.status = OrderStatus.error.value
                db.commit()
        elif order.tito_quantity_held_at is not None:
            order.status = OrderStatus.awaiting_payment.value
            order.error_code = None
            order.error_step = None
            db.commit()
        else:
            raise RuntimeError("Hold repair failed or proforma not paid yet")

        result_msg = "success"
        if order.status == OrderStatus.completed.value:
            result_msg = "completed"
        elif order.status == OrderStatus.awaiting_payment.value:
            result_msg = "hold_repaired"
        else:
            result_msg = f"error:{order.error_code or 'unknown'}"

        _write_audit(
            db,
            admin_email=admin_email,
            order_public_id=public_id,
            action="retry_workflow",
            payload={
                "repair_tito_hold": body.repair_tito_hold,
                "error_code_before": error_code_before,
            },
            result=result_msg,
        )

        return OrderRetryWorkflowOut(
            public_id=order.public_id,
            status=order.status,
            message=result_msg,
        )
    except Exception as e:
        logger.exception("Admin retry failed for %s: %s", public_id, e)
        db.refresh(order)
        if order.status == OrderStatus.paid_processing.value:
            order.status = OrderStatus.error.value
            db.commit()
        _write_audit(
            db,
            admin_email=admin_email,
            order_public_id=public_id,
            action="retry_workflow",
            payload={
                "repair_tito_hold": body.repair_tito_hold,
                "error_code_before": error_code_before,
            },
            result=f"error: {e!s}"[:512],
        )
        raise HTTPException(502, f"Retry failed: {e}") from e
