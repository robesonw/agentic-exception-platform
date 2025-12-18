import { Routes, Route, useLocation } from 'react-router-dom'
import AppLayout from './layouts/AppLayout.tsx'
import LoginPage from './routes/LoginPage.tsx'
import ExceptionsPage from './routes/ExceptionsPage.tsx'
import ExceptionDetailPage from './routes/ExceptionDetailPage.tsx'
import SupervisorPage from './routes/SupervisorPage.tsx'
import ToolsPage from './routes/ToolsPage.tsx'
import ToolDetailPage from './routes/ToolDetailPage.tsx'
import ConfigPage from './routes/ConfigPage.tsx'
import ConfigDetailPage from './routes/ConfigDetailPage.tsx'
import OpsPage from './routes/OpsPage.tsx'
import NotFoundPage from './routes/NotFoundPage.tsx'

function App() {
  const location = useLocation()
  const isLoginPage = location.pathname === '/login'

  // Render login page without AppLayout
  if (isLoginPage) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    )
  }

  // Render other pages with AppLayout
  return (
    <AppLayout>
      <Routes>
        <Route path="/exceptions" element={<ExceptionsPage />} />
        <Route path="/exceptions/:id" element={<ExceptionDetailPage />} />
        <Route path="/supervisor" element={<SupervisorPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/tools/:id" element={<ToolDetailPage />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/config/:type/:id" element={<ConfigDetailPage />} />
        {import.meta.env.VITE_ENABLE_OPS_PAGE === 'true' && (
          <Route path="/ops" element={<OpsPage />} />
        )}
        <Route path="/" element={<ExceptionsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppLayout>
  )
}

export default App
