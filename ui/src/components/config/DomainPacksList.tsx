import { useState, useMemo } from 'react'
import { Box, Alert } from '@mui/material'
import DataTable from '../common/DataTable.tsx'
import { useDomainPacks } from '../../hooks/useConfig.ts'
import { formatDateTime } from '../../utils/dateFormat.ts'
import type { ConfigListItem } from '../../types'

/**
 * Common config filters interface
 */
export interface CommonConfigFilters {
  tenantId?: string
  domain?: string
}

/**
 * Props for DomainPacksList component
 */
export interface DomainPacksListProps {
  filters: CommonConfigFilters
  onSelectItem: (type: 'domain-packs' | 'tenant-policies' | 'playbooks', id: string) => void
}

/**
 * Domain Packs List Component
 * 
 * Displays a table of domain packs with filtering, pagination, and sorting.
 */
export default function DomainPacksList({ filters, onSelectItem }: DomainPacksListProps) {
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(50)
  const [sortField, setSortField] = useState<string>('timestamp')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  // Prepare API parameters
  const apiParams = {
    ...(filters.tenantId ? { tenant_id: filters.tenantId } : {}),
    ...(filters.domain ? { domain: filters.domain } : {}),
  }

  // Fetch domain packs
  const { data, isLoading, isError, error } = useDomainPacks(apiParams)

  // Client-side sorting (backend doesn't support sorting yet)
  const sortedItems = useMemo(() => {
    if (!data?.items) return []
    const items = [...data.items]
    
    if (!sortField) return items
    
    return items.sort((a, b) => {
      const aValue = a[sortField]
      const bValue = b[sortField]
      
      if (aValue === null || aValue === undefined) return 1
      if (bValue === null || bValue === undefined) return -1
      
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortDirection === 'asc' 
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue)
      }
      
      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortDirection === 'asc' ? aValue - bValue : bValue - aValue
      }
      
      return 0
    })
  }, [data?.items, sortField, sortDirection])

  // Client-side pagination
  const paginatedItems = useMemo(() => {
    const start = page * pageSize
    return sortedItems.slice(start, start + pageSize)
  }, [sortedItems, page, pageSize])

  // Define columns
  const columns = [
    {
      id: 'id',
      label: 'Pack ID',
      accessor: (row: ConfigListItem) => (
        <Box
          component="span"
          sx={{
            fontFamily: 'monospace',
            fontSize: '0.875rem',
            cursor: 'pointer',
            color: 'primary.main',
            '&:hover': { textDecoration: 'underline' },
          }}
          onClick={() => onSelectItem('domain-packs', row.id)}
        >
          {row.id}
        </Box>
      ),
    },
    {
      id: 'name',
      label: 'Name',
      accessor: (row: ConfigListItem) => row.name || '—',
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row: ConfigListItem) => row.version || '—',
    },
    {
      id: 'tenant_id',
      label: 'Tenant ID',
      accessor: (row: ConfigListItem) => (
        <Box component="span" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
          {row.tenant_id}
        </Box>
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row: ConfigListItem) => row.domain || '—',
    },
    {
      id: 'timestamp',
      label: 'Timestamp',
      accessor: (row: ConfigListItem) => formatDateTime(row.timestamp),
    },
  ]

  // Handle sorting
  const handleSortChange = (field: string, direction: 'asc' | 'desc') => {
    setSortField(field)
    setSortDirection(direction)
    setPage(0) // Reset to first page on sort
  }

  // Handle pagination
  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(0) // Reset to first page
  }

  // Error state
  if (isError) {
    return (
      <Alert severity="error">
        Failed to load domain packs: {error?.message || 'Unknown error'}
      </Alert>
    )
  }

  return (
    <DataTable
      columns={columns}
      rows={paginatedItems}
      loading={isLoading}
      page={page}
      pageSize={pageSize}
      totalCount={data?.total || sortedItems.length}
      onPageChange={handlePageChange}
      onPageSizeChange={handlePageSizeChange}
      sortField={sortField}
      sortDirection={sortDirection}
      onSortChange={handleSortChange}
      emptyTitle="No domain packs found"
      emptyMessage="No domain packs match the selected filters. Try adjusting your tenant or domain filters."
    />
  )
}

