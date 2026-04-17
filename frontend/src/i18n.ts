import type { Country } from './api'

export type Lang = 'cs' | 'en'

/** ISO 3166-1 alpha-2 → localized country name (Česko, Slovakia, …) */
export function countryDisplayName(code: string, lang: Lang, fallback: string): string {
  try {
    const locale = lang === 'cs' ? 'cs-CZ' : 'en-GB'
    const dn = new Intl.DisplayNames([locale], { type: 'region' })
    return dn.of(code) ?? fallback
  } catch {
    return fallback
  }
}

/** CZ a SK první, zbytek abecedně podle lokalizovaného názvu */
export function orderCountriesForDisplay(countries: Country[], lang: Lang): Country[] {
  const priority: string[] = ['CZ', 'SK']
  const locale = lang === 'cs' ? 'cs-CZ' : 'en-GB'
  const collatorLocale = lang === 'cs' ? 'cs' : 'en'
  const dn = new Intl.DisplayNames([locale], { type: 'region' })
  const label = (c: Country) => dn.of(c.code) ?? c.name_en

  const head = priority
    .map((code) => countries.find((c) => c.code === code))
    .filter((c): c is Country => c != null)

  const rest = countries.filter((c) => !priority.includes(c.code))
  rest.sort((a, b) => label(a).localeCompare(label(b), collatorLocale))

  return [...head, ...rest]
}

const STRINGS: Record<Lang, Record<string, string>> = {
  cs: {
    title: 'Objednávka vstupenek',
    subtitle: 'Exponential Summit 2026 — fakturace přes Red Button EDU',
    fullName: 'Jméno a příjmení',
    email: 'E-mail',
    ticket: 'Typ vstupenky',
    quantity: 'Počet',
    invoiceCompany: 'Faktura na firmu',
    address: 'Fakturační adresa',
    addressStreet: 'Ulice a číslo popisné',
    addressCity: 'Město',
    addressZip: 'PSČ',
    country: 'Stát',
    ico: 'IČO',
    companyName: 'Název firmy',
    vatId: 'DIČ',
    lookup: 'Načíst z ARES',
    lookupRpo: 'Načíst z RPO',
    submit: 'Odeslat objednávku',
    lang: 'Jazyk',
    priceWithVat: 's DPH',
    priceWithoutVat: 'bez DPH',
    total: 'Celkem',
    selectTicket: 'Vyberte vstupenku',
    error: 'Chyba',
    successMessage:
      'Děkujeme za váš zájem o Exponential Summit - objednávku jsme přijali a v e-mailu na vás už čeká zálohová faktura.\nPo zaplacení Vám odešleme voucher na registraci vstupenek.\n\nA těším se v říjnu 🙂\n\nTým Red Button EDU',
    icoNotFound: 'Subjekt s tímto IČO nebyl nalezen.',
    icoNotFoundSk: 'Subjekt s tímto IČO nebyl nalezen v registru RPO (ŠÚ SR).',
    lookupTimeout:
      'Načtení údajů vypršelo — zkuste to znovu za chvíli nebo vyplňte údaje ručně.',
    required: 'Vyplňte povinná pole.',
  },
  en: {
    title: 'Ticket order',
    subtitle: 'Exponential Summit 2026 — invoicing via Red Button EDU',
    fullName: 'Full name',
    email: 'E-mail',
    ticket: 'Ticket type',
    quantity: 'Quantity',
    invoiceCompany: 'Invoice to company',
    address: 'Billing address',
    addressStreet: 'Street and number',
    addressCity: 'City',
    addressZip: 'Postal code',
    country: 'Country',
    ico: 'Company ID',
    companyName: 'Company name',
    vatId: 'VAT ID',
    lookup: 'Load from ARES',
    lookupRpo: 'Load from RPO',
    submit: 'Submit order',
    lang: 'Language',
    priceWithVat: 'incl. VAT',
    priceWithoutVat: 'excl. VAT',
    total: 'Total',
    selectTicket: 'Select ticket',
    error: 'Error',
    successMessage:
      'Thank you for your interest in Exponential Summit — we have received your order, and the proforma invoice is already waiting for you in your inbox.\nOnce you pay, we will send you a voucher to register your ticket.\n\nI look forward to seeing you in October 🙂\n\nTeam Red Button EDU',
    icoNotFound: 'No company found for this registration number.',
    icoNotFoundSk: 'No company found in the Slovak RPO register (ŠÚ SR) for this ID.',
    lookupTimeout:
      'Loading company details timed out — try again shortly or enter the details manually.',
    required: 'Please fill in required fields.',
  },
}

export function detectLang(): Lang {
  const nav = typeof navigator !== 'undefined' ? navigator.language : 'en'
  if (nav.toLowerCase().startsWith('cs')) return 'cs'
  if (nav.toLowerCase().startsWith('en')) return 'en'
  return 'en'
}

/**
 * Jazyk z URL: nejdřív `?lang=cs` / `?lang=en`, jinak první segment cesty `/cs/…` nebo `/en/…`.
 */
export function langFromUrl(): Lang | null {
  if (typeof window === 'undefined') return null
  try {
    const u = new URL(window.location.href)
    const q = u.searchParams.get('lang')?.trim().toLowerCase()
    if (q === 'cs' || q === 'en') return q

    const first = u.pathname.split('/').filter(Boolean)[0]?.toLowerCase()
    if (first === 'cs' || first === 'en') return first as Lang
    return null
  } catch {
    return null
  }
}

/** Pořadí: URL → prohlížeč */
export function initialLang(): Lang {
  return langFromUrl() ?? detectLang()
}

/**
 * Zapíše jazyk do adresy (replaceState): u cesty jen `/cs` nebo `/en` mění segment,
 * jinak nastaví / doplní `?lang=`.
 */
export function applyLangToBrowserUrl(lang: Lang): void {
  if (typeof window === 'undefined') return
  const u = new URL(window.location.href)
  const segments = u.pathname.split('/').filter(Boolean)
  const onlyLangPath = segments.length === 1 && (segments[0] === 'cs' || segments[0] === 'en')

  if (onlyLangPath) {
    u.pathname = `/${lang}/`
    u.searchParams.delete('lang')
  } else {
    u.searchParams.set('lang', lang)
  }
  const qs = u.searchParams.toString()
  history.replaceState(null, '', `${u.pathname}${qs ? `?${qs}` : ''}${u.hash}`)
}

export function t(lang: Lang, key: keyof typeof STRINGS.cs): string {
  return STRINGS[lang][key] ?? key
}
