"""Single-line billing address for CRM / e-mail context."""

from app.models import Order


def billing_address_one_line(order: Order) -> str:
    street = (order.address_street or "").strip()
    zip_code = (order.address_zip or "").strip()
    city = (order.address_city or "").strip()
    line2 = " ".join(p for p in [zip_code, city] if p)
    return ", ".join(p for p in [street, line2] if p)
