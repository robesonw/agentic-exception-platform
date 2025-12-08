import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  Paper,
} from '@mui/material'
import TableSkeleton from './TableSkeleton'
import EmptyState from './EmptyState'

export interface DataTableColumn<TRow> {
  id: string
  label: string
  accessor?: (row: TRow) => React.ReactNode
  disableSort?: boolean
  numeric?: boolean
  minWidth?: number
}

export interface DataTableProps<TRow> {
  columns: DataTableColumn<TRow>[]
  rows: TRow[]
  loading?: boolean
  page: number
  pageSize: number
  totalCount: number
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  sortField?: string
  sortDirection?: 'asc' | 'desc'
  onSortChange?: (field: string, direction: 'asc' | 'desc') => void
  emptyMessage?: string
  emptyTitle?: string
  emptyAction?: React.ReactNode
}

export default function DataTable<TRow extends Record<string, unknown>>({
  columns,
  rows,
  loading = false,
  page,
  pageSize,
  totalCount,
  onPageChange,
  onPageSizeChange,
  sortField,
  sortDirection,
  onSortChange,
  emptyMessage = 'No records found.',
  emptyTitle,
  emptyAction,
}: DataTableProps<TRow>) {
  const handleSort = (columnId: string) => {
    if (!onSortChange) return

    const isAsc = sortField === columnId && sortDirection === 'asc'
    const newDirection = isAsc ? 'desc' : 'asc'
    onSortChange(columnId, newDirection)
  }

  const handleChangePage = (_event: unknown, newPage: number) => {
    onPageChange(newPage)
  }

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    onPageSizeChange(parseInt(event.target.value, 10))
    onPageChange(0) // Reset to first page when page size changes
  }

  const renderCell = (row: TRow, column: DataTableColumn<TRow>): React.ReactNode => {
    if (column.accessor) {
      return column.accessor(row)
    }
    // Fallback to direct property access
    const value = (row as Record<string, unknown>)[column.id]
    if (value === null || value === undefined) {
      return null
    }
    if (typeof value === 'object') {
      return JSON.stringify(value)
    }
    return String(value)
  }

  return (
    <Paper sx={{ width: '100%', overflow: 'hidden' }}>
      <TableContainer sx={{ maxHeight: 'calc(100vh - 300px)', overflowX: 'auto' }}>
        <Table stickyHeader size="small" aria-label="data table">
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableCell
                  key={column.id}
                  align={column.numeric ? 'right' : 'left'}
                  style={{ minWidth: column.minWidth }}
                  sortDirection={sortField === column.id ? sortDirection : false}
                  sx={{
                    backgroundColor: 'background.default',
                    borderBottom: '2px solid',
                    borderColor: 'divider',
                    fontWeight: 600,
                    fontSize: '0.875rem',
                  }}
                >
                  {column.disableSort || !onSortChange ? (
                    column.label
                  ) : (
                    <TableSortLabel
                      active={sortField === column.id}
                      direction={sortField === column.id ? sortDirection : 'asc'}
                      onClick={() => handleSort(column.id)}
                    >
                      {column.label}
                    </TableSortLabel>
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          {loading ? (
            <TableSkeleton rowCount={pageSize} columnCount={columns.length} />
          ) : (
            <TableBody>
              {rows.length === 0 ? (
                // Empty state
                <TableRow>
                  <TableCell colSpan={columns.length} sx={{ p: 0, border: 0 }}>
                    <EmptyState
                      title={emptyTitle || 'No records found'}
                      description={emptyMessage}
                      action={emptyAction}
                      sx={{ py: 4 }}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                // Data rows
                rows.map((row, rowIndex) => (
                  <TableRow
                    key={rowIndex}
                    hover
                    sx={{
                      '&:last-child td, &:last-child th': { border: 0 },
                      '&:hover': {
                        backgroundColor: 'action.hover',
                        cursor: 'pointer',
                      },
                      transition: 'background-color 0.2s ease',
                    }}
                  >
                    {columns.map((column) => (
                      <TableCell
                        key={column.id}
                        align={column.numeric ? 'right' : 'left'}
                      >
                        {renderCell(row, column)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          )}
        </Table>
      </TableContainer>
      <TablePagination
        component="div"
        count={totalCount}
        page={page}
        onPageChange={handleChangePage}
        rowsPerPage={pageSize}
        onRowsPerPageChange={handleChangeRowsPerPage}
        rowsPerPageOptions={[10, 25, 50, 100]}
        labelRowsPerPage="Rows per page:"
        labelDisplayedRows={({ from, to, count }) =>
          `${from}–${to} of ${count !== -1 ? count : `more than ${to}`}`
        }
      />
    </Paper>
  )
}

