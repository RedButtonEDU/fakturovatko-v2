import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { AdminGuard, AdminIndexRedirect } from './admin/AdminLayout.tsx'
import { AdminOrdersPage } from './admin/AdminOrdersPage.tsx'
import { AdminOrderDetailPage } from './admin/AdminOrderDetailPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/admin" element={<AdminGuard />}>
          <Route index element={<AdminIndexRedirect />} />
          <Route path="orders" element={<AdminOrdersPage />} />
          <Route path="orders/:publicId" element={<AdminOrderDetailPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
