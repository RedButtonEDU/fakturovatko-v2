import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getOrder, patchOrder, retryWorkflow, type OrderAdminOut } from './api'
import './admin.css'

type FormState = {
  full_name: string
  email: string
  invoice_to_company: boolean
  company_name: string
  company_registration: string
  vat_id: string
  address_street: string
  address_city: string
  address_zip: string
  country_code: string
}

function orderToForm(o: OrderAdminOut): FormState {
  return {
    full_name: o.full_name,
    email: o.email,
    invoice_to_company: o.invoice_to_company,
    company_name: o.company_name || '',
    company_registration: o.company_registration || '',
    vat_id: o.vat_id || '',
    address_street: o.address_street || '',
    address_city: o.address_city || '',
    address_zip: o.address_zip || '',
    country_code: o.country_code || '',
  }
}

function statusBadge(status: string) {
  const cls =
    status === 'error'
      ? 'badge badge-error'
      : status === 'completed'
        ? 'badge badge-ok'
        : status === 'cancelled'
          ? 'badge badge-muted'
          : 'badge'
  return <span className={cls}>{status}</span>
}

export function AdminOrderDetailPage() {
  const { publicId } = useParams<{ publicId: string }>()
  const [order, setOrder] = useState<OrderAdminOut | null>(null)
  const [form, setForm] = useState<FormState | null>(null)
  const [savedForm, setSavedForm] = useState<FormState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [retrying, setRetrying] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const isDirty = useMemo(() => {
    if (!form || !savedForm) return false
    return JSON.stringify(form) !== JSON.stringify(savedForm)
  }, [form, savedForm])

  function load() {
    if (!publicId) return
    setLoading(true)
    setError(null)
    getOrder(publicId)
      .then((o) => {
        setOrder(o)
        const f = orderToForm(o)
        setForm(f)
        setSavedForm(f)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [publicId])

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault()
    if (!publicId || !form || !order?.can_edit) return
    setSaving(true)
    setMessage(null)
    setError(null)
    try {
      const updated = await patchOrder(publicId, {
        full_name: form.full_name,
        email: form.email,
        invoice_to_company: form.invoice_to_company,
        company_name: form.company_name || null,
        company_registration: form.company_registration || null,
        vat_id: form.vat_id || null,
        address_street: form.address_street || null,
        address_city: form.address_city || null,
        address_zip: form.address_zip || null,
        country_code: form.country_code || null,
      })
      setOrder(updated)
      const f = orderToForm(updated)
      setForm(f)
      setSavedForm(f)
      setMessage('Údaje uloženy.')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  async function onRetry() {
    if (!publicId || !order?.can_retry_workflow) return
    setRetrying(true)
    setMessage(null)
    setError(null)
    setShowConfirm(false)
    try {
      const repair = order.needs_legacy_hold_repair
      const result = await retryWorkflow(publicId, repair)
      setMessage(`Workflow: ${result.message} (stav: ${result.status})`)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      load()
    } finally {
      setRetrying(false)
    }
  }

  const canRetryNow = order?.can_retry_workflow && !isDirty

  if (loading) {
    return (
      <div className="admin-panel">
        <p>Načítání…</p>
      </div>
    )
  }

  if (error && !order) {
    return (
      <div className="admin-panel">
        <p className="admin-error">{error}</p>
        <Link to="/admin" className="admin-link">
          ← Seznam objednávek
        </Link>
      </div>
    )
  }

  if (!order || !form) return null

  const retrySteps = [
    order.needs_legacy_hold_repair ? 'Ti.to hold (retroaktivní snížení public qty)' : null,
    'Ti.to credit invoice pool',
    'Ti.to voucher',
    'Allfred finální faktura',
    'E-mail zákazníkovi',
  ].filter(Boolean)

  return (
    <div className="admin-panel">
      <p>
        <Link to="/admin" className="admin-link">
          ← Seznam objednávek
        </Link>
      </p>
      <h1 className="admin-title">Objednávka {order.public_id.slice(0, 8)}…</h1>
      <div className="admin-detail-grid">
        <div>
          <p>
            Stav: {statusBadge(order.status)} · {order.ticket_quantity}× {order.tito_release_title}
          </p>
          {order.error_label && (
            <p className="admin-error-label">
              {order.error_label}
              {order.error_code ? ` [${order.error_code}]` : ''}
            </p>
          )}
          {order.last_error && <pre className="admin-pre">{order.last_error}</pre>}
        </div>
        <div className="admin-links">
          {order.allfred_proforma_url && (
            <a href={order.allfred_proforma_url} target="_blank" rel="noreferrer">
              Allfred proforma
            </a>
          )}
          {order.allfred_final_invoice_url && (
            <a href={order.allfred_final_invoice_url} target="_blank" rel="noreferrer">
              Allfred faktura
            </a>
          )}
          {order.tito_release_url && (
            <a href={order.tito_release_url} target="_blank" rel="noreferrer">
              Ti.to release
            </a>
          )}
          {order.tito_invoice_release_url && (
            <a href={order.tito_invoice_release_url} target="_blank" rel="noreferrer">
              Ti.to invoice klon
            </a>
          )}
        </div>
      </div>

      {order.partial_failure_hint === 'voucher_without_email' && (
        <div className="admin-banner admin-banner-warn">
          <strong>Voucher existuje, e-mail neodešel.</strong> Kód pro ruční odeslání:{' '}
          <code>{order.tito_discount_code}</code>
          <br />
          {order.retry_blocked_reason}
        </div>
      )}

      {order.retry_blocked_reason && !order.can_retry_workflow && !order.partial_failure_hint && (
        <div className="admin-banner admin-banner-muted">{order.retry_blocked_reason}</div>
      )}

      {order.can_edit && (
        <>
          <p className="admin-hint">
            Nejdřív zkontrolujte a uložte údaje, pak spusťte workflow.
          </p>
          <form className="admin-form" onSubmit={onSave}>
            <label>
              Jméno
              <input
                value={form.full_name}
                onChange={(e) => updateField('full_name', e.target.value)}
                required
              />
            </label>
            <label>
              E-mail
              <input
                type="email"
                value={form.email}
                onChange={(e) => updateField('email', e.target.value)}
                required
              />
            </label>
            <label className="admin-checkbox">
              <input
                type="checkbox"
                checked={form.invoice_to_company}
                onChange={(e) => updateField('invoice_to_company', e.target.checked)}
              />
              Faktura na firmu
            </label>
            {form.invoice_to_company && (
              <>
                <label>
                  Název firmy
                  <input
                    value={form.company_name}
                    onChange={(e) => updateField('company_name', e.target.value)}
                  />
                </label>
                <label>
                  IČO
                  <input
                    value={form.company_registration}
                    onChange={(e) => updateField('company_registration', e.target.value)}
                  />
                </label>
                <label>
                  DIČ
                  <input value={form.vat_id} onChange={(e) => updateField('vat_id', e.target.value)} />
                </label>
              </>
            )}
            <label>
              Ulice
              <input
                value={form.address_street}
                onChange={(e) => updateField('address_street', e.target.value)}
              />
            </label>
            <label>
              Město
              <input
                value={form.address_city}
                onChange={(e) => updateField('address_city', e.target.value)}
              />
            </label>
            <label>
              PSČ
              <input
                value={form.address_zip}
                onChange={(e) => updateField('address_zip', e.target.value)}
              />
            </label>
            <label>
              Země (ISO)
              <input
                value={form.country_code}
                onChange={(e) => updateField('country_code', e.target.value.toUpperCase())}
                maxLength={2}
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={saving || !isDirty}>
              {saving ? 'Ukládám…' : 'Uložit'}
            </button>
          </form>
        </>
      )}

      {order.can_retry_workflow && (
        <div className="admin-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canRetryNow || retrying}
            onClick={() => setShowConfirm(true)}
          >
            {retrying ? 'Spouštím…' : 'Znovu spustit workflow'}
          </button>
          {isDirty && (
            <p className="admin-hint admin-error">Nejdřív uložte změny před spuštěním workflow.</p>
          )}
        </div>
      )}

      {message && <p className="admin-ok">{message}</p>}
      {error && <p className="admin-error">{error}</p>}

      {order.audit_log.length > 0 && (
        <section className="admin-audit">
          <h2>Audit log</h2>
          <ul>
            {order.audit_log.map((a) => (
              <li key={a.id}>
                {a.created_at} — {a.admin_email} — {a.action} — {a.result}
              </li>
            ))}
          </ul>
        </section>
      )}

      {showConfirm && (
        <div className="admin-modal-backdrop" role="presentation" onClick={() => setShowConfirm(false)}>
          <div
            className="admin-modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Potvrdit spuštění workflow</h2>
            <p>Provedou se tyto kroky (již dokončené se přeskočí):</p>
            <ul>
              {retrySteps.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            {order.needs_legacy_hold_repair && (
              <p className="admin-banner admin-banner-warn">
                Retroaktivní Ti.to hold sníží public qty — ověřte, že inventura v Ti.to odpovídá
                realitě prodeje.
              </p>
            )}
            <div className="admin-modal-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setShowConfirm(false)}>
                Zrušit
              </button>
              <button type="button" className="btn btn-primary" onClick={onRetry}>
                Spustit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
