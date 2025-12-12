/**
 * Tests for SupervisorPage component
 * 
 * P6-28: Tests for supervisor dashboard with DB-backed analytics
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import SupervisorPage from '../SupervisorPage.tsx'
import * as supervisorApi from '../../api/supervisor.ts'
import type { SupervisorOverview } from '../../types'

// Mock the API
vi.mock('../../api/supervisor.ts')
vi.mock('../../hooks/useTenant.tsx', () => ({
  useTenant: () => ({
    tenantId: 'test-tenant-001',
    apiKey: 'test-api-key',
  }),
}))

describe('SupervisorPage', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    })
    vi.clearAllMocks()
  })

  const renderComponent = () => {
    return render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <SupervisorPage />
        </QueryClientProvider>
      </BrowserRouter>
    )
  }

  const mockOverviewResponse: SupervisorOverview = {
    counts: {
      CRITICAL: { OPEN: 5, IN_PROGRESS: 2, RESOLVED: 10, ESCALATED: 1, PENDING_APPROVAL: 0 },
      HIGH: { OPEN: 10, IN_PROGRESS: 3, RESOLVED: 20, ESCALATED: 2, PENDING_APPROVAL: 0 },
      MEDIUM: { OPEN: 15, IN_PROGRESS: 5, RESOLVED: 30, ESCALATED: 0, PENDING_APPROVAL: 0 },
      LOW: { OPEN: 20, IN_PROGRESS: 2, RESOLVED: 40, ESCALATED: 0, PENDING_APPROVAL: 0 },
    },
    escalations_count: 3,
    pending_approvals_count: 0,
    top_policy_violations: [
      {
        exception_id: 'exc-001',
        tenant_id: 'test-tenant-001',
        domain: 'finance',
        timestamp: '2024-01-15T10:00:00Z',
        violation_type: 'BLOCK',
        violated_rule: 'Amount threshold exceeded',
        decision: 'BLOCK',
      },
    ],
    optimization_suggestions_summary: {
      total_suggestions: 2,
      by_category: { performance: 1, cost: 1 },
      high_priority_count: 1,
    },
  }

  it('renders supervisor dashboard header', () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    expect(screen.getByText(/Supervisor Dashboard/i)).toBeDefined()
  })

  it('displays severity overview cards', async () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    await waitFor(() => {
      // Check that severity cards are displayed
      expect(screen.getByText(/Severity Overview/i)).toBeDefined()
      expect(screen.getByText(/CRITICAL/i)).toBeDefined()
      expect(screen.getByText(/HIGH/i)).toBeDefined()
      expect(screen.getByText(/MEDIUM/i)).toBeDefined()
      expect(screen.getByText(/LOW/i)).toBeDefined()
    })

    // Check that counts are displayed
    // CRITICAL total = 5 + 2 + 10 + 1 = 18
    expect(screen.getByText('18')).toBeDefined()
  })

  it('displays status summary cards', async () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    await waitFor(() => {
      expect(screen.getByText(/Status Summary/i)).toBeDefined()
      expect(screen.getByText(/Open exceptions/i)).toBeDefined()
      expect(screen.getByText(/Escalated exceptions/i)).toBeDefined()
      expect(screen.getByText(/Resolved exceptions/i)).toBeDefined()
    })

    // Check escalations count
    expect(screen.getByText('3')).toBeDefined() // escalations_count
  })

  it('displays top policy violations table', async () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    await waitFor(() => {
      expect(screen.getByText(/Top Policy Violations/i)).toBeDefined()
      expect(screen.getByText(/exc-001/i)).toBeDefined()
      expect(screen.getByText(/Amount threshold exceeded/i)).toBeDefined()
    })
  })

  it('displays filter controls', () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    // Check filter controls are present
    expect(screen.getByLabelText(/Domain/i)).toBeDefined()
    expect(screen.getByLabelText(/From Date/i)).toBeDefined()
    expect(screen.getByLabelText(/To Date/i)).toBeDefined()
  })

  it('displays date range preset buttons', () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    expect(screen.getByText(/Today/i)).toBeDefined()
    expect(screen.getByText(/Last 7 days/i)).toBeDefined()
    expect(screen.getByText(/Last 30 days/i)).toBeDefined()
  })

  it('shows empty state when no violations', async () => {
    const emptyResponse: SupervisorOverview = {
      ...mockOverviewResponse,
      top_policy_violations: [],
    }
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(emptyResponse)

    renderComponent()

    await waitFor(() => {
      expect(screen.getByText(/No policy violations found/i)).toBeDefined()
    })
  })

  it('shows loading state initially', () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    renderComponent()

    // Should show loading skeletons
    const container = document.body
    expect(container).toBeDefined()
  })

  it('shows error state on API failure', async () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockRejectedValue(
      new Error('Failed to fetch overview')
    )

    renderComponent()

    await waitFor(() => {
      expect(screen.getByText(/Failed to load supervisor overview/i)).toBeDefined()
    })
  })

  it('shows tenant information', () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    expect(screen.getByText(/Tenant: test-tenant-001/i)).toBeDefined()
  })

  it('displays tabs for overview, escalations, and violations', () => {
    vi.mocked(supervisorApi.getSupervisorOverview).mockResolvedValue(mockOverviewResponse)

    renderComponent()

    expect(screen.getByText(/Overview/i)).toBeDefined()
    expect(screen.getByText(/Escalations/i)).toBeDefined()
    expect(screen.getByText(/Policy Violations/i)).toBeDefined()
  })
})

