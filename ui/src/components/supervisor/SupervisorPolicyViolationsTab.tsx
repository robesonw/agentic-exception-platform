import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Box, Chip, Alert } from '@mui/material'
import DataTable, { type DataTableColumn } from '../common/DataTable.tsx'
import { useSupervisorPolicyViolations } from '../../hooks/useSupervisor.ts'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { PolicyViolationItem } from '../../types'

/**
 * Props for SupervisorPolicyViolationsTab component
 */
export interface SupervisorPolicyViolationsTabProps {
  /** Filter parameters */
  filters: {
    tenantId?: string
    domain?: string
    from_ts?: string
    to_ts?: string
  }
}

/**
 * Supervisor Policy Violations Tab Component
 * 
 * Displays a table of policy violations with filtering, pagination, and sorting.
 */
export default function SupervisorPolicyViolationsTab({ filters }: SupervisorPolicyViolationsTabProps) {
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(50)
  const [sortField, setSortField] = useState<string>('timestamp')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  // Prepare API parameters
  const apiParams = useMemo(() => {
    const params: { domain?: string; limit?: number } = {}
    if (filters.domain) {
      params.domain = filters.domain
    }
    // Note: API uses limit, not page/pageSize, so we calculate limit from page and pageSize
    params.limit = pageSize
    return params
  }, [filters.domain, pageSize])

  // Fetch policy violations
  const { data, isLoading, isError, error } = useSupervisorPolicyViolations(apiParams)

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

  // Define table columns
  const columns: DataTableColumn<PolicyViolationItem>[] = useMemo(
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
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              {row.exception_id}
            </Box>
          </Link>
        ),
      },
      {
        id: 'tenant_id',
        label: 'Tenant ID',
        minWidth: 120,
        accessor: (row) => (
          <Box component="span" sx={{ fontFamily: 'monospace', fontWeight: 500, color: 'primary.main', fontSize: '0.8125rem' }}>
            {row.tenant_id}
          </Box>
        ),
      },
      {
        id: 'domain',
        label: 'Domain',
        minWidth: 100,
        accessor: (row) => row.domain || '—',
      },
      {
        id: 'timestamp',
        label: 'Timestamp',
        minWidth: 150,
        accessor: (row) => (
          <Box component="span" sx={{ color: 'text.secondary', fontSize: '0.8125rem' }}>
            {formatDateTime(row.timestamp)}
          </Box>
        ),
      },
      {
        id: 'violation_type',
        label: 'Violation Type',
        minWidth: 120,
        accessor: (row) => (
          <Chip
            label={row.violation_type}
            size="small"
            color="error"
          />
        ),
      },
      {
        id: 'violated_rule',
        label: 'Violated Rule',
        minWidth: 150,
        accessor: (row) => (
          <Box
            sx={{
              maxWidth: 200,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={row.violated_rule}
          >
            {row.violated_rule}
          </Box>
        ),
      },
      {
        id: 'decision',
        label: 'Decision',
        minWidth: 150,
        accessor: (row) => (
          <Box
            sx={{
              maxWidth: 200,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={row.decision}
          >
            {row.decision}
          </Box>
        ),
      },
    ],
    []
  )

  // Error state
  if (isError) {
    return (
      <Alert severity="error">
        Failed to load policy violations: {error?.message || 'Unknown error'}
      </Alert>
    )
  }

  // Get violations data
  const violations = data?.violations || []
  const totalCount = data?.total || 0

  // Note: Since the API uses limit-based pagination, we need to handle pagination client-side
  // For MVP, we'll show the first pageSize items. In a real implementation, the API would support
  // offset/limit or page/pageSize pagination.
  const paginatedViolations = violations.slice(page * pageSize, (page + 1) * pageSize)

  // Sort violations client-side (since API doesn't support sorting)
  const sortedViolations = useMemo(() => {
    const sorted = [...paginatedViolations]
    sorted.sort((a, b) => {
      let aValue: unknown = a[sortField as keyof PolicyViolationItem]
      let bValue: unknown = b[sortField as keyof PolicyViolationItem]

      // Handle null/undefined
      if (aValue == null) aValue = ''
      if (bValue == null) bValue = ''

      // Convert to strings for comparison
      const aStr = String(aValue)
      const bStr = String(bValue)

      if (sortDirection === 'asc') {
        return aStr.localeCompare(bStr)
      } else {
        return bStr.localeCompare(aStr)
      }
    })
    return sorted
  }, [paginatedViolations, sortField, sortDirection])

  return (
    <Box>
      <DataTable<PolicyViolationItem>
        columns={columns}
        rows={sortedViolations}
        loading={isLoading}
        page={page}
        pageSize={pageSize}
        totalCount={totalCount}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
        sortField={sortField}
        sortDirection={sortDirection}
        onSortChange={handleSortChange}
        emptyTitle="No policy violations found"
        emptyMessage="No policy violations match the selected filters. Try adjusting your filters or date range."
      />
    </Box>
  )
}

