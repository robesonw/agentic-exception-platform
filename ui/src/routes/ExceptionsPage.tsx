import { useState, useEffect, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Box, Button, Alert, Grid, Paper, Typography } from '@mui/material'
import FilterBar, { type ExceptionFilters } from '../components/common/FilterBar.tsx'
import DataTable, { type DataTableColumn } from '../components/common/DataTable.tsx'
import { SeverityChip, StatusChip } from '../components/common'
import { useExceptionsList } from '../hooks/useExceptions.ts'
import { useTenant } from '../hooks/useTenant.tsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'
import { formatDateTime } from '../utils/dateFormat.ts'
import type { ExceptionSummary } from '../types'
import { themeColors } from '../theme/theme.ts'


export default function ExceptionsPage() {
  useDocumentTitle('Exceptions')
  const { tenantId, apiKey } = useTenant()
  const [searchParams, setSearchParams] = useSearchParams()

  // Initialize state from URL query params
  const [filters, setFilters] = useState<ExceptionFilters>(() => {
    return {
      domain: searchParams.get('domain') || undefined,
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
    if (filters.domain) params.set('domain', filters.domain)
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
  // P6-26: Updated to use DB-backed /exceptions/{tenant_id} endpoint
  const apiParams = useMemo(() => {
    const params: {
      page?: number
      page_size?: number
      domain?: string
      severity?: string
      status?: string
      created_from?: string
      created_to?: string
    } = {
      page: page + 1, // Convert 0-based to 1-based for API
      page_size: pageSize,
    }

    if (filters.domain) params.domain = filters.domain
    // Backend expects lowercase severity values
    if (filters.severity) params.severity = filters.severity.toLowerCase()
    // Backend expects lowercase status values (open, analyzing, resolved, escalated)
    if (filters.status) {
      const statusMap: Record<string, string> = {
        'OPEN': 'open',
        'IN_PROGRESS': 'analyzing',
        'RESOLVED': 'resolved',
        'ESCALATED': 'escalated',
      }
      params.status = statusMap[filters.status] || filters.status.toLowerCase()
    }
    if (filters.dateFrom) {
      // Convert date to ISO datetime
      const date = new Date(filters.dateFrom)
      params.created_from = date.toISOString()
    }
    if (filters.dateTo) {
      // Convert date to ISO datetime (end of day)
      const date = new Date(filters.dateTo)
      date.setHours(23, 59, 59, 999)
      params.created_to = date.toISOString()
    }

    return params
  }, [filters, page, pageSize])

  // Fetch exceptions
  const { data, isLoading, isError, error } = useExceptionsList(apiParams)

  // Show message if API key is missing (but tenant is set)
  if (!apiKey && tenantId) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
            Operations Center
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor and triage exceptions across all tenants and domains.
          </Typography>
        </Box>
        <Alert severity="warning">
          API key is required to access exceptions. Please go to <Link to="/login">Login</Link> to set your API key.
        </Alert>
      </Box>
    )
  }

  // Check if exceptions are stuck (all in OPEN status with no events)
  const hasUnprocessedExceptions = useMemo(() => {
    if (!data?.items) return false
    // Check if most exceptions are in OPEN status (might indicate workers not running)
    const openCount = data.items.filter(e => e.resolution_status === 'OPEN').length
    return openCount > 0 && data.items.length > 0
  }, [data])

  // Use the data and loading state
  const exceptions = data?.items || []
  const totalCount = data?.total || 0

  // Compute quick stats from current page data
  // Note: These are approximate for open/critical since we only have current page
  const openCount = exceptions.filter((e) => e.resolution_status !== 'RESOLVED').length
  const criticalCount = exceptions.filter((e) => e.severity === 'CRITICAL').length

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
    filters.domain || filters.severity || filters.status || filters.dateFrom || filters.dateTo || filters.sourceSystem
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
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Header Section */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary', mb: 0.5 }}>
            Operations Center
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor and triage exceptions across all tenants and domains.
          </Typography>
        </Box>
        <Button variant="contained" onClick={handleNewException}>
          New Exception
        </Button>
      </Box>

      {/* Workers Warning Banner */}
      {hasUnprocessedExceptions && (
        <Alert severity="warning">
          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
            Workers May Not Be Running
          </Typography>
          <Typography variant="body2">
            Some exceptions appear to be unprocessed. Workers must be running to process exceptions through the pipeline.
            See <strong>docs/WORKERS_QUICK_START.md</strong> for instructions on starting workers.
          </Typography>
        </Alert>
      )}

      {/* Quick Stats / KPI Cards */}
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: themeColors.borderPrimary,
              bgcolor: themeColors.bgSecondary,
              background: `linear-gradient(135deg, ${themeColors.error}15, transparent)`,
              borderLeft: '4px solid',
              borderLeftColor: themeColors.error,
              position: 'relative',
              overflow: 'hidden',
              '&:hover': {
                borderColor: themeColors.borderSecondary,
                boxShadow: `0 4px 12px ${themeColors.error}20`,
                transform: 'translateY(-2px)',
              },
              transition: 'all 0.2s',
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                right: 0,
                width: 80,
                height: 80,
                background: `radial-gradient(circle, ${themeColors.error}10, transparent)`,
                borderRadius: '50%',
                transform: 'translate(20px, -20px)',
              }}
            />
            <Typography
              variant="caption"
              sx={{
                textTransform: 'uppercase',
                fontSize: '0.75rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
                display: 'block',
                mb: 1,
                color: themeColors.textTertiary,
                position: 'relative',
                zIndex: 1,
              }}
            >
              Critical Exceptions
            </Typography>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                color: themeColors.textPrimary,
                position: 'relative',
                zIndex: 1,
              }}
            >
              {criticalCount.toLocaleString()}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: themeColors.borderPrimary,
              bgcolor: themeColors.bgSecondary,
              background: `linear-gradient(135deg, ${themeColors.primary}15, transparent)`,
              borderLeft: '4px solid',
              borderLeftColor: themeColors.primary,
              position: 'relative',
              overflow: 'hidden',
              '&:hover': {
                borderColor: themeColors.borderSecondary,
                boxShadow: `0 4px 12px ${themeColors.primary}20`,
                transform: 'translateY(-2px)',
              },
              transition: 'all 0.2s',
            }}
          >
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                right: 0,
                width: 80,
                height: 80,
                background: `radial-gradient(circle, ${themeColors.primary}10, transparent)`,
                borderRadius: '50%',
                transform: 'translate(20px, -20px)',
              }}
            />
            <Typography
              variant="caption"
              sx={{
                textTransform: 'uppercase',
                fontSize: '0.75rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
                display: 'block',
                mb: 1,
                color: themeColors.textTertiary,
                position: 'relative',
                zIndex: 1,
              }}
            >
              AI Resolution Rate
            </Typography>
            <Typography
              variant="h4"
              sx={{
                fontWeight: 700,
                color: themeColors.textPrimary,
                position: 'relative',
                zIndex: 1,
              }}
            >
              —
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: themeColors.borderPrimary,
              bgcolor: themeColors.bgSecondary,
              position: 'relative',
              overflow: 'hidden',
              '&:hover': {
                borderColor: themeColors.borderSecondary,
                boxShadow: `0 4px 12px ${themeColors.warning}20`,
                transform: 'translateY(-2px)',
              },
              transition: 'all 0.2s',
            }}
          >
            <Typography
              variant="caption"
              sx={{
                textTransform: 'uppercase',
                fontSize: '0.75rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
                display: 'block',
                mb: 1,
                color: themeColors.textTertiary,
              }}
            >
              Open Exceptions
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: themeColors.textPrimary }}>
              {openCount.toLocaleString()}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Paper
            sx={{
              p: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: themeColors.borderPrimary,
              bgcolor: themeColors.bgSecondary,
              position: 'relative',
              overflow: 'hidden',
              '&:hover': {
                borderColor: themeColors.borderSecondary,
                boxShadow: `0 4px 12px ${themeColors.info}20`,
                transform: 'translateY(-2px)',
              },
              transition: 'all 0.2s',
            }}
          >
            <Typography
              variant="caption"
              sx={{
                textTransform: 'uppercase',
                fontSize: '0.75rem',
                fontWeight: 700,
                letterSpacing: '0.05em',
                display: 'block',
                mb: 1,
                color: themeColors.textTertiary,
              }}
            >
              Total Exceptions
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 700, color: themeColors.textPrimary }}>
              {totalCount.toLocaleString()}
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Filters + Table Section */}
      <Paper
        sx={{
          p: 2,
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        {/* Filter Bar */}
        <Box sx={{ mb: 2 }}>
          <FilterBar value={filters} onChange={handleFilterChange} />
        </Box>

        {/* Error State */}
        {isError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Failed to load exceptions: {error?.message || 'Unknown error'}
          </Alert>
        )}

        {/* Data Table */}
        {tenantId ? (
          <Box
            sx={{
              '& .MuiPaper-root': {
                backgroundColor: 'background.paper',
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider',
                boxShadow: 'none',
              },
            }}
          >
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
          </Box>
        ) : (
          <Alert severity="info">
            Please select a tenant to view exceptions.
          </Alert>
        )}
      </Paper>
    </Box>
  )
}
