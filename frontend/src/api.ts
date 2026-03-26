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

export async function lookupAres(ico: string, country: string) {
  const q = new URLSearchParams({ ico, country })
  const r = await fetch(`${base}/api/ares/lookup?${q}`)
  if (r.status === 404) return null
  if (!r.ok) throw new Error('ares')
  return r.json()
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
