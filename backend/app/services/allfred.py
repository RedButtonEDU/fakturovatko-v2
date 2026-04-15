"""Allfred Workspace GraphQL API."""

import logging
from datetime import date
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.models import Order

logger = logging.getLogger(__name__)

OUTGOING_PROFORMA_QUERY = """
query OutgoingProformaInvoices($page: Int!) {
  outgoingProformaInvoices(page: $page) {
    paginatorInfo { hasMorePages currentPage }
    data {
      id invoice_no issue_date due_date paid_at
      projects { id title code }
      client { id name }
    }
  }
}
"""

OUTGOING_INVOICES_QUERY = """
query OutgoingInvoices($page: Int!) {
  outgoingInvoices(page: $page) {
    paginatorInfo { hasMorePages currentPage }
    data {
      id invoice_no issue_date paid_at
      projects { id title code }
      client { id name }
    }
  }
}
"""

# quickSetupClientProjectInvoice → QuickSetupResult (introspection 2026-04):
# optional outgoingInvoice vs outgoingProformaInvoice depending on QuickSetupInvoiceInput.type (INVOICE | PROFORMA).
QUICK_SETUP_MUTATION = """
mutation QuickSetup($input: QuickSetupInput!) {
  quickSetupClientProjectInvoice(input: $input) {
    client { id name }
    project { id title code }
    outgoingInvoice {
      id
      invoice_no
      invoicePdf { download preview }
    }
    outgoingProformaInvoice {
      id
      invoice_no
    }
  }
}
"""

OUTGOING_INVOICE_PDF_QUERY = """
query OutgoingInvoicePdf($id: ID!) {
  outgoingInvoice(id: $id) {
    id
    invoicePdf { download preview }
  }
}
"""


def _base_url(workspace: str) -> str:
    return f"https://{workspace}-api.allfred.io/workspace-api"


async def _graphql(query: str, variables: Optional[dict] = None) -> dict[str, Any]:
    s = get_settings()
    if not s.allfred_api_key:
        raise RuntimeError("ALLFRED_API_KEY is not set")
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            _base_url(s.allfred_workspace),
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {s.allfred_api_key}",
            },
        )
        r.raise_for_status()
        data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"Allfred GraphQL errors: {data['errors']}")
    return data.get("data") or {}


async def fetch_all_proformas() -> list[dict[str, Any]]:
    """Paginate all outgoing proforma invoices."""
    all_rows: list[dict[str, Any]] = []
    page = 1
    while True:
        data = await _graphql(OUTGOING_PROFORMA_QUERY, {"page": page})
        block = data.get("outgoingProformaInvoices") or {}
        rows = block.get("data") or []
        all_rows.extend(rows)
        info = block.get("paginatorInfo") or {}
        if not info.get("hasMorePages"):
            break
        page += 1
        if page > 500:
            break
    return all_rows


async def fetch_all_invoices() -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    page = 1
    while True:
        data = await _graphql(OUTGOING_INVOICES_QUERY, {"page": page})
        block = data.get("outgoingInvoices") or {}
        rows = block.get("data") or []
        all_rows.extend(rows)
        info = block.get("paginatorInfo") or {}
        if not info.get("hasMorePages"):
            break
        page += 1
        if page > 500:
            break
    return all_rows


def find_project_ids(proforma: dict) -> list[str]:
    projects = proforma.get("projects") or []
    return [str(p.get("id")) for p in projects if isinstance(p, dict) and p.get("id")]


def mock_create_proforma_invoice(order_public_id: str) -> dict[str, str]:
    """Placeholder until Allfred exposes create mutation."""
    return {
        "id": f"mock-proforma-{order_public_id[:8]}",
        "project_id": f"mock-project-{order_public_id[:8]}",
    }


def quick_setup_ready() -> bool:
    """True when env has API key + IDs required by quickSetupClientProjectInvoice (QuickSetupInput)."""
    s = get_settings()
    return bool(
        s.allfred_api_key
        and s.allfred_workspace_company_id
        and s.allfred_team_id
        and s.allfred_project_manager_id
        and s.allfred_quick_setup_error_email
    )


def _split_contact_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        return "?", "?"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], parts[-1]


def unit_price_hellers(order: Order) -> int:
    s = get_settings()
    czk = order.ticket_unit_price_czk if order.ticket_unit_price_czk is not None else s.allfred_fallback_unit_price_czk
    return int(round(float(czk) * 100))


def build_quick_setup_input(order: Order) -> dict[str, Any]:
    """Build QuickSetupInput for GraphQL (amounts in haléřích)."""
    s = get_settings()
    today = date.today().isoformat()
    fn, ln = _split_contact_name(order.full_name)
    street = (order.address_street or "").strip()
    city = (order.address_city or "").strip()
    zipc = (order.address_zip or "").strip()
    cc = (order.country_code or "CZ").upper()
    email = order.email.strip()

    if order.invoice_to_company:
        cn = (order.company_name or "").strip() or order.full_name.strip()
        client_data: dict[str, Any] = {
            "client_name": cn,
            "legal_name": cn,
            "street": street,
            "city": city,
            "zip": zipc,
            "country_iso": cc,
            "language": "cz",
            "contact_first_name": fn,
            "contact_last_name": ln,
            "contact_email": email,
        }
        reg = (order.company_registration or "").strip()
        if reg:
            client_data["reg_no"] = reg
        vat = (order.vat_id or "").strip()
        if vat:
            client_data["vat_no"] = vat
    else:
        nm = order.full_name.strip()
        client_data = {
            "client_name": nm,
            "legal_name": nm,
            "street": street,
            "city": city,
            "zip": zipc,
            "country_iso": cc,
            "language": "cz",
            "contact_first_name": fn,
            "contact_last_name": ln,
            "contact_email": email,
        }

    uh = unit_price_hellers(order)
    if uh <= 0:
        raise ValueError("unit price must be positive for Allfred invoice")

    # QuickSetupInvoiceTypeEnum: INVOICE | PROFORMA (cron flow needs final invoice + PDF on OutgoingInvoice)
    invoice_payload: dict[str, Any] = {
        "type": "INVOICE",
        "issue_date": today,
        "due_date": today,
        "date_of_supply": today,
        "workspace_company_id": s.allfred_workspace_company_id,
        "currency_iso": "CZK",
        "send_oi": False,
        "paid": True,
        "vat_rate": s.allfred_invoice_vat_rate,
        "invoice_items": [
            {
                "description": f"{order.tito_release_title} — Exponential Summit 2026",
                "unit_price": uh,
                "quantity": float(order.ticket_quantity),
            }
        ],
        "note": f"Objednávka Exponential Summit {order.public_id}",
    }
    if s.allfred_workspace_bank_account_id:
        invoice_payload["workspace_bank_account_id"] = s.allfred_workspace_bank_account_id
    if s.allfred_invoice_sequence_id:
        invoice_payload["invoice_sequence_id"] = s.allfred_invoice_sequence_id
    if s.allfred_vat_reverse_charge is not None:
        invoice_payload["vat_reverse_charge"] = s.allfred_vat_reverse_charge

    inp: dict[str, Any] = {
        "client_data": client_data,
        "project": {
            "title": f"Exponential Summit 2026 — {order.tito_release_title} ({order.public_id[:8]})",
            "billable": True,
            "project_manager_id": s.allfred_project_manager_id,
            "team_id": s.allfred_team_id,
            "start_date": today,
        },
        "invoice": invoice_payload,
        "error_email": s.allfred_quick_setup_error_email,
    }
    return inp


async def quick_setup_client_project_invoice(order: Order) -> dict[str, Any]:
    """Create client + project + outgoing invoice via Allfred quick setup."""
    variables = {"input": build_quick_setup_input(order)}
    data = await _graphql(QUICK_SETUP_MUTATION, variables)
    block = data.get("quickSetupClientProjectInvoice") or {}
    oi = block.get("outgoingInvoice")
    if not oi or not oi.get("id"):
        raise RuntimeError(f"quickSetupClientProjectInvoice unexpected response: {data}")
    return block


async def fetch_outgoing_invoice_download_url(invoice_id: str) -> Optional[str]:
    data = await _graphql(OUTGOING_INVOICE_PDF_QUERY, {"id": str(invoice_id)})
    oi = data.get("outgoingInvoice") or {}
    ipdf = oi.get("invoicePdf") or {}
    return ipdf.get("download")


async def download_pdf_from_url(url: str) -> bytes:
    """Download PDF; retry with Bearer if URL requires workspace auth."""
    s = get_settings()
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        r = await client.get(url)
        if r.status_code == 401 and s.allfred_api_key:
            r = await client.get(
                url,
                headers={"Authorization": f"Bearer {s.allfred_api_key}"},
            )
        r.raise_for_status()
        return r.content


async def resolve_outgoing_invoice_pdf_bytes(outgoing_invoice: dict[str, Any]) -> Optional[bytes]:
    """Use download URL from mutation response or query outgoingInvoice by id."""
    ipdf = outgoing_invoice.get("invoicePdf") or {}
    url = ipdf.get("download")
    oid = outgoing_invoice.get("id")
    if not url and oid:
        url = await fetch_outgoing_invoice_download_url(str(oid))
    if not url:
        logger.warning("Allfred outgoing invoice %s has no PDF download URL", oid)
        return None
    return await download_pdf_from_url(url)


async def download_outgoing_invoice_pdf_by_id(invoice_id: str) -> Optional[bytes]:
    url = await fetch_outgoing_invoice_download_url(invoice_id)
    if not url:
        return None
    return await download_pdf_from_url(url)
