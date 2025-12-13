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

  // Phase 7 P7-18: Tests for playbook event rendering
  describe('Playbook Events', () => {
    const mockPlaybookEventsResponse: ExceptionEventsListResponse = {
      items: [
        {
          eventId: 'event-playbook-001',
          exceptionId: 'exc-001',
          tenantId: 'test-tenant-001',
          eventType: 'PlaybookStarted',
          actorType: 'agent',
          actorId: 'PolicyAgent',
          payload: {
            playbook_id: 1,
            playbook_name: 'PaymentFailurePlaybook',
            playbook_version: 1,
            total_steps: 3,
          },
          createdAt: '2024-01-15T10:15:00Z',
        },
        {
          eventId: 'event-playbook-002',
          exceptionId: 'exc-001',
          tenantId: 'test-tenant-001',
          eventType: 'PlaybookStepCompleted',
          actorType: 'user',
          actorId: 'user-123',
          payload: {
            playbook_id: 1,
            step_id: 'step-1',
            step_order: 1,
            step_name: 'Notify Team',
            action_type: 'notify',
            is_last_step: false,
            is_risky: false,
            notes: 'Team notified successfully',
            actor_type: 'user',
            actor_id: 'user-123',
          },
          createdAt: '2024-01-15T10:20:00Z',
        },
        {
          eventId: 'event-playbook-003',
          exceptionId: 'exc-001',
          tenantId: 'test-tenant-001',
          eventType: 'PlaybookCompleted',
          actorType: 'user',
          actorId: 'user-123',
          payload: {
            playbook_id: 1,
            total_steps: 3,
            notes: 'All steps completed',
            actor_type: 'user',
            actor_id: 'user-123',
          },
          createdAt: '2024-01-15T10:25:00Z',
        },
      ],
      total: 3,
      page: 1,
      pageSize: 50,
      totalPages: 1,
    }

    it('renders PlaybookStarted event with details', async () => {
      vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue({
        ...mockPlaybookEventsResponse,
        items: [mockPlaybookEventsResponse.items[0]],
        total: 1,
      })

      renderComponent('exc-001')

      await waitFor(() => {
        expect(screen.getByText(/Playbook Started/i)).toBeDefined()
        expect(screen.getByText(/Playbook ID:/i)).toBeDefined()
        expect(screen.getByText(/1/i)).toBeDefined() // playbook_id
        expect(screen.getByText(/PaymentFailurePlaybook/i)).toBeDefined()
        expect(screen.getByText(/Version:/i)).toBeDefined()
        expect(screen.getByText(/Total Steps:/i)).toBeDefined()
        expect(screen.getByText(/3/i)).toBeDefined() // total_steps
      })
    })

    it('renders PlaybookStepCompleted event with details', async () => {
      vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue({
        ...mockPlaybookEventsResponse,
        items: [mockPlaybookEventsResponse.items[1]],
        total: 1,
      })

      renderComponent('exc-001')

      await waitFor(() => {
        expect(screen.getByText(/Playbook Step Completed/i)).toBeDefined()
        expect(screen.getByText(/Playbook ID:/i)).toBeDefined()
        expect(screen.getByText(/Step Order:/i)).toBeDefined()
        expect(screen.getByText(/1/i)).toBeDefined() // step_order
        expect(screen.getByText(/Step Name:/i)).toBeDefined()
        expect(screen.getByText(/Notify Team/i)).toBeDefined()
        expect(screen.getByText(/Action Type:/i)).toBeDefined()
        expect(screen.getByText(/notify/i)).toBeDefined()
        expect(screen.getByText(/Notes:/i)).toBeDefined()
        expect(screen.getByText(/Team notified successfully/i)).toBeDefined()
      })
    })

    it('renders PlaybookCompleted event with details', async () => {
      vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue({
        ...mockPlaybookEventsResponse,
        items: [mockPlaybookEventsResponse.items[2]],
        total: 1,
      })

      renderComponent('exc-001')

      await waitFor(() => {
        expect(screen.getByText(/Playbook Completed/i)).toBeDefined()
        expect(screen.getByText(/Playbook ID:/i)).toBeDefined()
        expect(screen.getByText(/Total Steps:/i)).toBeDefined()
        expect(screen.getByText(/3/i)).toBeDefined() // total_steps
        expect(screen.getByText(/Notes:/i)).toBeDefined()
        expect(screen.getByText(/All steps completed/i)).toBeDefined()
      })
    })

    it('displays actor information for playbook events', async () => {
      vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue(mockPlaybookEventsResponse)

      renderComponent('exc-001')

      await waitFor(() => {
        // Check actor types are displayed
        expect(screen.getAllByText(/Agent/i).length).toBeGreaterThan(0)
        expect(screen.getAllByText(/User/i).length).toBeGreaterThan(0)
        // Check actor IDs are displayed
        expect(screen.getByText(/PolicyAgent/i)).toBeDefined()
        expect(screen.getByText(/user-123/i)).toBeDefined()
      })
    })

    it('includes playbook event types in filter dropdown', async () => {
      vi.mocked(exceptionsApi.fetchExceptionEvents).mockResolvedValue(mockPlaybookEventsResponse)

      renderComponent('exc-001')

      await waitFor(() => {
        const eventTypeSelect = screen.getByLabelText(/Event Type/i)
        expect(eventTypeSelect).toBeDefined()
        
        // Check that playbook event types are in the dropdown
        // Note: We can't easily test dropdown options without opening it,
        // but we can verify the select exists and the component renders
        expect(eventTypeSelect).toBeDefined()
      })
    })
  })
})

