const jsonHeaders = { 'Content-Type': 'application/json' }

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: {
      ...jsonHeaders,
      ...(init?.headers || {}),
    },
  })
  if (res.status === 401) {
    const next = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.href = `/auth/login?next=${next}`
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export type AdminMe = { email: string }

export type OrderAdminListItem = {
  public_id: string
  created_at: string
  full_name: string
  email: string
  status: string
  error_code: string | null
  error_label: string | null
  allfred_proforma_id: string | null
  ticket_quantity: number
}

export type OrderAdminListOut = {
  items: OrderAdminListItem[]
  total: number
  skip: number
  limit: number
}

export type AdminAuditEntry = {
  id: number
  created_at: string
  admin_email: string
  action: string
  payload_json: string | null
  result: string
}

export type OrderAdminOut = {
  public_id: string
  created_at: string
  updated_at: string
  full_name: string
  email: string
  status: string
  ticket_quantity: number
  tito_release_title: string
  tito_release_slug: string
  error_code: string | null
  error_step: string | null
  error_label: string | null
  last_error: string | null
  can_edit: boolean
  can_retry_workflow: boolean
  retry_blocked_reason: string | null
  partial_failure_hint: string | null
  needs_legacy_hold_repair: boolean
  allfred_proforma_id: string | null
  allfred_proforma_invoice_no: string | null
  allfred_final_invoice_id: string | null
  tito_discount_code: string | null
  tito_invoice_release_id: number | null
  tito_invoice_release_slug: string | null
  tito_quantity_held_at: string | null
  tito_invoice_quantity_patched_at: string | null
  paid_customer_email_sent_at: string | null
  invoice_to_company: boolean
  company_name: string | null
  company_registration: string | null
  vat_id: string | null
  address_street: string | null
  address_city: string | null
  address_zip: string | null
  country_code: string | null
  admin_url: string
  allfred_proforma_url: string | null
  allfred_final_invoice_url: string | null
  tito_release_url: string | null
  tito_invoice_release_url: string | null
  audit_log: AdminAuditEntry[]
}

export function getAuthMe(): Promise<AdminMe> {
  return adminFetch<AdminMe>('/auth/me')
}

export function logout(): Promise<{ ok: boolean }> {
  return adminFetch('/auth/logout', { method: 'POST' })
}

export function listOrders(skip = 0, limit = 50): Promise<OrderAdminListOut> {
  return adminFetch(`/api/admin/orders?skip=${skip}&limit=${limit}`)
}

export function getOrder(publicId: string): Promise<OrderAdminOut> {
  return adminFetch(`/api/admin/orders/${publicId}`)
}

export function patchOrder(publicId: string, body: Record<string, unknown>): Promise<OrderAdminOut> {
  return adminFetch(`/api/admin/orders/${publicId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function retryWorkflow(
  publicId: string,
  repairTitoHold: boolean,
): Promise<{ public_id: string; status: string; message: string }> {
  return adminFetch(`/api/admin/orders/${publicId}/retry-workflow`, {
    method: 'POST',
    body: JSON.stringify({ repair_tito_hold: repairTitoHold }),
  })
}
