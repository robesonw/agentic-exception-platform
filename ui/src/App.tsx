import { Routes, Route, useLocation, Navigate } from 'react-router-dom'
import AppLayout from './layouts/AppLayout.tsx'
import LoginPage from './routes/LoginPage.tsx'
import ExceptionsPage from './routes/ExceptionsPage.tsx'
import ExceptionDetailPage from './routes/ExceptionDetailPage.tsx'
import SupervisorPage from './routes/SupervisorPage.tsx'
import DeprecatedPage from './routes/DeprecatedPage.tsx'
import NotFoundPage from './routes/NotFoundPage.tsx'
import ProtectedRoute from './components/common/ProtectedRoute.tsx'
import OpsOverviewPage from './routes/ops/OpsOverviewPage.tsx'
import UsagePage from './routes/ops/UsagePage.tsx'
import RateLimitsPage from './routes/ops/RateLimitsPage.tsx'
import AdminLandingPage from './routes/admin/AdminLandingPage.tsx'
import ConfigChangesPage from './routes/admin/ConfigChangesPage.tsx'
import PacksPage from './routes/admin/PacksPage.tsx'
import PlaybooksPage from './routes/admin/PlaybooksPage.tsx'
import AdminToolsPage from './routes/admin/ToolsPage.tsx'
import WorkersPage from './routes/ops/WorkersPage.tsx'
import SLAPage from './routes/ops/SLAPage.tsx'
import DLQPage from './routes/ops/DLQPage.tsx'
import AlertsConfigPage from './routes/ops/AlertsConfigPage.tsx'
import AlertsHistoryPage from './routes/ops/AlertsHistoryPage.tsx'
import AuditReportsPage from './routes/ops/AuditReportsPage.tsx'

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
        
        {/* Deprecated routes - redirect to Admin equivalents */}
        <Route 
          path="/tools" 
          element={<DeprecatedPage oldPath="/tools" newPath="/admin/tools" description="Tool management has moved to the Admin section." />} 
        />
        <Route path="/tools/:id" element={<Navigate to="/admin/tools" replace />} />
        <Route 
          path="/config" 
          element={<DeprecatedPage oldPath="/config" newPath="/admin/packs" description="Configuration management has moved to the Admin section." />} 
        />
        <Route path="/config/:type/:id" element={<Navigate to="/admin/packs" replace />} />
        
        {/* Ops routes - protected by feature flag */}
        <Route
          path="/ops"
          element={
            <ProtectedRoute requireOps>
              <OpsOverviewPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/usage"
          element={
            <ProtectedRoute requireOps>
              <UsagePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/rate-limits"
          element={
            <ProtectedRoute requireOps>
              <RateLimitsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/workers"
          element={
            <ProtectedRoute requireOps>
              <WorkersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/sla"
          element={
            <ProtectedRoute requireOps>
              <SLAPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/dlq"
          element={
            <ProtectedRoute requireOps>
              <DLQPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/alerts"
          element={
            <ProtectedRoute requireOps>
              <AlertsConfigPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/alerts/history"
          element={
            <ProtectedRoute requireOps>
              <AlertsHistoryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ops/reports"
          element={
            <ProtectedRoute requireOps>
              <AuditReportsPage />
            </ProtectedRoute>
          }
        />
        
        {/* Admin routes - protected by feature flag */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute requireAdmin>
              <AdminLandingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/config-changes"
          element={
            <ProtectedRoute requireAdmin>
              <ConfigChangesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/packs"
          element={
            <ProtectedRoute requireAdmin>
              <PacksPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/playbooks"
          element={
            <ProtectedRoute requireAdmin>
              <PlaybooksPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/tools"
          element={
            <ProtectedRoute requireAdmin>
              <AdminToolsPage />
            </ProtectedRoute>
          }
        />
        
        <Route path="/" element={<ExceptionsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppLayout>
  )
}

export default App
