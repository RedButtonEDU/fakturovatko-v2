from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class OrderCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=512)
    email: EmailStr
    ticket_quantity: int = Field(..., ge=1, le=50)
    tito_release_id: int
    tito_release_slug: str = Field(..., min_length=1, max_length=255)
    tito_release_title: str = Field(..., min_length=1, max_length=512)
    ticket_unit_price_czk: Optional[float] = Field(None, gt=0)
    invoice_to_company: bool = False
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    company_registration: Optional[str] = None
    vat_id: Optional[str] = None
    company_name: Optional[str] = None


class OrderOut(BaseModel):
    public_id: str
    status: str
    message: str = "ok"
    allfred_proforma_invoice_no: Optional[str] = None


class ReleaseOut(BaseModel):
    id: int
    slug: str
    title: str
    price: Optional[float] = None
    state: Optional[str] = None
    secret: Optional[bool] = None
    quantity_remaining: Optional[int] = None
    min_per_order: Optional[int] = None
    max_per_order: Optional[int] = None


class CountryOut(BaseModel):
    code: str
    name_en: str


class AresLookupOut(BaseModel):
    company_name: str = ""
    street: str = ""
    city: str = ""
    zip: str = ""
    vat_id: Optional[str] = None


class OrderAdminPatch(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=512)
    email: Optional[EmailStr] = None
    invoice_to_company: Optional[bool] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    company_registration: Optional[str] = None
    vat_id: Optional[str] = None
    company_name: Optional[str] = None


class OrderAdminListItem(BaseModel):
    public_id: str
    created_at: str
    full_name: str
    email: str
    status: str
    error_code: Optional[str] = None
    error_label: Optional[str] = None
    allfred_proforma_id: Optional[str] = None
    ticket_quantity: int


class OrderAdminListOut(BaseModel):
    items: list[OrderAdminListItem]
    total: int
    skip: int
    limit: int


class AdminAuditEntryOut(BaseModel):
    id: int
    created_at: str
    admin_email: str
    action: str
    payload_json: Optional[str] = None
    result: str


class OrderAdminOut(BaseModel):
    public_id: str
    created_at: str
    updated_at: str
    full_name: str
    email: str
    status: str
    ticket_quantity: int
    tito_release_title: str
    tito_release_slug: str
    error_code: Optional[str] = None
    error_step: Optional[str] = None
    error_label: Optional[str] = None
    last_error: Optional[str] = None
    can_edit: bool
    can_retry_workflow: bool
    retry_blocked_reason: Optional[str] = None
    partial_failure_hint: Optional[str] = None
    needs_legacy_hold_repair: bool = False
    allfred_proforma_id: Optional[str] = None
    allfred_proforma_invoice_no: Optional[str] = None
    allfred_final_invoice_id: Optional[str] = None
    tito_discount_code: Optional[str] = None
    tito_invoice_release_id: Optional[int] = None
    tito_invoice_release_slug: Optional[str] = None
    tito_quantity_held_at: Optional[str] = None
    tito_invoice_quantity_patched_at: Optional[str] = None
    paid_customer_email_sent_at: Optional[str] = None
    invoice_to_company: bool
    company_name: Optional[str] = None
    company_registration: Optional[str] = None
    vat_id: Optional[str] = None
    address_street: Optional[str] = None
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    country_code: Optional[str] = None
    admin_url: str
    allfred_proforma_url: Optional[str] = None
    allfred_final_invoice_url: Optional[str] = None
    tito_release_url: Optional[str] = None
    tito_invoice_release_url: Optional[str] = None
    audit_log: list[AdminAuditEntryOut] = []


class OrderRetryWorkflowIn(BaseModel):
    repair_tito_hold: bool = False


class OrderRetryWorkflowOut(BaseModel):
    public_id: str
    status: str
    message: str
