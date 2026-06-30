import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { getAuthMe, logout } from './api'
import '../App.css'
import './admin.css'

export function AdminGuard() {
  const [email, setEmail] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const location = useLocation()

  useEffect(() => {
    let cancelled = false
    getAuthMe()
      .then((me) => {
        if (!cancelled) setEmail(me.email)
      })
      .catch(() => {
        if (!cancelled) setEmail(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [location.pathname])

  useEffect(() => {
    if (!loading && !email) {
      const next = encodeURIComponent(location.pathname + location.search)
      window.location.href = `/auth/login?next=${next}`
    }
  }, [loading, email, location.pathname, location.search])

  if (loading || !email) {
    return (
      <div className="admin-page page">
        <p className="admin-muted" style={{ padding: '2rem' }}>
          Načítání…
        </p>
      </div>
    )
  }

  return <AdminLayout email={email} />
}

function AdminLayout({ email }: { email: string }) {
  async function onLogout() {
    await logout()
    window.location.href = '/auth/login?next=/admin'
  }

  return (
    <div className="admin-page page">
      <header className="site-header admin-header">
        <a href="/" className="logo">
          <img src="/assets/exponential-summit-logo.svg" alt="Exponential Summit by Red Button" />
        </a>
        <div className="header-right">
          <span className="admin-user">{email}</span>
          <button type="button" className="btn btn-secondary admin-logout" onClick={onLogout}>
            Odhlásit
          </button>
        </div>
      </header>
      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  )
}

export function AdminIndexRedirect() {
  return <Navigate to="/admin/orders" replace />
}
