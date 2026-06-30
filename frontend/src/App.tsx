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
  summitHomeUrl,
  t,
  tf,
  type Lang,
} from './i18n'

const FORM_QTY_HARD_MAX = 50

function releaseQtyBounds(release: Release | null): { min: number; max: number } {
  let min = 1
  let max = FORM_QTY_HARD_MAX
  if (!release) return { min, max }
  if (release.min_per_order != null) min = Math.max(1, release.min_per_order)
  if (release.max_per_order != null) max = Math.min(max, release.max_per_order)
  if (release.quantity_remaining != null) max = Math.min(max, release.quantity_remaining)
  if (min > max) min = max
  return { min, max }
}

function formatReleaseRemaining(release: Release, lang: Lang): string {
  if (release.quantity_remaining == null) return ''
  return ` — ${tf(lang, 'ticketsRemaining', { n: release.quantity_remaining })}`
}

function formatOrderQtyHint(release: Release | null, lang: Lang): string | null {
  if (!release) return null
  const { min_per_order: min, max_per_order: max } = release
  if (min != null && max != null) return tf(lang, 'orderQtyHintRange', { min, max })
  if (min != null) return tf(lang, 'orderQtyHintMin', { n: min })
  if (max != null) return tf(lang, 'orderQtyHintMax', { n: max })
  return null
}

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
  const [bootLoading, setBootLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
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
        if (!cancelled) setBootLoading(false)
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

  const qtyBounds = useMemo(() => releaseQtyBounds(selectedRelease), [selectedRelease])

  useEffect(() => {
    if (!selectedRelease) return
    const { min, max } = releaseQtyBounds(selectedRelease)
    setQtyInput((prev) => {
      const n = parseInt(prev, 10)
      const current = prev === '' || Number.isNaN(n) ? min : n
      const clamped = Math.min(max, Math.max(min, current))
      return String(clamped)
    })
  }, [releaseId, selectedRelease])

  const quantityForTotals = useMemo(() => {
    const n = parseInt(qtyInput, 10)
    if (qtyInput === '' || Number.isNaN(n)) return 0
    return Math.min(qtyBounds.max, Math.max(qtyBounds.min, n))
  }, [qtyInput, qtyBounds])

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

  const orderQtyHint = useMemo(
    () => formatOrderQtyHint(selectedRelease, lang),
    [selectedRelease, lang],
  )

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
    const { min, max } = releaseQtyBounds(selectedRelease)
    const ticketQty =
      qtyInput === '' || Number.isNaN(n) ? min : Math.min(max, Math.max(min, n))

    setSubmitting(true)
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
      setSubmitting(false)
    }
  }

  const currency = eventMeta?.currency ?? 'CZK'

  function switchLang(next: Lang) {
    setLang(next)
    applyLangToBrowserUrl(next)
  }

  const otherLang: Lang = lang === 'cs' ? 'en' : 'cs'

  return (
    <div className="page">
      <header className="site-header">
        <a className="logo" href={summitHomeUrl(lang)} aria-label="Exponential Summit">
          <img src="/assets/exponential-summit-logo.svg" alt="Exponential Summit by Red Button" />
        </a>
        <div className="header-right">
          <button
            type="button"
            className="lang-switch"
            onClick={() => switchLang(otherLang)}
            aria-label={otherLang === 'en' ? 'English' : 'Čeština'}
          >
            <span className="lang-flag">{lang === 'cs' ? '🇨🇿' : '🇬🇧'}</span>
            <span className="lang-arrow">▼</span>
          </button>
        </div>
      </header>

      <main className="order-main">
        <div className="page-intro">
          <p className="page-eyebrow">Exponential Summit</p>
          <h1 className="page-title">{t(lang, 'title')}</h1>
          <p className="page-lead">{t(lang, 'subtitle')}</p>
        </div>

        {bootLoading ? (
          <div className="page-loading" aria-live="polite">
            …
          </div>
        ) : done ? (
          <div className="card success">
            <div className="success-message">{t(lang, 'successMessage')}</div>
          </div>
        ) : (
          <form className="card form" onSubmit={onSubmit} aria-busy={submitting}>
            {err && <div className="alert">{err}</div>}

            <fieldset className="form-fieldset" disabled={submitting}>
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
                    {formatReleaseRemaining(r, lang)}
                  </option>
                ))}
              </select>
              {selectedRelease?.quantity_remaining != null && (
                <p className="field-hint">
                  {tf(lang, 'ticketsRemaining', { n: selectedRelease.quantity_remaining })}
                </p>
              )}
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
                  const { min, max } = releaseQtyBounds(selectedRelease)
                  const n = parseInt(qtyInput, 10)
                  if (qtyInput === '' || Number.isNaN(n) || n < min) {
                    setQtyInput(String(min))
                  } else {
                    setQtyInput(String(Math.min(max, n)))
                  }
                }}
              />
              {orderQtyHint && <p className="field-hint">{orderQtyHint}</p>}
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
                    <button
                      type="button"
                      className="btn-pill btn-pill--secondary"
                      onClick={onLookupIco}
                      disabled={icoLoading}
                    >
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
            </fieldset>

            {submitting && (
              <p id="order-submit-status" className="submit-status" role="status" aria-live="polite">
                {t(lang, 'submitProcessingHint')}
              </p>
            )}

            <button
              type="submit"
              className="hero-btn hero-btn--primary hero-btn--block"
              disabled={submitting}
              aria-describedby={submitting ? 'order-submit-status' : undefined}
            >
              <span className={`hero-btn-label${submitting ? ' hero-btn-label--loading' : ''}`}>
                {submitting && <span className="hero-btn-spinner" aria-hidden="true" />}
                {submitting ? t(lang, 'submitProcessing') : t(lang, 'submit')}
              </span>
            </button>
          </form>
        )}
      </main>

      <footer className="site-footer">
        <a href={summitHomeUrl(lang)}>exponentialsummit.cz</a>
        {' · '}
        <span>Red Button EDU</span>
      </footer>
    </div>
  )
}
