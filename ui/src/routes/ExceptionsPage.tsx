import { useState, useEffect, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Box, Button, Alert } from '@mui/material'
import PageHeader from '../components/common/PageHeader.tsx'
import FilterBar, { type ExceptionFilters } from '../components/common/FilterBar.tsx'
import DataTable, { type DataTableColumn } from '../components/common/DataTable.tsx'
import { SeverityChip, StatusChip } from '../components/common'
import { useExceptionsList } from '../hooks/useExceptions.ts'
import { useTenant } from '../hooks/useTenant.tsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'
import { formatDateTime } from '../utils/dateFormat.ts'
import type { ExceptionSummary } from '../types'


export default function ExceptionsPage() {
  useDocumentTitle('Exceptions')
  const { tenantId, apiKey } = useTenant()
  const [searchParams, setSearchParams] = useSearchParams()

  // Initialize state from URL query params
  const [filters, setFilters] = useState<ExceptionFilters>(() => {
    return {
      severity: searchParams.get('severity') || undefined,
      status: searchParams.get('status') || undefined,
      dateFrom: searchParams.get('dateFrom') || undefined,
      dateTo: searchParams.get('dateTo') || undefined,
      sourceSystem: searchParams.get('sourceSystem') || undefined,
    }
  })

  const [page, setPage] = useState(() => {
    const pageParam = searchParams.get('page')
    return pageParam ? parseInt(pageParam, 10) - 1 : 0 // Convert 1-based to 0-based
  })

  const [pageSize, setPageSize] = useState(() => {
    const pageSizeParam = searchParams.get('pageSize')
    return pageSizeParam ? parseInt(pageSizeParam, 10) : 50
  })

  const [sortField, setSortField] = useState<string | undefined>(() => {
    return searchParams.get('sortField') || undefined
  })

  const [sortDirection, setSortDirection] = useState<'asc' | 'desc' | undefined>(() => {
    const dir = searchParams.get('sortDirection')
    return dir === 'asc' || dir === 'desc' ? dir : undefined
  })

  // Sync filters, pagination, and sorting to URL query params
  useEffect(() => {
    const params = new URLSearchParams()

    // Add filters
    if (filters.severity) params.set('severity', filters.severity)
    if (filters.status) params.set('status', filters.status)
    if (filters.dateFrom) params.set('dateFrom', filters.dateFrom)
    if (filters.dateTo) params.set('dateTo', filters.dateTo)
    if (filters.sourceSystem) params.set('sourceSystem', filters.sourceSystem)

    // Add pagination (convert 0-based to 1-based for URL)
    if (page > 0) params.set('page', String(page + 1))
    if (pageSize !== 50) params.set('pageSize', String(pageSize))

    // Add sorting
    if (sortField) params.set('sortField', sortField)
    if (sortDirection) params.set('sortDirection', sortDirection)

    setSearchParams(params, { replace: true })
  }, [filters, page, pageSize, sortField, sortDirection, setSearchParams])

  // Prepare API params
  const apiParams = useMemo(() => {
    const params: {
      page?: number
      page_size?: number
      severity?: string
      status?: string
      from_ts?: string
      to_ts?: string
      sourceSystem?: string
    } = {
      page: page + 1, // Convert 0-based to 1-based for API
      page_size: pageSize,
    }

    if (filters.severity) params.severity = filters.severity
    if (filters.status) params.status = filters.status
    if (filters.dateFrom) {
      // Convert date to ISO timestamp
      const date = new Date(filters.dateFrom)
      params.from_ts = date.toISOString()
    }
    if (filters.dateTo) {
      // Convert date to ISO timestamp (end of day)
      const date = new Date(filters.dateTo)
      date.setHours(23, 59, 59, 999)
      params.to_ts = date.toISOString()
    }
    if (filters.sourceSystem) params.sourceSystem = filters.sourceSystem

    return params
  }, [filters, page, pageSize])

  // Show message if API key is missing (but tenant is set)
  if (!apiKey && tenantId) {
    return (
      <Box>
        <PageHeader title="Exceptions" subtitle="Monitor and investigate exceptions for the current tenant" />
        <Alert severity="warning" sx={{ mt: 3 }}>
          API key is required to access exceptions. Please go to <Link to="/login">Login</Link> to set your API key.
        </Alert>
      </Box>
    )
  }

  // Fetch exceptions
  const { data, isLoading, isError, error } = useExceptionsList(apiParams)

  // Use the data and loading state
  const exceptions = data?.items || []
  const totalCount = data?.total || 0

  // Handle filter change
  const handleFilterChange = (newFilters: ExceptionFilters) => {
    setFilters(newFilters)
    setPage(0) // Reset to first page when filters change
  }

  // Handle pagination
  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(0) // Reset to first page when page size changes
  }

  // Handle sorting
  const handleSortChange = (field: string, direction: 'asc' | 'desc') => {
    setSortField(field)
    setSortDirection(direction)
  }

  // Handle "New Exception" button click
  const handleNewException = () => {
    // Placeholder: Show alert or navigate to ingestion UI
    alert('Exception ingestion UI coming in a later phase. For now, use the backend API to ingest exceptions.')
  }

  // Handle clear filters
  const handleClearFilters = () => {
    setFilters({})
    setPage(0)
    // Clear URL params
    const params = new URLSearchParams()
    params.set('page', '1')
    params.set('pageSize', String(pageSize))
    setSearchParams(params)
  }

  // Check if any filters are active
  const hasActiveFilters = Boolean(
    filters.severity || filters.status || filters.dateFrom || filters.dateTo || filters.sourceSystem
  )

  // Define table columns
  const columns: DataTableColumn<ExceptionSummary>[] = useMemo(
    () => [
      {
        id: 'exception_id',
        label: 'Exception ID',
        minWidth: 150,
        accessor: (row) => (
          <Link
            to={`/exceptions/${row.exception_id}`}
            style={{ textDecoration: 'none', color: 'inherit' }}
          >
            <Box
              component="span"
              sx={{
                color: 'primary.main',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              {row.exception_id}
            </Box>
          </Link>
        ),
      },
      {
        id: 'severity',
        label: 'Severity',
        minWidth: 120,
        accessor: (row) => <SeverityChip severity={row.severity} size="small" />,
      },
      {
        id: 'resolution_status',
        label: 'Status',
        minWidth: 130,
        accessor: (row) => <StatusChip status={row.resolution_status} size="small" />,
      },
      {
        id: 'exception_type',
        label: 'Exception Type',
        minWidth: 180,
        accessor: (row) => row.exception_type || '—',
      },
      {
        id: 'source_system',
        label: 'Source System',
        minWidth: 150,
        accessor: (row) => row.source_system || '—',
      },
      {
        id: 'timestamp',
        label: 'Timestamp',
        minWidth: 180,
        accessor: (row) => formatDateTime(row.timestamp),
      },
    ],
    []
  )

  return (
    <Box>
      <PageHeader
        title="Exceptions"
        subtitle="Monitor and investigate exceptions for the current tenant"
        actions={
          <Button variant="contained" onClick={handleNewException}>
            New Exception
          </Button>
        }
      />

      {/* Filter Bar */}
      <FilterBar value={filters} onChange={handleFilterChange} />

      {/* Error State */}
      {isError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          Failed to load exceptions: {error?.message || 'Unknown error'}
        </Alert>
      )}

      {/* Data Table */}
      {tenantId ? (
        <DataTable
          columns={columns}
          rows={exceptions}
          loading={isLoading}
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={handlePageChange}
          onPageSizeChange={handlePageSizeChange}
          sortField={sortField}
          sortDirection={sortDirection}
          onSortChange={handleSortChange}
          emptyTitle="No exceptions found"
          emptyMessage={
            hasActiveFilters
              ? 'Try clearing filters or expanding your date range to see more results.'
              : 'No exceptions have been recorded yet for this tenant.'
          }
          emptyAction={
            hasActiveFilters ? (
              <Button variant="outlined" size="small" onClick={handleClearFilters}>
                Clear filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Alert severity="info" sx={{ mt: 3 }}>
          Please select a tenant to view exceptions.
        </Alert>
      )}
    </Box>
  )
}
