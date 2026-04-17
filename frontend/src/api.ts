const base = ''

export type Release = {
  id: number
  slug: string
  title: string
  price: number | null
  state: string | null
  secret: boolean | null
}

export type Country = { code: string; name_en: string }

export async function getEventMeta(): Promise<{ show_prices_ex_tax: boolean; currency: string }> {
  const r = await fetch(`${base}/api/event`)
  if (!r.ok) throw new Error('event')
  return r.json()
}

export async function getReleases(): Promise<Release[]> {
  const r = await fetch(`${base}/api/releases`)
  if (!r.ok) throw new Error('releases')
  return r.json()
}

export async function getCountries(): Promise<Country[]> {
  const r = await fetch(`${base}/api/countries`)
  if (!r.ok) throw new Error('countries')
  return r.json()
}

/** Request aborted (browser) nebo 504 z API — zobrazit lookupTimeout. */
export function isAresLookupTimeout(e: unknown): boolean {
  if (e instanceof DOMException && e.name === 'AbortError') return true
  if (e instanceof Error && e.message === 'LOOKUP_TIMEOUT') return true
  return false
}

export async function lookupAres(ico: string, country: string) {
  const q = new URLSearchParams({ ico, country })
  const ac = new AbortController()
  const tid = setTimeout(() => ac.abort(), 40000)
  try {
    const r = await fetch(`${base}/api/ares/lookup?${q}`, { signal: ac.signal })
    if (r.status === 404) return null
    if (r.status === 504) throw new Error('LOOKUP_TIMEOUT')
    if (!r.ok) throw new Error('ares')
    return r.json()
  } finally {
    clearTimeout(tid)
  }
}

export type OrderPayload = {
  full_name: string
  email: string
  ticket_quantity: number
  tito_release_id: number
  tito_release_slug: string
  tito_release_title: string
  /** Jednotková cena vstupenky v Kč (pro Allfred fakturu) */
  ticket_unit_price_czk?: number | null
  invoice_to_company: boolean
  address_street?: string | null
  address_city?: string | null
  address_zip?: string | null
  country_code?: string | null
  company_registration?: string | null
  vat_id?: string | null
  company_name?: string | null
}

export async function createOrder(body: OrderPayload) {
  const r = await fetch(`${base}/api/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error((data as { detail?: string }).detail || 'order failed')
  return data
}
