"""Create orders (Allfred PROFORMA + email)."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.debug_ndjson import agent_log
from app.db import get_db
from app.models import Order, OrderStatus
from app.schemas import OrderCreate, OrderOut
from app.services import allfred as allfred_svc
from app.services import email as email_svc

logger = logging.getLogger(__name__)

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
async def create_order(body: OrderCreate, db: Session = Depends(get_db)):
    _validate_payload(body)
    s = get_settings()
    if not allfred_svc.quick_setup_ready():
        raise HTTPException(
            503,
            "Allfred quick setup is not configured. Set ALLFRED_API_KEY, ALLFRED_WORKSPACE_COMPANY_ID, "
            "ALLFRED_TEAM_ID, ALLFRED_PROJECT_MANAGER_ID, and ALLFRED_QUICK_SETUP_ERROR_EMAIL.",
        )
    if not allfred_svc.allfred_ui_pdf_ready():
        raise HTTPException(
            503,
            "PDF příloha e-mailu: nastavte ALLFRED_UI_EMAIL a ALLFRED_UI_PASSWORD (webové přihlášení do Allfredu, "
            "stejně jako v projektu „Allfred invoices – Equilibrium“ / n8n). Samotný ALLFRED_API_KEY na stažení PDF nestačí.",
        )

    public_id = str(uuid.uuid4())

    order_for_api = Order(
        public_id=public_id,
        full_name=body.full_name.strip(),
        email=body.email.lower().strip(),
        ticket_quantity=body.ticket_quantity,
        tito_release_id=body.tito_release_id,
        tito_release_slug=body.tito_release_slug.strip(),
        tito_release_title=body.tito_release_title.strip(),
        ticket_unit_price_czk=body.ticket_unit_price_czk,
        invoice_to_company=body.invoice_to_company,
        address_street=_trim(body.address_street),
        address_city=_trim(body.address_city),
        address_zip=_trim(body.address_zip),
        country_code=(body.country_code or "").upper() or None,
        company_registration=body.company_registration,
        vat_id=body.vat_id,
        company_name=body.company_name,
        status=OrderStatus.awaiting_payment.value,
        updated_at=datetime.utcnow(),
    )

    try:
        block = await allfred_svc.quick_setup_proforma_invoice(order_for_api)
    except Exception as e:
        logger.exception("Allfred quickSetup PROFORMA failed: %s", e)
        raise HTTPException(502, f"Allfred: nelze vytvořit zálohovou fakturu: {e!s}") from e

    proforma_id = str(block["outgoingProformaInvoice"]["id"])
    project_id = str(block["project"]["id"])

    try:
        pdf_bytes = await allfred_svc.download_proforma_pdf_bytes(proforma_id)
    except Exception as e:
        logger.exception("Proforma PDF download failed (id=%s): %s", proforma_id, e)
        raise HTTPException(
            502,
            f"Proforma v Allfredu vznikla (id {proforma_id}), ale PDF se nepodařilo stáhnout: {e!s}",
        ) from e

    order = Order(
        public_id=public_id,
        full_name=body.full_name.strip(),
        email=body.email.lower().strip(),
        ticket_quantity=body.ticket_quantity,
        tito_release_id=body.tito_release_id,
        tito_release_slug=body.tito_release_slug.strip(),
        tito_release_title=body.tito_release_title.strip(),
        ticket_unit_price_czk=body.ticket_unit_price_czk,
        invoice_to_company=body.invoice_to_company,
        address_street=_trim(body.address_street),
        address_city=_trim(body.address_city),
        address_zip=_trim(body.address_zip),
        country_code=(body.country_code or "").upper() or None,
        company_registration=body.company_registration,
        vat_id=body.vat_id,
        company_name=body.company_name,
        status=OrderStatus.awaiting_payment.value,
        allfred_proforma_id=proforma_id,
        allfred_project_id=project_id,
        mock_proforma_note=None,
        updated_at=datetime.utcnow(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    subject = "Exponential Summit – zálohová faktura (proforma)"
    text = (
        f"Dobrý den,\n\n"
        f"děkujeme za objednávku. V příloze je zálohová faktura z Allfredu.\n"
        f"Číslo objednávky: {public_id}\n\n"
        f"Tým Exponential Summit"
    )
    try:
        if s.gmail_refresh_token:
            # region agent log
            _dom = order.email.split("@", 1)[-1] if "@" in order.email else "?"
            agent_log(
                "H4",
                "api_orders.py:create_order",
                "before_send_email",
                {"public_id_prefix": public_id[:8], "recipient_domain": _dom},
            )
            # endregion
            email_svc.send_email(
                order.email,
                subject,
                text,
                attachment_bytes=pdf_bytes,
                attachment_name=f"proforma-{public_id[:8]}.pdf",
            )
    except Exception as e:
        order.last_error = f"email: {e}"
        db.commit()
        raise HTTPException(503, f"Could not send email: {e}") from e

    msg = "Proforma vytvořena v Allfredu a odeslána e-mailem."
    if not s.gmail_refresh_token:
        msg = "Proforma vytvořena v Allfredu (GMAIL_REFRESH_TOKEN není nastaven — e-mail neodeslán)."

    return OrderOut(public_id=public_id, status=order.status, message=msg)
