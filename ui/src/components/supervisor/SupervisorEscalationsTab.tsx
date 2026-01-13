import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Box, Alert } from '@mui/material'
import DataTable, { type DataTableColumn } from '../common/DataTable.tsx'
import { SeverityChip } from '../common'
import { useSupervisorEscalations } from '../../hooks/useSupervisor.ts'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { EscalationItem } from '../../types'

/**
 * Props for SupervisorEscalationsTab component
 */
export interface SupervisorEscalationsTabProps {
  /** Filter parameters */
  filters: {
    tenantId?: string
    domain?: string
    from_ts?: string
    to_ts?: string
  }
}


/**
 * Supervisor Escalations Tab Component
 * 
 * Displays a table of escalated exceptions with filtering, pagination, and sorting.
 */
export default function SupervisorEscalationsTab({ filters }: SupervisorEscalationsTabProps) {
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

  // Fetch escalations
  const { data, isLoading, isError, error } = useSupervisorEscalations(apiParams)

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
  const columns: DataTableColumn<EscalationItem>[] = useMemo(
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
          <Box sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
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
        id: 'exception_type',
        label: 'Exception Type',
        minWidth: 150,
        accessor: (row) => row.exception_type || '—',
      },
      {
        id: 'severity',
        label: 'Severity',
        minWidth: 100,
        accessor: (row) => <SeverityChip severity={row.severity} size="small" />,
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
        id: 'escalation_reason',
        label: 'Escalation Reason',
        minWidth: 200,
        accessor: (row) => (
          <Box
            sx={{
              maxWidth: 300,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={row.escalation_reason}
          >
            {row.escalation_reason}
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
        Failed to load escalations: {error?.message || 'Unknown error'}
      </Alert>
    )
  }

  // Get escalations data
  const escalations = data?.escalations || []
  const totalCount = data?.total || 0

  // Note: Since the API uses limit-based pagination, we need to handle pagination client-side
  // For MVP, we'll show the first pageSize items. In a real implementation, the API would support
  // offset/limit or page/pageSize pagination.
  const paginatedEscalations = escalations.slice(page * pageSize, (page + 1) * pageSize)

  // Sort escalations client-side (since API doesn't support sorting)
  const sortedEscalations = useMemo(() => {
    const sorted = [...paginatedEscalations]
    sorted.sort((a, b) => {
      let aValue: unknown = a[sortField as keyof EscalationItem]
      let bValue: unknown = b[sortField as keyof EscalationItem]

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
  }, [paginatedEscalations, sortField, sortDirection])

  return (
    <Box>
      <DataTable<EscalationItem>
        columns={columns}
        rows={sortedEscalations}
        loading={isLoading}
        page={page}
        pageSize={pageSize}
        totalCount={totalCount}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
        sortField={sortField}
        sortDirection={sortDirection}
        onSortChange={handleSortChange}
        emptyTitle="No escalations found"
        emptyMessage="No escalated exceptions match the selected filters. Try adjusting your filters or date range."
      />
    </Box>
  )
}

