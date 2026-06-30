import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listOrders, type OrderAdminListItem } from './api'
import './admin.css'

function statusBadge(status: string) {
  const cls =
    status === 'error'
      ? 'badge badge-error'
      : status === 'completed'
        ? 'badge badge-ok'
        : status === 'cancelled'
          ? 'badge badge-muted'
          : status === 'paid_processing'
            ? 'badge badge-warn'
            : 'badge'
  return <span className={cls}>{status}</span>
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString('cs-CZ')
  } catch {
    return iso
  }
}

export function AdminOrdersPage() {
  const [items, setItems] = useState<OrderAdminListItem[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listOrders()
      .then((data) => {
        setItems(data.items)
        setTotal(data.total)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="admin-panel">
      <h1 className="admin-title">Objednávky</h1>
      <p className="admin-muted">Celkem: {total}</p>
      {loading && <p>Načítání…</p>}
      {error && <p className="admin-error">{error}</p>}
      {!loading && !error && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Datum</th>
                <th>Zákazník</th>
                <th>Stav</th>
                <th>Chyba</th>
                <th>Proforma</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((o) => (
                <tr key={o.public_id}>
                  <td>{formatDate(o.created_at)}</td>
                  <td>
                    <div>{o.full_name}</div>
                    <div className="admin-muted admin-small">{o.email}</div>
                  </td>
                  <td>{statusBadge(o.status)}</td>
                  <td>{o.error_label || '—'}</td>
                  <td>{o.allfred_proforma_id || '—'}</td>
                  <td>
                    <Link className="admin-link" to={`/admin/orders/${o.public_id}`}>
                      Detail
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
