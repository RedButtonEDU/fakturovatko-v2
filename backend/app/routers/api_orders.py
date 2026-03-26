"""Create orders (proforma mock + email)."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Order, OrderStatus
from app.schemas import OrderCreate, OrderOut
from app.services import email as email_svc
from app.services.allfred import mock_create_proforma_invoice
from app.services.pdf_mock import MOCK_PDF_BYTES

router = APIRouter(prefix="/api", tags=["orders"])


def _trim(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    t = s.strip()
    return t or None


def _validate_payload(body: OrderCreate) -> None:
    def _addr_ok() -> bool:
        return bool(
            (body.address_street or "").strip()
            and (body.address_city or "").strip()
            and (body.address_zip or "").strip()
        )

    if not body.country_code:
        raise HTTPException(422, "country_code is required")

    if not body.invoice_to_company:
        if not _addr_ok():
            raise HTTPException(422, "address_street, address_city, address_zip are required")
    else:
        if not (body.company_registration or "").strip():
            raise HTTPException(422, "company_registration (IČO) is required")
        if not (body.company_name or "").strip():
            raise HTTPException(422, "company_name is required")
        if not _addr_ok():
            raise HTTPException(422, "address_street, address_city, address_zip are required")


@router.post("/orders", response_model=OrderOut)
def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    _validate_payload(body)
    s = get_settings()
    public_id = str(uuid.uuid4())

    mock = mock_create_proforma_invoice(public_id)

    order = Order(
        public_id=public_id,
        full_name=body.full_name.strip(),
        email=body.email.lower().strip(),
        ticket_quantity=body.ticket_quantity,
        tito_release_id=body.tito_release_id,
        tito_release_slug=body.tito_release_slug.strip(),
        tito_release_title=body.tito_release_title.strip(),
        invoice_to_company=body.invoice_to_company,
        address_street=_trim(body.address_street),
        address_city=_trim(body.address_city),
        address_zip=_trim(body.address_zip),
        country_code=(body.country_code or "").upper() or None,
        company_registration=body.company_registration,
        vat_id=body.vat_id,
        company_name=body.company_name,
        status=OrderStatus.awaiting_payment.value,
        allfred_proforma_id=mock["id"],
        allfred_project_id=mock["project_id"],
        mock_proforma_note="Mock PDF until Allfred create API is available",
        updated_at=datetime.utcnow(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    subject = "Exponential Summit – zálohová faktura (proforma)"
    text = (
        f"Dobrý den,\n\n"
        f"děkujeme za objednávku. V příloze je zálohová faktura (náhled).\n"
        f"Číslo objednávky: {public_id}\n\n"
        f"Tým Exponential Summit"
    )
    try:
        if s.gmail_refresh_token:
            email_svc.send_email(
                order.email,
                subject,
                text,
                attachment_bytes=MOCK_PDF_BYTES,
                attachment_name=f"proforma-{public_id[:8]}.pdf",
            )
    except Exception as e:
        order.last_error = f"email: {e}"
        db.commit()
        raise HTTPException(503, f"Could not send email: {e}") from e

    return OrderOut(public_id=public_id, status=order.status, message="Proforma odeslána e-mailem.")
