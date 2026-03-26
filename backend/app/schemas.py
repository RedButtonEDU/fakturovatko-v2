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


class ReleaseOut(BaseModel):
    id: int
    slug: str
    title: str
    price: Optional[float] = None
    state: Optional[str] = None
    secret: Optional[bool] = None


class CountryOut(BaseModel):
    code: str
    name_en: str
