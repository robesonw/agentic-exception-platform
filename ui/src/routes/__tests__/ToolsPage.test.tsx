/**
 * Tests for ToolsPage component
 * 
 * Phase 8 P8-10: Basic component tests for tools list page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import ToolsPage from '../ToolsPage'
import * as useToolsHook from '../../hooks/useTools'

// Mock the useTools hook
vi.mock('../../hooks/useTools', () => ({
  useToolsList: vi.fn(),
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

describe('ToolsPage', () => {
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

  const renderWithProviders = (component: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{component}</BrowserRouter>
      </QueryClientProvider>
    )
  }

  it('renders page title and description', () => {
    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<ToolsPage />)

    expect(screen.getByText('Tools')).toBeInTheDocument()
    expect(screen.getByText(/Manage and view tool definitions/)).toBeInTheDocument()
  })

  it('renders filter controls', () => {
    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<ToolsPage />)

    // Check for label text (MUI Select renders label multiple times - label and legend)
    expect(screen.getAllByText('Scope').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Status').length).toBeGreaterThan(0)
    expect(screen.getByPlaceholderText('Filter by name')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Filter by type')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any)

    renderWithProviders(<ToolsPage />)

    // TableSkeleton should be rendered (we can check for table structure)
    expect(screen.getByText('Tools')).toBeInTheDocument()
  })

  it('shows empty state when no tools', () => {
    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<ToolsPage />)

    expect(screen.getByText('No tools found')).toBeInTheDocument()
  })

  it('renders tools table with data', async () => {
    const mockTools = [
      {
        toolId: 1,
        tenantId: null,
        name: 'Global HTTP Tool',
        type: 'http',
        config: {},
        enabled: true,
        createdAt: '2024-01-01T00:00:00Z',
      },
      {
        toolId: 2,
        tenantId: 'TENANT_001',
        name: 'Tenant Tool',
        type: 'webhook',
        config: {},
        enabled: false,
        createdAt: '2024-01-02T00:00:00Z',
      },
    ]

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: { items: mockTools, total: 2 },
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<ToolsPage />)

    await waitFor(() => {
      expect(screen.getByText('Global HTTP Tool')).toBeInTheDocument()
      expect(screen.getByText('Tenant Tool')).toBeInTheDocument()
      expect(screen.getByText('http')).toBeInTheDocument()
      expect(screen.getByText('webhook')).toBeInTheDocument()
    })
  })

  it('shows error message on error', () => {
    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to load tools'),
    } as any)

    renderWithProviders(<ToolsPage />)

    expect(screen.getByText(/Error loading tools/)).toBeInTheDocument()
  })

  it('renders scope and status chips correctly', async () => {
    const mockTools = [
      {
        toolId: 1,
        tenantId: null,
        name: 'Global Tool',
        type: 'http',
        config: {},
        enabled: true,
        createdAt: '2024-01-01T00:00:00Z',
      },
      {
        toolId: 2,
        tenantId: 'TENANT_001',
        name: 'Tenant Tool',
        type: 'webhook',
        config: {},
        enabled: false,
        createdAt: '2024-01-02T00:00:00Z',
      },
    ]

    vi.mocked(useToolsHook.useToolsList).mockReturnValue({
      data: { items: mockTools, total: 2 },
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<ToolsPage />)

    await waitFor(() => {
      expect(screen.getByText('Global')).toBeInTheDocument()
      expect(screen.getByText('Tenant')).toBeInTheDocument()
      expect(screen.getByText('Enabled')).toBeInTheDocument()
      expect(screen.getByText('Disabled')).toBeInTheDocument()
    })
  })
})

