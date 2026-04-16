"""Allfred Workspace GraphQL API."""

import logging
import re
from datetime import date, timedelta
from typing import Any, Literal, Optional

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


def allfred_ui_pdf_ready() -> bool:
    """True when Allfred web credentials are set (session cookie PDF download — viz Equilibrium n8n)."""
    s = get_settings()
    return bool((s.allfred_ui_email or "").strip() and (s.allfred_ui_password or "").strip())


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


def _quick_setup_anchor_date() -> date:
    """Datum vystavení: dnes, ale ne dřív než Allfred minimum (workspace business rules)."""
    s = get_settings()
    today = date.today()
    try:
        floor = date.fromisoformat(s.allfred_issue_date_not_before.strip())
    except ValueError:
        floor = today
    return max(today, floor)


def build_quick_setup_input(
    order: Order,
    *,
    document_type: Literal["INVOICE", "PROFORMA"] = "INVOICE",
    paid: Optional[bool] = None,
) -> dict[str, Any]:
    """Build QuickSetupInput for GraphQL (amounts in haléřích).

    PROFORMA = zálohová proforma (objednávka); INVOICE = finální faktura po zaplacení (cron).
    """
    s = get_settings()
    anchor = _quick_setup_anchor_date()
    today = anchor.isoformat()
    if document_type == "PROFORMA":
        due = (anchor + timedelta(days=s.allfred_proforma_due_days)).isoformat()
        issue_date = today
        due_date = due
        date_of_supply = today
        inv_paid = False if paid is None else paid
        inv_type = "PROFORMA"
    else:
        issue_date = due_date = date_of_supply = today
        inv_paid = True if paid is None else paid
        inv_type = "INVOICE"
    # Kontaktní osoba na dokladu (PDF) — allfred_contact_name; e-mail kontaktu = GMAIL_FROM_EMAIL
    c_fn, c_ln = _split_contact_name(s.allfred_contact_name)
    c_email = (s.gmail_from_email or "").strip()
    if not c_email:
        raise ValueError("gmail_from_email is required for Allfred client_data contact_email")

    street = (order.address_street or "").strip()
    city = (order.address_city or "").strip()
    zipc = (order.address_zip or "").strip()
    cc = (order.country_code or "CZ").upper()

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
            "contact_first_name": c_fn,
            "contact_last_name": c_ln,
            "contact_email": c_email,
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
            "contact_first_name": c_fn,
            "contact_last_name": c_ln,
            "contact_email": c_email,
        }

    uh = unit_price_hellers(order)
    if uh <= 0:
        raise ValueError("unit price must be positive for Allfred invoice")

    invoice_payload: dict[str, Any] = {
        "type": inv_type,
        "issue_date": issue_date,
        "due_date": due_date,
        "date_of_supply": date_of_supply,
        "workspace_company_id": s.allfred_workspace_company_id,
        "currency_iso": "CZK",
        "send_oi": False,
        "paid": inv_paid,
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


async def quick_setup_proforma_invoice(order: Order) -> dict[str, Any]:
    """Create client + project + outgoing PROFORMA via Allfred quick setup (order form)."""
    variables = {"input": build_quick_setup_input(order, document_type="PROFORMA")}
    data = await _graphql(QUICK_SETUP_MUTATION, variables)
    block = data.get("quickSetupClientProjectInvoice") or {}
    op = block.get("outgoingProformaInvoice")
    if not op or not op.get("id"):
        raise RuntimeError(f"quickSetupClientProjectInvoice (PROFORMA) unexpected response: {data}")
    return block


async def quick_setup_client_project_invoice(order: Order) -> dict[str, Any]:
    """Create client + project + final OutgoingInvoice (INVOICE) — po zaplacení zálohy."""
    variables = {"input": build_quick_setup_input(order, document_type="INVOICE")}
    data = await _graphql(QUICK_SETUP_MUTATION, variables)
    block = data.get("quickSetupClientProjectInvoice") or {}
    oi = block.get("outgoingInvoice")
    if not oi or not oi.get("id"):
        raise RuntimeError(f"quickSetupClientProjectInvoice (INVOICE) unexpected response: {data}")
    return block


def outgoing_proforma_pdf_download_url(proforma_id: str) -> str:
    """REST URL (Bearer často vrátí HTML; pro PDF použij UI session — download_proforma_pdf_bytes)."""
    s = get_settings()
    return f"https://{s.allfred_workspace}-api.allfred.io/outgoing-proforma-invoice/{proforma_id}/download"


async def _download_pdf_via_allfred_ui_session(resource_path: str) -> bytes:
    """GET PDF po přihlášení do Allfred web UI (stejně jako Allfred invoices - Equilibrium / n8n).

    ``resource_path`` bez úvodní lomítko, např. ``outgoing-invoice/20/download``.
    """
    s = get_settings()
    email = (s.allfred_ui_email or "").strip()
    password = s.allfred_ui_password or ""
    if not email or not password:
        raise RuntimeError("ALLFRED_UI_EMAIL and ALLFRED_UI_PASSWORD must be set for UI session PDF download")
    base = f"https://{s.allfred_workspace}-api.allfred.io"
    path = resource_path.lstrip("/")
    async with httpx.AsyncClient(base_url=base, follow_redirects=True, timeout=120.0) as client:
        r1 = await client.get("/login")
        r1.raise_for_status()
        m = re.search(r'name="_token"\s+value="([^"]+)"', r1.text)
        if not m:
            raise RuntimeError("CSRF token not found on Allfred login page")
        token = m.group(1)
        r2 = await client.post(
            "/login",
            data={
                "_token": token,
                "email": email,
                "password": password,
                "remember": "on",
            },
        )
        if r2.status_code >= 400:
            raise RuntimeError(f"Allfred UI login failed: HTTP {r2.status_code}")
        r3 = await client.get(f"/{path}")
        r3.raise_for_status()
        data = r3.content
    if not data.startswith(b"%PDF"):
        head = data[:220].decode("utf-8", errors="replace")
        if "<html" in head.lower():
            raise RuntimeError("Allfred PDF URL returned HTML (login failed or insufficient rights)")
        raise RuntimeError(f"Expected PDF from Allfred UI, got: {head!r}")
    return data


def _ensure_pdf_magic(data: bytes, context: str) -> None:
    if not data.startswith(b"%PDF"):
        head = data[:120].decode("utf-8", errors="replace")
        raise RuntimeError(f"{context}: očekáváno PDF, server vrátil: {head!r}")


async def fetch_outgoing_invoice_download_url(invoice_id: str) -> Optional[str]:
    data = await _graphql(OUTGOING_INVOICE_PDF_QUERY, {"id": str(invoice_id)})
    oi = data.get("outgoingInvoice") or {}
    ipdf = oi.get("invoicePdf") or {}
    return ipdf.get("download")


async def download_pdf_from_url(url: str) -> bytes:
    """Download PDF; retry with Bearer if URL requires workspace auth."""
    s = get_settings()
    accept = {"Accept": "application/pdf,*/*;q=0.1"}
    headers = dict(accept)
    if s.allfred_api_key and "allfred.io" in url:
        headers["Authorization"] = f"Bearer {s.allfred_api_key}"
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        if r.status_code == 401 and s.allfred_api_key:
            r = await client.get(
                url,
                headers={**accept, "Authorization": f"Bearer {s.allfred_api_key}"},
            )
        r.raise_for_status()
        return r.content


async def download_proforma_pdf_bytes(proforma_id: str) -> bytes:
    """Stažení PDF proformy. GraphQL nemá invoicePdf u proformy — Equilibrium používá UI session + GET."""
    if allfred_ui_pdf_ready():
        errs: list[str] = []
        for rel in (
            f"outgoing-proforma-invoice/{proforma_id}/download",
            f"proforma-invoice/{proforma_id}/download",
        ):
            try:
                return await _download_pdf_via_allfred_ui_session(rel)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    errs.append(f"{rel}: 404")
                    continue
                raise
            except RuntimeError as e:
                errs.append(f"{rel}: {e!s}")
                continue
        raise RuntimeError(
            "Proforma PDF (UI session): žádná cesta nevrátila PDF — " + "; ".join(errs)
        )

    url = outgoing_proforma_pdf_download_url(proforma_id)
    data = await download_pdf_from_url(url)
    _ensure_pdf_magic(data, "Allfred proforma PDF (Bearer)")
    return data


async def resolve_outgoing_invoice_pdf_bytes(outgoing_invoice: dict[str, Any]) -> Optional[bytes]:
    """PDF finální faktury — při nastaveném UI stejně jako Equilibrium (session), jinak URL z GraphQL."""
    oid = outgoing_invoice.get("id")
    if oid and allfred_ui_pdf_ready():
        try:
            return await _download_pdf_via_allfred_ui_session(f"outgoing-invoice/{oid}/download")
        except Exception as e:
            logger.warning("Allfred UI session PDF failed for invoice %s: %s", oid, e)
    ipdf = outgoing_invoice.get("invoicePdf") or {}
    url = ipdf.get("download")
    if not url and oid:
        url = await fetch_outgoing_invoice_download_url(str(oid))
    if not url:
        logger.warning("Allfred outgoing invoice %s has no PDF download URL", oid)
        return None
    data = await download_pdf_from_url(url)
    if data.startswith(b"%PDF"):
        return data
    logger.warning("Allfred invoice %s: download URL did not return raw PDF (use ALLFRED_UI_EMAIL/PASSWORD)", oid)
    return None


async def download_outgoing_invoice_pdf_by_id(invoice_id: str) -> Optional[bytes]:
    if allfred_ui_pdf_ready():
        try:
            return await _download_pdf_via_allfred_ui_session(f"outgoing-invoice/{invoice_id}/download")
        except Exception as e:
            logger.warning("Allfred UI session invoice PDF failed: %s", e)
    url = await fetch_outgoing_invoice_download_url(invoice_id)
    if not url:
        return None
    data = await download_pdf_from_url(url)
    return data if data.startswith(b"%PDF") else None
