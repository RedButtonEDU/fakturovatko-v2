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
    success: 'Objednávka odeslána',
    successDetail: 'Zkontrolujte e-mail s proforma fakturou.',
    icoNotFound: 'Subjekt s tímto IČO nebyl nalezen.',
    icoNotFoundSk: 'Subjekt s tímto IČO nebyl nalezen v registru RPO (ŠÚ SR).',
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
    success: 'Order submitted',
    successDetail: 'Check your e-mail for the proforma invoice.',
    icoNotFound: 'No company found for this registration number.',
    icoNotFoundSk: 'No company found in the Slovak RPO register (ŠÚ SR) for this ID.',
    required: 'Please fill in required fields.',
  },
}

export function detectLang(): Lang {
  const nav = typeof navigator !== 'undefined' ? navigator.language : 'en'
  if (nav.toLowerCase().startsWith('cs')) return 'cs'
  if (nav.toLowerCase().startsWith('en')) return 'en'
  return 'en'
}

export function t(lang: Lang, key: keyof typeof STRINGS.cs): string {
  return STRINGS[lang][key] ?? key
}
