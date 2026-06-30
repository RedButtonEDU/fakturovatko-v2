"""SQLAlchemy models for orders."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OrderStatus(str, enum.Enum):
    pending_proforma = "pending_proforma"
    proforma_sent = "proforma_sent"
    awaiting_payment = "awaiting_payment"
    paid_processing = "paid_processing"
    completed = "completed"
    cancelled = "cancelled"
    error = "error"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Customer
    full_name: Mapped[str] = mapped_column(String(512))
    email: Mapped[str] = mapped_column(String(320), index=True)

    # Ticket
    ticket_quantity: Mapped[int] = mapped_column(Integer)
    tito_release_id: Mapped[int] = mapped_column(Integer)
    tito_release_slug: Mapped[str] = mapped_column(String(255))
    tito_release_title: Mapped[str] = mapped_column(String(512))
    # Jednotková cena vstupenky v Kč (pro Allfred fakturu); z frontendu při objednávce
    ticket_unit_price_czk: Mapped[Optional[float]] = mapped_column(nullable=True)

    # Billing
    invoice_to_company: Mapped[bool] = mapped_column(Boolean, default=False)
    address_street: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address_city: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address_zip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    company_registration: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # IČO
    vat_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # DIČ
    company_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Allfred / workflow
    status: Mapped[str] = mapped_column(String(64), default=OrderStatus.pending_proforma.value, index=True)
    allfred_proforma_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    allfred_project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    allfred_final_invoice_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mock_proforma_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tito_discount_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tito_discount_code_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Ti.to invoice clone (title contains "invoice") — voucher pool after payment
    tito_invoice_release_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tito_invoice_release_slug: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Audit: hold on public release after order (quantity PATCH)
    tito_public_quantity_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tito_public_quantity_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tito_quantity_held_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tito_quantity_released_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    tito_invoice_quantity_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tito_invoice_quantity_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tito_invoice_quantity_patched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    error_step: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    paid_customer_email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipedrive_person_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pipedrive_org_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    admin_email: Mapped[str] = mapped_column(String(320))
    order_public_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(String(512))
