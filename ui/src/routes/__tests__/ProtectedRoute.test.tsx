/**
 * Tests for ProtectedRoute component
 * 
 * P11-1: Tests for route protection and feature flag gating
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ProtectedRoute from '../../components/common/ProtectedRoute'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import * as featureFlags from '../../utils/featureFlags'

// Mock feature flags
vi.mock('../../utils/featureFlags', () => ({
  isOpsEnabled: vi.fn(),
  isAdminEnabled: vi.fn(),
}))

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const renderRoute = (requireOps = false, requireAdmin = false) => {
    return render(
      <BrowserRouter>
        <Routes>
          <Route
            path="/test"
            element={
              <ProtectedRoute requireOps={requireOps} requireAdmin={requireAdmin}>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    )
  }

  it('renders children when no requirements', () => {
    renderRoute(false, false)
    expect(screen.getByText('Protected Content')).toBeDefined()
  })

  it('shows NotAuthorizedPage when Ops required but not enabled', () => {
    vi.mocked(featureFlags.isOpsEnabled).mockReturnValue(false)
    renderRoute(true, false)
    expect(screen.getByText(/Not Authorized/i)).toBeDefined()
    expect(screen.queryByText('Protected Content')).toBeNull()
  })

  it('renders children when Ops required and enabled', () => {
    vi.mocked(featureFlags.isOpsEnabled).mockReturnValue(true)
    renderRoute(true, false)
    expect(screen.getByText('Protected Content')).toBeDefined()
  })

  it('shows NotAuthorizedPage when Admin required but not enabled', () => {
    vi.mocked(featureFlags.isAdminEnabled).mockReturnValue(false)
    renderRoute(false, true)
    expect(screen.getByText(/Not Authorized/i)).toBeDefined()
    expect(screen.queryByText('Protected Content')).toBeNull()
  })

  it('renders children when Admin required and enabled', () => {
    vi.mocked(featureFlags.isAdminEnabled).mockReturnValue(true)
    renderRoute(false, true)
    expect(screen.getByText('Protected Content')).toBeDefined()
  })

  it('shows NotAuthorizedPage when both required but only Ops enabled', () => {
    vi.mocked(featureFlags.isOpsEnabled).mockReturnValue(true)
    vi.mocked(featureFlags.isAdminEnabled).mockReturnValue(false)
    renderRoute(true, true)
    expect(screen.getByText(/Not Authorized/i)).toBeDefined()
  })
})

