import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ClientDetailPage from './pages/ClientDetailPage'
import ClientsPage from './pages/ClientsPage'
import SystemPage from './pages/SystemPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/clients" replace />} />
          <Route path="/clients" element={<ClientsPage />} />
          <Route path="/clients/:id" element={<ClientDetailPage />} />
          <Route path="/system" element={<SystemPage />} />
          <Route path="*" element={<Navigate to="/clients" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
