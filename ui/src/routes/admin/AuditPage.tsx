/**
 * Admin Audit Page - Phase 12+ Governance & Audit Polish
 *
 * Provides a comprehensive view of governance audit events with:
 * - Filtering by tenant, domain, entity type, event type, date range
 * - Pagination and sorting
 * - Detail drawer with before/after JSON (redacted)
 * - Correlation ID tracing
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Grid,
  Card,
  CardContent,
  Tooltip,
  IconButton,
  Divider,
  Alert,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material'
import FilterListIcon from '@mui/icons-material/FilterList'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import LinkIcon from '@mui/icons-material/Link'
import RefreshIcon from '@mui/icons-material/Refresh'
import SearchIcon from '@mui/icons-material/Search'
import { useTenant } from '../../hooks/useTenant'
import {
  listAuditEvents,
  getAuditEvent,
  getEventsByCorrelation,
  type GovernanceAuditEvent,
  type ListAuditEventsParams,
  ENTITY_TYPES,
  ACTIONS,
  EVENT_TYPES,
  getEntityTypeLabel,
  getActionLabel,
  getActionColor,
} from '../../api/governanceAudit'
import { listTenants } from '../../api/onboarding'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import CodeViewer from '../../components/common/CodeViewer'
import type { DataTableColumn } from '../../components/common/DataTable'
import { isAdminEnabled } from '../../utils/featureFlags'
import { formatDateTime, formatRelativeTime } from '../../utils/dateFormat'
import { useSnackbar } from '../../components/common/SnackbarProvider'

export default function AuditPage() {
  const { tenantId } = useTenant()
  const { showSuccess, showError } = useSnackbar()
  const isAdmin = isAdminEnabled()

  // Pagination state
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)

  // Filter state
  const [showFilters, setShowFilters] = useState(true)
  const [filters, setFilters] = useState<ListAuditEventsParams>({})

  // Detail dialog state
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<GovernanceAuditEvent | null>(null)
  const [correlatedEvents, setCorrelatedEvents] = useState<GovernanceAuditEvent[]>([])

  // Query audit events
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['audit-events', page, pageSize, filters],
    queryFn: () =>
      listAuditEvents({
        ...filters,
        page: page + 1,
        page_size: pageSize,
      }),
    enabled: isAdmin,
  })

  // Query tenants for filter dropdown
  const { data: tenantsData } = useQuery({
    queryKey: ['tenants-for-filter'],
    queryFn: () => listTenants({ page_size: 100 }),
    enabled: isAdmin,
  })

  // Handle 401/403 errors
  if (isError && error && 'status' in error && (error.status === 401 || error.status === 403)) {
    return <NotAuthorizedPage />
  }

  if (!isAdmin) {
    return <NotAuthorizedPage />
  }

  const handleViewDetail = async (event: GovernanceAuditEvent) => {
    setSelectedEvent(event)
    setDetailDialogOpen(true)

    // Load correlated events if correlation ID exists
    if (event.correlation_id) {
      try {
        const correlated = await getEventsByCorrelation(event.correlation_id)
        setCorrelatedEvents(correlated.filter((e) => e.id !== event.id))
      } catch (err) {
        console.error('Failed to load correlated events:', err)
        setCorrelatedEvents([])
      }
    } else {
      setCorrelatedEvents([])
    }
  }

  const handleCloseDetail = () => {
    setDetailDialogOpen(false)
    setSelectedEvent(null)
    setCorrelatedEvents([])
  }

  const handleFilterChange = (key: keyof ListAuditEventsParams, value: string) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value || undefined,
    }))
    setPage(0) // Reset to first page on filter change
  }

  const handleClearFilters = () => {
    setFilters({})
    setPage(0)
  }

  const columns: DataTableColumn<GovernanceAuditEvent>[] = [
    {
      id: 'created_at',
      label: 'Time',
      accessor: (row) => (
        <Tooltip title={formatDateTime(row.created_at)}>
          <Typography variant="body2" sx={{ whiteSpace: 'nowrap' }}>
            {formatRelativeTime(row.created_at)}
          </Typography>
        </Tooltip>
      ),
    },
    {
      id: 'event_type',
      label: 'Event',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.event_type}
        </Typography>
      ),
    },
    {
      id: 'tenant_id',
      label: 'Tenant',
      accessor: (row) =>
        row.tenant_id ? (
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
            {row.tenant_id}
          </Typography>
        ) : (
          <Typography variant="body2" color="text.secondary">
            -
          </Typography>
        ),
    },
    {
      id: 'entity_type',
      label: 'Entity',
      accessor: (row) => (
        <Box>
          <Chip
            label={getEntityTypeLabel(row.entity_type)}
            size="small"
            variant="outlined"
            sx={{ mr: 0.5 }}
          />
          <Typography
            variant="caption"
            sx={{ fontFamily: 'monospace', display: 'block', mt: 0.25 }}
          >
            {row.entity_id}
            {row.entity_version && ` (${row.entity_version})`}
          </Typography>
        </Box>
      ),
    },
    {
      id: 'action',
      label: 'Action',
      accessor: (row) => (
        <Chip
          label={getActionLabel(row.action)}
          size="small"
          color={getActionColor(row.action)}
        />
      ),
    },
    {
      id: 'actor_id',
      label: 'Actor',
      accessor: (row) => (
        <Box>
          <Typography variant="body2">{row.actor_id}</Typography>
          {row.actor_role && (
            <Typography variant="caption" color="text.secondary">
              {row.actor_role}
            </Typography>
          )}
        </Box>
      ),
    },
    {
      id: 'correlation_id',
      label: 'Correlation',
      accessor: (row) =>
        row.correlation_id ? (
          <Tooltip title={`Trace: ${row.correlation_id}`}>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'monospace',
                maxWidth: 80,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                display: 'block',
              }}
            >
              {row.correlation_id.slice(0, 12)}...
            </Typography>
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      id: 'actions',
      label: '',
      accessor: (row) => (
        <Button size="small" onClick={() => handleViewDetail(row)}>
          Details
        </Button>
      ),
    },
  ]

  return (
    <Box>
      <PageHeader
        title="Governance Audit Trail"
        subtitle="Enterprise audit events for tenant and configuration changes"
        actions={
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<FilterListIcon />}
              onClick={() => setShowFilters(!showFilters)}
            >
              {showFilters ? 'Hide Filters' : 'Show Filters'}
            </Button>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={() => refetch()}
            >
              Refresh
            </Button>
          </Box>
        }
      />

      <AdminWarningBanner />

      {/* Filter Panel */}
      {showFilters && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Tenant</InputLabel>
                <Select
                  value={filters.tenant_id || ''}
                  label="Tenant"
                  onChange={(e) => handleFilterChange('tenant_id', e.target.value)}
                >
                  <MenuItem value="">
                    <em>All Tenants</em>
                  </MenuItem>
                  {tenantsData?.items.map((tenant) => (
                    <MenuItem key={tenant.tenant_id} value={tenant.tenant_id}>
                      {tenant.tenant_id}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Entity Type</InputLabel>
                <Select
                  value={filters.entity_type || ''}
                  label="Entity Type"
                  onChange={(e) => handleFilterChange('entity_type', e.target.value)}
                >
                  <MenuItem value="">
                    <em>All Types</em>
                  </MenuItem>
                  {ENTITY_TYPES.map((type) => (
                    <MenuItem key={type} value={type}>
                      {getEntityTypeLabel(type)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Action</InputLabel>
                <Select
                  value={filters.action || ''}
                  label="Action"
                  onChange={(e) => handleFilterChange('action', e.target.value)}
                >
                  <MenuItem value="">
                    <em>All Actions</em>
                  </MenuItem>
                  {ACTIONS.map((action) => (
                    <MenuItem key={action} value={action}>
                      {getActionLabel(action)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Domain"
                value={filters.domain || ''}
                onChange={(e) => handleFilterChange('domain', e.target.value)}
                placeholder="e.g., PAYMENTS"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Entity ID"
                value={filters.entity_id || ''}
                onChange={(e) => handleFilterChange('entity_id', e.target.value)}
                placeholder="e.g., TENANT_001"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Actor ID"
                value={filters.actor_id || ''}
                onChange={(e) => handleFilterChange('actor_id', e.target.value)}
                placeholder="e.g., admin@example.com"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                type="date"
                label="From Date"
                value={filters.from_date?.split('T')[0] || ''}
                onChange={(e) =>
                  handleFilterChange('from_date', e.target.value ? `${e.target.value}T00:00:00Z` : '')
                }
                InputLabelProps={{ shrink: true }}
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                size="small"
                type="date"
                label="To Date"
                value={filters.to_date?.split('T')[0] || ''}
                onChange={(e) =>
                  handleFilterChange('to_date', e.target.value ? `${e.target.value}T23:59:59Z` : '')
                }
                InputLabelProps={{ shrink: true }}
              />
            </Grid>

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                <Button variant="outlined" onClick={handleClearFilters}>
                  Clear Filters
                </Button>
                <Button variant="contained" startIcon={<SearchIcon />} onClick={() => refetch()}>
                  Search
                </Button>
              </Box>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Error state */}
      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load audit events. Please try again.
        </Alert>
      )}

      {/* Results table */}
      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={isLoading}
        page={page}
        pageSize={pageSize}
        totalCount={data?.total || 0}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        emptyMessage="No audit events found matching your filters."
      />

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={handleCloseDetail}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            Audit Event Details
            {selectedEvent && (
              <Chip
                label={getActionLabel(selectedEvent.action)}
                size="small"
                color={getActionColor(selectedEvent.action)}
              />
            )}
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedEvent && (
            <Box>
              {/* Event metadata */}
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Event Type
                  </Typography>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                    {selectedEvent.event_type}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Timestamp
                  </Typography>
                  <Typography variant="body1">
                    {formatDateTime(selectedEvent.created_at)}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Entity
                  </Typography>
                  <Typography variant="body1">
                    {getEntityTypeLabel(selectedEvent.entity_type)}: {selectedEvent.entity_id}
                    {selectedEvent.entity_version && ` (${selectedEvent.entity_version})`}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Tenant
                  </Typography>
                  <Typography variant="body1">
                    {selectedEvent.tenant_id || 'Global'}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Domain
                  </Typography>
                  <Typography variant="body1">
                    {selectedEvent.domain || '-'}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Actor
                  </Typography>
                  <Typography variant="body1">
                    {selectedEvent.actor_id}
                    {selectedEvent.actor_role && ` (${selectedEvent.actor_role})`}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    IP Address
                  </Typography>
                  <Typography variant="body1">
                    {selectedEvent.ip_address || '-'}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Correlation ID
                  </Typography>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {selectedEvent.correlation_id || '-'}
                  </Typography>
                </Grid>
              </Grid>

              {/* Diff Summary */}
              {selectedEvent.diff_summary && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Change Summary
                  </Typography>
                  <Alert severity="info" sx={{ fontFamily: 'monospace' }}>
                    {selectedEvent.diff_summary}
                  </Alert>
                </Box>
              )}

              {/* Before/After JSON */}
              <Grid container spacing={2}>
                {selectedEvent.before_json && (
                  <Grid item xs={12} md={6}>
                    <Accordion defaultExpanded>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2">Before</Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <CodeViewer
                          code={JSON.stringify(selectedEvent.before_json, null, 2)}
                          language="json"
                          maxHeight={300}
                        />
                      </AccordionDetails>
                    </Accordion>
                  </Grid>
                )}
                {selectedEvent.after_json && (
                  <Grid item xs={12} md={selectedEvent.before_json ? 6 : 12}>
                    <Accordion defaultExpanded>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2">After</Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <CodeViewer
                          code={JSON.stringify(selectedEvent.after_json, null, 2)}
                          language="json"
                          maxHeight={300}
                        />
                      </AccordionDetails>
                    </Accordion>
                  </Grid>
                )}
              </Grid>

              {/* Correlated Events */}
              {correlatedEvents.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    <LinkIcon sx={{ mr: 0.5, verticalAlign: 'middle', fontSize: 16 }} />
                    Related Events ({correlatedEvents.length})
                  </Typography>
                  <Paper variant="outlined" sx={{ mt: 1 }}>
                    {correlatedEvents.map((event, idx) => (
                      <Box
                        key={event.id}
                        sx={{
                          p: 1.5,
                          borderBottom: idx < correlatedEvents.length - 1 ? '1px solid' : 'none',
                          borderColor: 'divider',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {event.event_type}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {getEntityTypeLabel(event.entity_type)}: {event.entity_id} •{' '}
                            {formatRelativeTime(event.created_at)}
                          </Typography>
                        </Box>
                        <Chip
                          label={getActionLabel(event.action)}
                          size="small"
                          color={getActionColor(event.action)}
                        />
                      </Box>
                    ))}
                  </Paper>
                </Box>
              )}

              {/* Additional Metadata */}
              {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                <Accordion sx={{ mt: 2 }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Additional Metadata</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <CodeViewer
                      code={JSON.stringify(selectedEvent.metadata, null, 2)}
                      language="json"
                      maxHeight={200}
                    />
                  </AccordionDetails>
                </Accordion>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDetail}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
