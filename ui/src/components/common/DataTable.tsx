import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TablePagination,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  Checkbox,
  Box,
} from '@mui/material'
import DownloadIcon from '@mui/icons-material/Download'
import ViewColumnIcon from '@mui/icons-material/ViewColumn'
import TableSkeleton from './TableSkeleton'
import EmptyState from './EmptyState'
import { useState } from 'react'
import {
  tableHeaderCellSx,
  tableBodyCellSx,
  tableRowSx,
  tableContainerSx,
  tablePaginationSx,
  tableSortLabelSx,
} from './tableStyles'

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
  exportEnabled?: boolean
  onExport?: (format: 'csv' | 'json') => void
  columnVisibility?: Record<string, boolean>
  onColumnVisibilityChange?: (columnId: string, visible: boolean) => void
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
  exportEnabled = false,
  onExport,
  columnVisibility,
  onColumnVisibilityChange,
}: DataTableProps<TRow>) {
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(null)
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

  const visibleColumns = columns.filter(
    (col) => columnVisibility === undefined || columnVisibility[col.id] !== false
  )

  const handleExport = (format: 'csv' | 'json') => {
    if (onExport) {
      onExport(format)
    } else {
      // Default export implementation
      if (format === 'csv') {
        const headers = visibleColumns.map((col) => col.label).join(',')
        const csvRows = rows.map((row) =>
          visibleColumns
            .map((col) => {
              const value = col.accessor ? col.accessor(row) : (row as Record<string, unknown>)[col.id]
              return typeof value === 'string' ? `"${value.replace(/"/g, '""')}"` : value ?? ''
            })
            .join(',')
        )
        const csv = [headers, ...csvRows].join('\n')
        const blob = new Blob([csv], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `export-${new Date().toISOString()}.csv`
        a.click()
        URL.revokeObjectURL(url)
      } else {
        const json = JSON.stringify(rows, null, 2)
        const blob = new Blob([json], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `export-${new Date().toISOString()}.json`
        a.click()
        URL.revokeObjectURL(url)
      }
    }
  }

  return (
    <Box sx={{ width: '100%', overflow: 'hidden' }}>
      {/* Toolbar */}
      {(exportEnabled || onColumnVisibilityChange) && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 1,
            px: 2,
            py: 1,
            borderBottom: 1,
            borderColor: 'divider',
            backgroundColor: 'background.paper',
          }}
        >
          {onColumnVisibilityChange && (
            <>
              <Tooltip title="Column visibility">
                <IconButton
                  size="small"
                  onClick={(e) => setColumnMenuAnchor(e.currentTarget)}
                >
                  <ViewColumnIcon />
                </IconButton>
              </Tooltip>
              <Menu
                anchorEl={columnMenuAnchor}
                open={Boolean(columnMenuAnchor)}
                onClose={() => setColumnMenuAnchor(null)}
              >
                {columns.map((column) => (
                  <MenuItem key={column.id} dense>
                    <Checkbox
                      checked={columnVisibility?.[column.id] !== false}
                      onChange={(e) =>
                        onColumnVisibilityChange(column.id, e.target.checked)
                      }
                      size="small"
                    />
                    {column.label}
                  </MenuItem>
                ))}
              </Menu>
            </>
          )}
          {exportEnabled && (
            <Tooltip title="Export data">
              <IconButton size="small" onClick={() => handleExport('csv')}>
                <DownloadIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      )}
      <TableContainer sx={tableContainerSx}>
        <Table stickyHeader size="small" aria-label="data table">
          <TableHead>
            <TableRow>
              {visibleColumns.map((column) => (
                <TableCell
                  key={column.id}
                  align={column.numeric ? 'right' : 'left'}
                  style={{ minWidth: column.minWidth }}
                  sortDirection={sortField === column.id ? sortDirection : false}
                  sx={tableHeaderCellSx}
                >
                  {column.disableSort || !onSortChange ? (
                    column.label
                  ) : (
                    <TableSortLabel
                      active={sortField === column.id}
                      direction={sortField === column.id ? sortDirection : 'asc'}
                      onClick={() => handleSort(column.id)}
                      sx={tableSortLabelSx}
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
                  <TableCell colSpan={visibleColumns.length} sx={{ p: 0, border: 0 }}>
                    <EmptyState
                      title={emptyTitle || 'No records found'}
                      description={emptyMessage}
                      action={emptyAction}
                      sx={{ py: 6 }}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                // Data rows - consistent height, subtle hover
                rows.map((row, rowIndex) => (
                  <TableRow
                    key={rowIndex}
                    sx={tableRowSx}
                  >
                    {visibleColumns.map((column) => (
                      <TableCell
                        key={column.id}
                        align={column.numeric ? 'right' : 'left'}
                        sx={tableBodyCellSx}
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
        labelRowsPerPage="Rows:"
        labelDisplayedRows={({ from, to, count }) =>
          `${from}–${to} of ${count !== -1 ? count : `more than ${to}`}`
        }
        sx={tablePaginationSx}
      />
    </Box>
  )
}

