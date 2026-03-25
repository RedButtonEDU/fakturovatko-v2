"""Allfred Workspace GraphQL API."""

from typing import Any, Optional

import httpx

from app.config import get_settings

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
