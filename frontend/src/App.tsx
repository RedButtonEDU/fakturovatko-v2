import { useEffect, useMemo, useState } from 'react'
import './App.css'
import {
  createOrder,
  getCountries,
  getEventMeta,
  getReleases,
  isAresLookupTimeout,
  lookupAres,
  type Country,
  type Release,
} from './api'
import {
  applyLangToBrowserUrl,
  countryDisplayName,
  initialLang,
  orderCountriesForDisplay,
  t,
  type Lang,
} from './i18n'

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
  const [lang, setLang] = useState<Lang>(() => initialLang())

  useEffect(() => {
    document.documentElement.lang = lang === 'cs' ? 'cs' : 'en'
  }, [lang])
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
  const [addressStreet, setAddressStreet] = useState('')
  const [addressCity, setAddressCity] = useState('')
  const [addressZip, setAddressZip] = useState('')
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
      if (data.street) setAddressStreet(data.street)
      if (data.zip) setAddressZip(data.zip)
      if (data.city) setAddressCity(data.city)
      if (data.vat_id) setVatId(data.vat_id)
    } catch (e) {
      if (isAresLookupTimeout(e)) {
        setErr(t(lang, 'lookupTimeout'))
      } else {
        setErr(t(lang, country === 'SK' ? 'icoNotFoundSk' : 'icoNotFound'))
      }
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
    const addrOk =
      addressStreet.trim() !== '' && addressCity.trim() !== '' && addressZip.trim() !== ''
    if (!country) {
      setErr(t(lang, 'required'))
      return
    }
    if (!invoiceCompany && !addrOk) {
      setErr(t(lang, 'required'))
      return
    }
    if (invoiceCompany) {
      if (!ico.trim() || !companyName.trim() || !addrOk) {
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
        ticket_unit_price_czk:
          selectedRelease.price != null && !Number.isNaN(selectedRelease.price)
            ? selectedRelease.price
            : null,
        invoice_to_company: invoiceCompany,
        address_street: addressStreet || null,
        address_city: addressCity || null,
        address_zip: addressZip || null,
        country_code: country,
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
            <button
              type="button"
              className={lang === 'cs' ? 'active' : ''}
              onClick={() => {
                setLang('cs')
                applyLangToBrowserUrl('cs')
              }}
            >
              Čeština
            </button>
            <button
              type="button"
              className={lang === 'en' ? 'active' : ''}
              onClick={() => {
                setLang('en')
                applyLangToBrowserUrl('en')
              }}
            >
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

            {!invoiceCompany && (
              <fieldset className="address-block">
                <legend>{t(lang, 'address')}</legend>
                <label>
                  {t(lang, 'addressStreet')}
                  <input
                    value={addressStreet}
                    onChange={(e) => setAddressStreet(e.target.value)}
                    autoComplete="street-address"
                    required
                  />
                </label>
                <div className="address-zip-city">
                  <label>
                    {t(lang, 'addressZip')}
                    <input
                      value={addressZip}
                      onChange={(e) => setAddressZip(e.target.value)}
                      inputMode="text"
                      autoComplete="postal-code"
                      required
                    />
                  </label>
                  <label>
                    {t(lang, 'addressCity')}
                    <input
                      value={addressCity}
                      onChange={(e) => setAddressCity(e.target.value)}
                      autoComplete="address-level2"
                      required
                    />
                  </label>
                </div>
              </fieldset>
            )}

            {invoiceCompany && (
              <>
                <div className="ico-row">
                  <label className="ico-row-label" htmlFor="order-ico">
                    {t(lang, 'ico')}
                  </label>
                  <div className="ico-row-inner">
                    <input
                      id="order-ico"
                      value={ico}
                      onChange={(e) => setIco(e.target.value)}
                      inputMode="numeric"
                      autoComplete="off"
                    />
                    <button type="button" className="secondary" onClick={onLookupIco} disabled={icoLoading}>
                      {icoLoading ? '…' : t(lang, country === 'SK' ? 'lookupRpo' : 'lookup')}
                    </button>
                  </div>
                </div>
                <label>
                  {t(lang, 'companyName')}
                  <input value={companyName} onChange={(e) => setCompanyName(e.target.value)} required />
                </label>
                <label>
                  {t(lang, 'vatId')}
                  <input value={vatId} onChange={(e) => setVatId(e.target.value)} />
                </label>
                <fieldset className="address-block">
                  <legend>{t(lang, 'address')}</legend>
                  <label>
                    {t(lang, 'addressStreet')}
                    <input
                      value={addressStreet}
                      onChange={(e) => setAddressStreet(e.target.value)}
                      autoComplete="street-address"
                      required
                    />
                  </label>
                  <div className="address-zip-city">
                    <label>
                      {t(lang, 'addressZip')}
                      <input
                        value={addressZip}
                        onChange={(e) => setAddressZip(e.target.value)}
                        inputMode="text"
                        autoComplete="postal-code"
                        required
                      />
                    </label>
                    <label>
                      {t(lang, 'addressCity')}
                      <input
                        value={addressCity}
                        onChange={(e) => setAddressCity(e.target.value)}
                        autoComplete="address-level2"
                        required
                      />
                    </label>
                  </div>
                </fieldset>
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
