/**
 * Tools Page Component
 * 
 * Provides a browser interface for viewing and managing tools.
 * Supports filtering by scope and enabled status, and navigation to tool detail views.
 * 
 * Phase 8 P8-10: Tools list page with filters and table view
 */

import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  InputAdornment,
  Stack,
  IconButton,
  Tooltip,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import VisibilityIcon from '@mui/icons-material/Visibility'
import { useToolsList } from '../hooks/useTools'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { TableSkeleton } from '../components/common'
import { EmptyState } from '../components/common'
import type { ToolDefinition } from '../api/tools'

/**
 * Scope filter options
 */
type ScopeFilter = 'all' | 'global' | 'tenant'

/**
 * Status filter options
 */
type StatusFilter = 'all' | 'enabled' | 'disabled'

/**
 * Tools Page Component
 */
export default function ToolsPage() {
  useDocumentTitle('Tools')
  const navigate = useNavigate()

  // Filter state
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [nameFilter, setNameFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(50)

  // Build query params
  const queryParams = useMemo(() => {
    const params: Record<string, string> = {}
    if (scopeFilter !== 'all') {
      params.scope = scopeFilter
    }
    if (statusFilter !== 'all') {
      params.status = statusFilter
    }
    if (nameFilter.trim()) {
      params.name = nameFilter.trim()
    }
    if (typeFilter.trim()) {
      params.type = typeFilter.trim()
    }
    return params
  }, [scopeFilter, statusFilter, nameFilter, typeFilter])

  // Fetch tools
  const { data, isLoading, error } = useToolsList(queryParams)

  // Handle pagination
  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage)
  }

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPageSize(parseInt(event.target.value, 10))
    setPage(0)
  }

  // Paginate data (client-side pagination for MVP)
  const paginatedItems = useMemo(() => {
    if (!data?.items) return []
    const start = page * pageSize
    const end = start + pageSize
    return data.items.slice(start, end)
  }, [data?.items, page, pageSize])

  // Handle row click to navigate to detail
  const handleRowClick = (toolId: number) => {
    navigate(`/tools/${toolId}`)
  }

  // Render scope chip
  const renderScopeChip = (tenantId: string | null) => {
    if (tenantId === null) {
      return <Chip label="Global" size="small" color="primary" variant="outlined" />
    }
    return <Chip label="Tenant" size="small" color="secondary" variant="outlined" />
  }

  // Render status chip
  const renderStatusChip = (enabled: boolean | null) => {
    if (enabled === null) {
      return <Chip label="Unknown" size="small" color="default" variant="outlined" />
    }
    if (enabled) {
      return <Chip label="Enabled" size="small" color="success" />
    }
    return <Chip label="Disabled" size="small" color="error" />
  }

  return (
    <Box>
      {/* Page Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 600, mb: 1 }}>
          Tools
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage and view tool definitions. Tools can be global (available to all tenants) or tenant-scoped.
        </Typography>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Scope</InputLabel>
            <Select
              value={scopeFilter}
              label="Scope"
              onChange={(e) => setScopeFilter(e.target.value as ScopeFilter)}
            >
              <MenuItem value="all">All</MenuItem>
              <MenuItem value="global">Global</MenuItem>
              <MenuItem value="tenant">Tenant</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={statusFilter}
              label="Status"
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            >
              <MenuItem value="all">All</MenuItem>
              <MenuItem value="enabled">Enabled</MenuItem>
              <MenuItem value="disabled">Disabled</MenuItem>
            </Select>
          </FormControl>

          <TextField
            size="small"
            placeholder="Filter by name"
            value={nameFilter}
            onChange={(e) => setNameFilter(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
            sx={{ flexGrow: 1, maxWidth: 300 }}
          />

          <TextField
            size="small"
            placeholder="Filter by type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            sx={{ flexGrow: 1, maxWidth: 200 }}
          />
        </Stack>
      </Paper>

      {/* Tools Table */}
      <Paper>
        {isLoading ? (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Scope</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableSkeleton rowCount={5} columnCount={5} />
            </Table>
          </TableContainer>
        ) : error ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="error">Error loading tools: {error.message}</Typography>
          </Box>
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            title="No tools found"
            description="No tools match the current filters. Try adjusting your search criteria."
          />
        ) : (
          <>
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Type</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Scope</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {paginatedItems.map((tool: ToolDefinition) => (
                    <TableRow
                      key={tool.toolId}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => handleRowClick(tool.toolId)}
                    >
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {tool.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={tool.type} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>{renderScopeChip(tool.tenantId)}</TableCell>
                      <TableCell>{renderStatusChip(tool.enabled)}</TableCell>
                      <TableCell>
                        <Tooltip title="View details">
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleRowClick(tool.toolId)
                            }}
                          >
                            <VisibilityIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={data.total}
              page={page}
              onPageChange={handleChangePage}
              rowsPerPage={pageSize}
              onRowsPerPageChange={handleChangeRowsPerPage}
              rowsPerPageOptions={[25, 50, 100]}
            />
          </>
        )}
      </Paper>
    </Box>
  )
}

