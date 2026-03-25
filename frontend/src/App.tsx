import { useEffect, useMemo, useState } from 'react'
import './App.css'
import {
  createOrder,
  getCountries,
  getEventMeta,
  getReleases,
  lookupAres,
  type Country,
  type Release,
} from './api'
import { countryDisplayName, detectLang, orderCountriesForDisplay, t, type Lang } from './i18n'

const VAT = 0.21

function unitPrices(
  unit: number | null | undefined,
  showPricesExTax: boolean,
): { ex: number; inc: number } {
  if (unit == null || Number.isNaN(unit)) return { ex: 0, inc: 0 }
  if (showPricesExTax) {
    return { ex: unit, inc: unit * (1 + VAT) }
  }
  return { ex: unit / (1 + VAT), inc: unit }
}

function formatMoney(n: number, currency: string) {
  return new Intl.NumberFormat('cs-CZ', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(n)
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => detectLang())
  const [releases, setReleases] = useState<Release[]>([])
  const [countries, setCountries] = useState<Country[]>([])
  const [eventMeta, setEventMeta] = useState<{ show_prices_ex_tax: boolean; currency: string } | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [releaseId, setReleaseId] = useState<number | ''>('')
  /** String so user can clear the field and type a new number; blur normalizes to 1–50 */
  const [qtyInput, setQtyInput] = useState('1')
  const [invoiceCompany, setInvoiceCompany] = useState(false)
  const [address, setAddress] = useState('')
  const [country, setCountry] = useState('CZ')
  const [ico, setIco] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [vatId, setVatId] = useState('')
  const [icoLoading, setIcoLoading] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [ev, rel, co] = await Promise.all([getEventMeta(), getReleases(), getCountries()])
        if (cancelled) return
        setEventMeta(ev)
        setReleases(rel)
        setCountries(co)
      } catch {
        setErr('Nelze načíst data. Zkuste to prosím znovu.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const selectedRelease = useMemo(
    () => releases.find((r) => r.id === releaseId) ?? null,
    [releases, releaseId],
  )

  const quantityForTotals = useMemo(() => {
    const n = parseInt(qtyInput, 10)
    if (qtyInput === '' || Number.isNaN(n)) return 0
    return Math.min(50, Math.max(1, n))
  }, [qtyInput])

  const linePrices = useMemo(() => {
    if (!eventMeta || !selectedRelease) return null
    const u = unitPrices(selectedRelease.price, eventMeta.show_prices_ex_tax)
    return {
      unitEx: u.ex,
      unitInc: u.inc,
      totalEx: u.ex * quantityForTotals,
      totalInc: u.inc * quantityForTotals,
    }
  }, [eventMeta, selectedRelease, quantityForTotals])

  const countriesForUi = useMemo(() => orderCountriesForDisplay(countries, lang), [countries, lang])

  async function onLookupIco() {
    if (!ico.trim()) return
    setIcoLoading(true)
    setErr(null)
    try {
      const data = await lookupAres(ico, country)
      if (!data) {
        setErr(t(lang, country === 'SK' ? 'icoNotFoundSk' : 'icoNotFound'))
        return
      }
      if (data.company_name) setCompanyName(data.company_name)
      const parts = [data.street, data.zip, data.city].filter(Boolean)
      if (parts.length) setAddress(parts.join(', '))
      if (data.vat_id) setVatId(data.vat_id)
    } catch {
      setErr(t(lang, country === 'SK' ? 'icoNotFoundSk' : 'icoNotFound'))
    } finally {
      setIcoLoading(false)
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    if (!selectedRelease) {
      setErr(t(lang, 'required'))
      return
    }
    if (!invoiceCompany && !address.trim()) {
      setErr(t(lang, 'required'))
      return
    }
    if (invoiceCompany) {
      if (!country || !ico.trim() || !companyName.trim() || !address.trim()) {
        setErr(t(lang, 'required'))
        return
      }
    }
    const n = parseInt(qtyInput, 10)
    const ticketQty =
      qtyInput === '' || Number.isNaN(n) || n < 1 ? 1 : Math.min(50, n)

    setLoading(true)
    try {
      await createOrder({
        full_name: fullName,
        email,
        ticket_quantity: ticketQty,
        tito_release_id: selectedRelease.id,
        tito_release_slug: selectedRelease.slug,
        tito_release_title: selectedRelease.title,
        invoice_to_company: invoiceCompany,
        address_line: address || null,
        country_code: invoiceCompany ? country : null,
        company_registration: invoiceCompany ? ico : null,
        vat_id: vatId || null,
        company_name: invoiceCompany ? companyName : null,
      })
      setDone(true)
    } catch (ex: unknown) {
      setErr(String(ex instanceof Error ? ex.message : ex))
    } finally {
      setLoading(false)
    }
  }

  const currency = eventMeta?.currency ?? 'CZK'

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-inner">
          <p className="eyebrow">Exponential Summit</p>
          <h1>{t(lang, 'title')}</h1>
          <p className="lead">{t(lang, 'subtitle')}</p>
          <div className="lang-switch">
            <span>{t(lang, 'lang')}:</span>
            <button type="button" className={lang === 'cs' ? 'active' : ''} onClick={() => setLang('cs')}>
              Čeština
            </button>
            <button type="button" className={lang === 'en' ? 'active' : ''} onClick={() => setLang('en')}>
              English
            </button>
          </div>
        </div>
      </header>

      <main className="shell">
        {done ? (
          <div className="card success">
            <h2>{t(lang, 'success')}</h2>
            <p>{t(lang, 'successDetail')}</p>
          </div>
        ) : (
          <form className="card form" onSubmit={onSubmit}>
            {err && <div className="alert">{err}</div>}

            <label>
              {t(lang, 'fullName')}
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </label>

            <label>
              {t(lang, 'email')}
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>

            <label>
              {t(lang, 'ticket')}
              <select
                value={releaseId === '' ? '' : String(releaseId)}
                onChange={(e) => setReleaseId(e.target.value ? Number(e.target.value) : '')}
                required
              >
                <option value="">{t(lang, 'selectTicket')}</option>
                {releases.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title}
                    {r.price != null && eventMeta
                      ? ` — ${formatMoney(
                          unitPrices(r.price, eventMeta.show_prices_ex_tax).inc,
                          currency,
                        )} ${t(lang, 'priceWithVat')}`
                      : ''}
                  </option>
                ))}
              </select>
            </label>

            <label>
              {t(lang, 'quantity')}
              <input
                type="text"
                inputMode="numeric"
                autoComplete="off"
                maxLength={2}
                value={qtyInput}
                onFocus={(e) => e.currentTarget.select()}
                onChange={(e) => {
                  const v = e.target.value
                  if (v === '' || /^\d+$/.test(v)) {
                    setQtyInput(v)
                  }
                }}
                onBlur={() => {
                  const n = parseInt(qtyInput, 10)
                  if (qtyInput === '' || Number.isNaN(n) || n < 1) {
                    setQtyInput('1')
                  } else {
                    setQtyInput(String(Math.min(50, n)))
                  }
                }}
              />
            </label>

            {linePrices && (
              <div className="price-box">
                {invoiceCompany ? (
                  <>
                    <div>
                      {t(lang, 'total')} ({t(lang, 'priceWithoutVat')}):{' '}
                      <strong>{formatMoney(linePrices.totalEx, currency)}</strong>
                    </div>
                    <div>
                      {t(lang, 'total')} ({t(lang, 'priceWithVat')}):{' '}
                      <strong>{formatMoney(linePrices.totalInc, currency)}</strong>
                    </div>
                  </>
                ) : (
                  <div>
                    {t(lang, 'total')} ({t(lang, 'priceWithVat')}):{' '}
                    <strong>{formatMoney(linePrices.totalInc, currency)}</strong>
                  </div>
                )}
              </div>
            )}

            <label className="checkbox">
              <input
                type="checkbox"
                checked={invoiceCompany}
                onChange={(e) => setInvoiceCompany(e.target.checked)}
              />
              {t(lang, 'invoiceCompany')}
            </label>

            {!invoiceCompany && (
              <label>
                {t(lang, 'address')}
                <textarea value={address} onChange={(e) => setAddress(e.target.value)} rows={3} required />
              </label>
            )}

            {invoiceCompany && (
              <>
                <label>
                  {t(lang, 'country')}
                  <select value={country} onChange={(e) => setCountry(e.target.value)} required>
                    {countriesForUi.map((c) => (
                      <option key={c.code} value={c.code}>
                        {countryDisplayName(c.code, lang, c.name_en)}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="ico-row">
                  <label>
                    {t(lang, 'ico')}
                    <input value={ico} onChange={(e) => setIco(e.target.value)} />
                  </label>
                  <button type="button" className="secondary" onClick={onLookupIco} disabled={icoLoading}>
                    {icoLoading ? '…' : t(lang, country === 'SK' ? 'lookupRpo' : 'lookup')}
                  </button>
                </div>
                <label>
                  {t(lang, 'companyName')}
                  <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
                </label>
                <label>
                  {t(lang, 'vatId')}
                  <input value={vatId} onChange={(e) => setVatId(e.target.value)} />
                  {country === 'SK' && <p className="field-hint">{t(lang, 'vatIdHintSk')}</p>}
                </label>
                <label>
                  {t(lang, 'address')}
                  <textarea value={address} onChange={(e) => setAddress(e.target.value)} rows={3} required />
                </label>
              </>
            )}

            <button type="submit" className="primary" disabled={loading}>
              {loading ? '…' : t(lang, 'submit')}
            </button>
          </form>
        )}
      </main>

      <footer className="footer">
        <span>Red Button EDU · invoice.exponentialsummit.cz</span>
      </footer>
    </div>
  )
}
