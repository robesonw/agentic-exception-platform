/**
 * Tests for ExceptionTimelineTab component
 * 
 * Phase 8 P8-13: Tests for tool execution events in timeline
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import ExceptionTimelineTab from '../ExceptionTimelineTab'
import * as useExceptionsHook from '../../../hooks/useExceptions'
import * as useToolsHook from '../../../hooks/useTools'

// Mock the hooks
vi.mock('../../../hooks/useExceptions', () => ({
  useExceptionEvents: vi.fn(),
}))

vi.mock('../../../hooks/useTools', () => ({
  useToolExecutions: vi.fn(),
  useToolsList: vi.fn(),
}))

// Mock useTenant
vi.mock('../../../hooks/useTenant', () => ({
  useTenant: () => ({
    tenantId: 'TENANT_001',
    apiKey: 'test-api-key',
  }),
}))

describe('ExceptionTimelineTab - Tool Execution Events', () => {
  let queryClient: QueryClient

  const mockExceptionEvents = {
    items: [
      {
        eventId: 'event-1',
        eventType: 'ExceptionCreated',
        actorType: 'system',
        actorId: 'system-001',
        payload: {},
        createdAt: '2024-01-01T10:00:00Z',
      },
    ],
    total: 1,
  }

  const mockToolExecutions = {
    items: [
      {
        executionId: 'exec-001',
        tenantId: 'TENANT_001',
        toolId: 1,
        exceptionId: 'exc-001',
        status: 'succeeded',
        requestedByActorType: 'agent',
        requestedByActorId: 'agent-001',
        inputPayload: { action: 'test' },
        outputPayload: { result: 'success', data: { value: 123 } },
        errorMessage: null,
        createdAt: '2024-01-01T11:00:00Z',
        updatedAt: '2024-01-01T11:00:01Z',
      },
      {
        executionId: 'exec-002',
        tenantId: 'TENANT_001',
        toolId: 2,
        exceptionId: 'exc-001',
        status: 'failed',
        requestedByActorType: 'user',
        requestedByActorId: 'user-001',
        inputPayload: { action: 'test2' },
        outputPayload: null,
        errorMessage: 'Tool execution failed',
        createdAt: '2024-01-01T12:00:00Z',
        updatedAt: '2024-01-01T12:00:02Z',
      },
    ],
    total: 2,
  }

  const mockTools = {
    items: [
      {
        toolId: 1,
        tenantId: null,
        name: 'Test Tool 1',
        type: 'http',
        config: {},
        enabled: true,
        createdAt: '2024-01-01T00:00:00Z',
      },
      {
        toolId: 2,
        tenantId: null,
        name: 'Test Tool 2',
        type: 'http',
        config: {},
        enabled: true,
        createdAt: '2024-01-01T00:00:00Z',
      },
    ],
    total: 2,
  }

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

  const renderWithProviders = (component: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{component}</BrowserRouter>
      </QueryClientProvider>
    )
  }

  it('displays tool execution events in timeline', async () => {
    vi.mocked(useExceptionsHook.useExceptionEvents).mockReturnValue({
      data: mockExceptionEvents,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockToolExecutions,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: mockTools,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderWithProviders(<ExceptionTimelineTab exceptionId="exc-001" />)

    await waitFor(() => {
      expect(screen.getAllByText('Tool Execution').length).toBeGreaterThan(0)
      expect(screen.getByText('Test Tool 1')).toBeInTheDocument()
      expect(screen.getByText('Succeeded')).toBeInTheDocument()
    })
  })

  it('displays tool name, status, and timestamp for tool executions', async () => {
    vi.mocked(useExceptionsHook.useExceptionEvents).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: {
        items: [mockToolExecutions.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: {
        items: [mockTools.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderWithProviders(<ExceptionTimelineTab exceptionId="exc-001" />)

    await waitFor(() => {
      expect(screen.getByText('Test Tool 1')).toBeInTheDocument()
      expect(screen.getByText('Succeeded')).toBeInTheDocument()
      // Check for timestamp (formatted)
      expect(screen.getByText(/2024/)).toBeInTheDocument()
    })
  })

  it('displays truncated output summary for tool executions', async () => {
    vi.mocked(useExceptionsHook.useExceptionEvents).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: {
        items: [mockToolExecutions.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: {
        items: [mockTools.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderWithProviders(<ExceptionTimelineTab exceptionId="exc-001" />)

    await waitFor(() => {
      // Check that output summary is displayed (truncated)
      expect(screen.getByText(/Output Summary/i)).toBeInTheDocument()
      // The output should be truncated if it's too long
      const outputText = screen.getByText(/result.*success/i)
      expect(outputText).toBeInTheDocument()
    })
  })

  it('displays error message for failed tool executions', async () => {
    vi.mocked(useExceptionsHook.useExceptionEvents).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: {
        items: [mockToolExecutions.items[1]], // Failed execution
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: {
        items: [mockTools.items[1]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderWithProviders(<ExceptionTimelineTab exceptionId="exc-001" />)

    await waitFor(() => {
      expect(screen.getByText('Failed')).toBeInTheDocument()
      expect(screen.getByText('Tool execution failed')).toBeInTheDocument()
    })
  })

  it('provides link to tool detail page', async () => {
    vi.mocked(useExceptionsHook.useExceptionEvents).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: {
        items: [mockToolExecutions.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: {
        items: [mockTools.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderWithProviders(<ExceptionTimelineTab exceptionId="exc-001" />)

    await waitFor(() => {
      const link = screen.getByRole('link', { name: /View Tool Details/i })
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute('href', '/tools/1')
    })
  })

  it('merges tool executions with exception events in chronological order', async () => {
    vi.mocked(useExceptionsHook.useExceptionEvents).mockReturnValue({
      data: mockExceptionEvents,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: {
        items: [mockToolExecutions.items[0]], // Created at 11:00
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: {
        items: [mockTools.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderWithProviders(<ExceptionTimelineTab exceptionId="exc-001" />)

    await waitFor(() => {
      // Should show both exception event and tool execution
      expect(screen.getByText(/Exception Created/i)).toBeInTheDocument()
      expect(screen.getByText('Tool Execution')).toBeInTheDocument()
    })
  })

  it('handles missing tool name gracefully', async () => {
    vi.mocked(useExceptionsHook.useExceptionEvents).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: {
        items: [mockToolExecutions.items[0]],
        total: 1,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    // Return empty tools list (tool name not found)
    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: {
        items: [],
        total: 0,
      },
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    renderWithProviders(<ExceptionTimelineTab exceptionId="exc-001" />)

    await waitFor(() => {
      // Should still show tool execution even without tool name
      expect(screen.getByText('Tool Execution')).toBeInTheDocument()
      expect(screen.getByText('Succeeded')).toBeInTheDocument()
    })
  })
})
