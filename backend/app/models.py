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

    # Billing
    invoice_to_company: Mapped[bool] = mapped_column(Boolean, default=False)
    address_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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

    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipedrive_person_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    pipedrive_org_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
