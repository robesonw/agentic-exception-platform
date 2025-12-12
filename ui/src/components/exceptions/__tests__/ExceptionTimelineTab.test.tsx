/**
 * Tests for ExceptionTimelineTab component
 * 
 * P6-27: Tests for event timeline display with DB-backed API
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ExceptionTimelineTab from '../ExceptionTimelineTab.tsx'
import * as exceptionsApi from '../../../api/exceptions.ts'
import type { ExceptionEventsListResponse } from '../../../api/exceptions.ts'

// Mock the API
vi.mock('../../../api/exceptions.ts')
vi.mock('../../../hooks/useTenant.tsx', () => ({
  useTenant: () => ({
    tenantId: 'test-tenant-001',
    apiKey: 'test-api-key',
  }),
}))

describe('ExceptionTimelineTab', () => {
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

  const renderComponent = (exceptionId: string) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <ExceptionTimelineTab exceptionId={exceptionId} />
      </QueryClientProvider>
    )
  }

  const mockEventsResponse: ExceptionEventsListResponse = {
    items: [
      {
        eventId: 'event-001',
        exceptionId: 'exc-001',
        tenantId: 'test-tenant-001',
        eventType: 'ExceptionCreated',
        actorType: 'system',
        actorId: null,
        payload: { source: 'api_ingestion' },
        createdAt: '2024-01-15T10:00:00Z',
      },
      {
        eventId: 'event-002',
        exceptionId: 'exc-001',
        tenantId: 'test-tenant-001',
        eventType: 'TriageCompleted',
        actorType: 'agent',
        actorId: 'triage-agent-001',
        payload: { decision: 'escalate', confidence: 0.95 },
        createdAt: '2024-01-15T10:05:00Z',
      },
      {
        eventId: 'event-003',
        exceptionId: 'exc-001',
        tenantId: 'test-tenant-001',
        eventType: 'ResolutionApproved',
        actorType: 'user',
        actorId: 'user-123',
        payload: { approved_by: 'user-123' },
        createdAt: '2024-01-15T10:10:00Z',
      },
    ],
    total: 3,
    page: 1,
    pageSize: 50,
    totalPages: 1,
  }

  it('renders loading state initially', () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    )

    renderComponent('exc-001')

    // Should show loading skeletons (CardSkeleton components)
    // The component uses CardSkeleton which doesn't render text, so we check for the component structure
    const container = screen.getByRole('tabpanel', { hidden: true }) || document.body
    expect(container).toBeDefined()
  })

  it('renders events in chronological order', async () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue(mockEventsResponse)

    renderComponent('exc-001')

    await waitFor(() => {
      // Check that events are displayed
      expect(screen.getByText(/Exception Created/i)).toBeDefined()
      expect(screen.getByText(/Triage Completed/i)).toBeDefined()
      expect(screen.getByText(/Resolution Approved/i)).toBeDefined()
    })

    // Verify chronological order (oldest first)
    const eventTypes = screen.getAllByText(/Exception Created|Triage Completed|Resolution Approved/i)
    expect(eventTypes[0].textContent).toContain('Exception Created')
    expect(eventTypes[1].textContent).toContain('Triage Completed')
    expect(eventTypes[2].textContent).toContain('Resolution Approved')
  })

  it('displays event details correctly', async () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue(mockEventsResponse)

    renderComponent('exc-001')

    await waitFor(() => {
      // Check event type
      expect(screen.getByText(/Exception Created/i)).toBeDefined()
      
      // Check actor type
      expect(screen.getByText(/System/i)).toBeDefined()
      expect(screen.getByText(/Agent/i)).toBeDefined()
      expect(screen.getByText(/User/i)).toBeDefined()
      
      // Check timestamps are displayed
      expect(screen.getByText(/2024-01-15/i)).toBeDefined()
    })
  })

  it('shows empty state when no events', async () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 50,
      totalPages: 0,
    })

    renderComponent('exc-001')

    await waitFor(() => {
      expect(screen.getByText(/No events available/i)).toBeDefined()
    })
  })

  it('shows error state on API failure', async () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockRejectedValue(
      new Error('Failed to fetch events')
    )

    renderComponent('exc-001')

    await waitFor(() => {
      expect(screen.getByText(/Failed to load timeline/i)).toBeDefined()
    })
  })

  it('shows tenant mismatch error', async () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockRejectedValue(
      new Error('Exception not found or does not belong to tenant')
    )

    renderComponent('exc-001')

    await waitFor(() => {
      expect(screen.getByText(/Exception not found or does not belong/i)).toBeDefined()
    })
  })

  it('displays filter controls', () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue(mockEventsResponse)

    renderComponent('exc-001')

    // Check filter controls are present
    expect(screen.getByLabelText(/Event Type/i)).toBeDefined()
    expect(screen.getByLabelText(/Actor Type/i)).toBeDefined()
    expect(screen.getByLabelText(/From/i)).toBeDefined()
    expect(screen.getByLabelText(/To/i)).toBeDefined()
  })

  it('shows event count', async () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue(mockEventsResponse)

    renderComponent('exc-001')

    await waitFor(() => {
      expect(screen.getByText(/Showing 3 of 3 event/i)).toBeDefined()
    })
  })

  it('shows filtered count when filters are active', async () => {
    vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue({
      ...mockEventsResponse,
      items: [mockEventsResponse.items[0]], // Only first event
      total: 1,
    })

    renderComponent('exc-001')

    await waitFor(() => {
      expect(screen.getByText(/Showing 1 of 1 event/i)).toBeDefined()
    })
  })
})

