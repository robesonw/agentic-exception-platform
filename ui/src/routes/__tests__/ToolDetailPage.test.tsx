/**
 * Tests for ToolDetailPage component
 * 
 * Phase 8 P8-11: Basic component tests for tool detail page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import ToolDetailPage from '../ToolDetailPage'
import * as useToolsHook from '../../hooks/useTools'

// Mock the useTools hooks
vi.mock('../../hooks/useTools', () => ({
  useTool: vi.fn(),
  useToolExecutions: vi.fn(),
  useExecuteTool: vi.fn(),
}))

// Mock useTenant hook
vi.mock('../../hooks/useTenant', () => ({
  useTenant: () => ({
    tenantId: 'TENANT_001',
    apiKey: 'test-api-key',
  }),
}))

// Mock useDocumentTitle
vi.mock('../../hooks/useDocumentTitle', () => ({
  useDocumentTitle: vi.fn(),
}))

// Mock useSnackbar
vi.mock('../../components/common/SnackbarProvider', () => ({
  useSnackbar: () => ({
    showSuccess: vi.fn(),
    showError: vi.fn(),
  }),
}))

// Mock react-syntax-highlighter
vi.mock('react-syntax-highlighter', () => ({
  Prism: ({ children }: { children: string }) => <pre>{children}</pre>,
}))

vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  vscDarkPlus: {},
}))

describe('ToolDetailPage', () => {
  let queryClient: QueryClient

  const mockTool = {
    toolId: 1,
    tenantId: 'TENANT_001',
    name: 'Test Tool',
    type: 'http',
    config: {
      description: 'Test tool description',
      inputSchema: { type: 'object', properties: { name: { type: 'string' } } },
      outputSchema: { type: 'object', properties: { result: { type: 'string' } } },
      authType: 'api_key',
      endpointConfig: { url: 'https://api.example.com', method: 'POST' },
    },
    enabled: true,
    createdAt: '2024-01-01T00:00:00Z',
  }

  const mockExecutions = {
    items: [
      {
        executionId: 'exec-001',
        tenantId: 'TENANT_001',
        toolId: 1,
        exceptionId: null,
        status: 'succeeded',
        requestedByActorType: 'user',
        requestedByActorId: 'user-001',
        inputPayload: { name: 'test' },
        outputPayload: { result: 'success' },
        errorMessage: null,
        createdAt: '2024-01-02T00:00:00Z',
        updatedAt: '2024-01-02T00:00:01Z',
      },
    ],
    total: 1,
    page: 1,
    pageSize: 10,
    totalPages: 1,
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

  it('renders loading state', () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: undefined,
      isLoading: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    expect(screen.getByText('Tool Detail')).toBeInTheDocument()
    expect(screen.getByText(/Loading tool information/)).toBeInTheDocument()
  })

  it('renders error state when tool not found', () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error('Tool not found'),
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: undefined,
      isLoading: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    expect(screen.getByText('Tool Not Found')).toBeInTheDocument()
    expect(screen.getByText('Tool not found')).toBeInTheDocument()
  })

  it('renders tool detail with metadata', async () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: mockTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockExecutions,
      isLoading: false,
    } as any)

    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      expect(screen.getAllByText('Test Tool').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Test tool description').length).toBeGreaterThan(0)
      expect(screen.getByText('Tool Metadata')).toBeInTheDocument()
      expect(screen.getByText('1')).toBeInTheDocument() // Tool ID
    })
  })

  it('renders input and output schemas', async () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: mockTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockExecutions,
      isLoading: false,
    } as any)

    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('Input Schema')).toBeInTheDocument()
      expect(screen.getByText('Output Schema')).toBeInTheDocument()
    })
  })

  it('renders auth and endpoint config', async () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: mockTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockExecutions,
      isLoading: false,
    } as any)

    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('Authentication & Endpoint')).toBeInTheDocument()
      expect(screen.getByText('api_key')).toBeInTheDocument()
    })
  })

  it('renders enabled status chip', async () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: mockTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockExecutions,
      isLoading: false,
    } as any)

    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('Enabled')).toBeInTheDocument()
    })
  })

  it('renders recent executions list', async () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: mockTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockExecutions,
      isLoading: false,
    } as any)

    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('Recent Executions')).toBeInTheDocument()
      expect(screen.getByText('Succeeded')).toBeInTheDocument()
      expect(screen.getByText('user/user-001')).toBeInTheDocument()
    })
  })

  it('opens execute dialog when Execute Tool button is clicked', async () => {
    const user = userEvent.setup()

    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: mockTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockExecutions,
      isLoading: false,
    } as any)

    const mockExecute = vi.fn().mockResolvedValue({})
    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: mockExecute,
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('Execute Tool')).toBeInTheDocument()
    })

    const executeButton = screen.getByText('Execute Tool')
    await user.click(executeButton)

    await waitFor(() => {
      expect(screen.getByText(/Execute Tool: Test Tool/)).toBeInTheDocument()
    })
  })

  it('disables Execute Tool button when tool is disabled', async () => {
    const disabledTool = { ...mockTool, enabled: false }

    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: disabledTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: mockExecutions,
      isLoading: false,
    } as any)

    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      const executeButton = screen.getByText('Execute Tool')
      expect(executeButton).toBeDisabled()
    })
  })

  it('shows empty state when no executions', async () => {
    vi.mocked(useToolsHook.useTool).mockReturnValue({
      data: mockTool,
      isLoading: false,
      isError: false,
      error: null,
    } as any)

    vi.mocked(useToolsHook.useToolExecutions).mockReturnValue({
      data: { items: [], total: 0, page: 1, pageSize: 10, totalPages: 0 },
      isLoading: false,
    } as any)

    vi.mocked(useToolsHook.useExecuteTool).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as any)

    renderWithProviders(<ToolDetailPage />)

    await waitFor(() => {
      expect(screen.getByText('No executions found')).toBeInTheDocument()
    })
  })
})

