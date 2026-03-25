export type Lang = 'cs' | 'en'

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
