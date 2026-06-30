import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listOrders,
  type OrderAdminListItem,
  type OrderAdminListSortDir,
  type OrderAdminListSortKey,
} from './api'
import './admin.css'

const SORT_COLUMNS: { key: OrderAdminListSortKey; label: string; defaultDir: OrderAdminListSortDir }[] = [
  { key: 'created_at', label: 'Datum', defaultDir: 'desc' },
  { key: 'full_name', label: 'Zákazník', defaultDir: 'asc' },
  { key: 'status', label: 'Stav', defaultDir: 'asc' },
  { key: 'error_code', label: 'Chyba', defaultDir: 'asc' },
  { key: 'allfred_proforma_id', label: 'Proforma', defaultDir: 'asc' },
]

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
  const [sortBy, setSortBy] = useState<OrderAdminListSortKey>('created_at')
  const [sortDir, setSortDir] = useState<OrderAdminListSortDir>('desc')

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    listOrders(0, 50, sortBy, sortDir)
      .then((data) => {
        setItems(data.items)
        setTotal(data.total)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [sortBy, sortDir])

  useEffect(() => {
    load()
  }, [load])

  function onSort(key: OrderAdminListSortKey) {
    const col = SORT_COLUMNS.find((c) => c.key === key)
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(key)
      setSortDir(col?.defaultDir ?? 'asc')
    }
  }

  function sortIndicator(key: OrderAdminListSortKey) {
    if (sortBy !== key) return '↕'
    return sortDir === 'asc' ? '↑' : '↓'
  }

  return (
    <div className="admin-panel">
      <h1 className="admin-title">Objednávky</h1>
      <p className="admin-muted">Celkem: {total}</p>
      {loading && <p>Načítání…</p>}
      {error && <p className="admin-error">{error}</p>}
      {!error && (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                {SORT_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className={
                      sortBy === col.key ? 'admin-sortable admin-sortable--active' : 'admin-sortable'
                    }
                  >
                    <button
                      type="button"
                      className="admin-sort-button"
                      onClick={() => onSort(col.key)}
                      aria-sort={
                        sortBy === col.key
                          ? sortDir === 'asc'
                            ? 'ascending'
                            : 'descending'
                          : 'none'
                      }
                    >
                      {col.label}
                      <span className="admin-sort-indicator">{sortIndicator(col.key)}</span>
                    </button>
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {!loading &&
                items.map((o) => (
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
