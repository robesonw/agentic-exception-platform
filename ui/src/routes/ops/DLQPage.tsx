import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Alert,
  Chip,
  Typography,
  CircularProgress,
  Drawer,
  IconButton,
  Button,
  Stack,
  Divider,
  Grid,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import RefreshIcon from '@mui/icons-material/Refresh'
import DeleteIcon from '@mui/icons-material/Delete'
import QueueIcon from '@mui/icons-material/Queue'
import PageHeader from '../../components/common/PageHeader'
import { useTenant } from '../../hooks/useTenant'
import { isOpsEnabled } from '../../utils/featureFlags'
import { listDLQEntries, getDLQEntry, retryDLQEntry, discardDLQEntry } from '../../api/ops'
import DataTable from '../../components/common/DataTable'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import CodeViewer from '../../components/common/CodeViewer'
import { useSnackbar } from '../../components/common/SnackbarProvider'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { DLQEntry } from '../../api/ops'
import type { OpsFilters } from '../../components/common/OpsFilterBar'

export default function DLQPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [filters, setFilters] = useState<OpsFilters>({})
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [selectedEntry, setSelectedEntry] = useState<DLQEntry | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [confirmAction, setConfirmAction] = useState<'retry' | 'discard' | null>(null)

  if (!isOpsEnabled()) {
    return (
      <Box>
        <Alert severity="error">Ops features are not enabled. Set VITE_OPS_ENABLED=true in ui/.env</Alert>
      </Box>
    )
  }

  const { data: dlqData, isLoading: dlqLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ['dlq-entries', tenantId, filters, page, pageSize],
    queryFn: () => listDLQEntries({
      tenantId: tenantId || '',
      status: filters.status,
      eventType: filters.eventType,
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: !!tenantId,
    refetchInterval: 30000,
  })

  const { data: entryDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['dlq-entry', selectedEntry?.eventId, tenantId],
    queryFn: () => getDLQEntry(selectedEntry!.eventId, tenantId || ''),
    enabled: !!selectedEntry && !!tenantId,
  })

  const retryMutation = useMutation({
    mutationFn: (id: string) => retryDLQEntry(id, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dlq-entries', tenantId] })
      setConfirmDialogOpen(false)
      setConfirmAction(null)
      showSuccess('DLQ entry retried successfully')
    },
    onError: (error) => {
      showError(`Failed to retry DLQ entry: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const discardMutation = useMutation({
    mutationFn: (id: string) => discardDLQEntry(id, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dlq-entries', tenantId] })
      setConfirmDialogOpen(false)
      setConfirmAction(null)
      if (selectedEntry) {
        setDrawerOpen(false)
        setSelectedEntry(null)
      }
      showSuccess('DLQ entry discarded successfully')
    },
    onError: (error) => {
      showError(`Failed to discard DLQ entry: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['dlq-entries', tenantId] })
    refetch()
  }

  const handleRowClick = (entry: DLQEntry) => {
    setSelectedEntry(entry)
    setDrawerOpen(true)
  }

  const handleRetry = () => {
    if (selectedEntry) {
      setConfirmAction('retry')
      setConfirmDialogOpen(true)
    }
  }

  const handleDiscard = () => {
    if (selectedEntry) {
      setConfirmAction('discard')
      setConfirmDialogOpen(true)
    }
  }

  const handleConfirm = () => {
    if (!selectedEntry) return
    if (confirmAction === 'retry') {
      retryMutation.mutate(selectedEntry.eventId)
    } else if (confirmAction === 'discard') {
      discardMutation.mutate(selectedEntry.eventId)
    }
  }

  const columns: DataTableColumn<DLQEntry>[] = [
    {
      id: 'eventId',
      label: 'Event ID',
      accessor: (row) => (
        <Typography
          variant="body2"
          sx={{ fontFamily: 'monospace', fontSize: '0.75rem', cursor: 'pointer', textDecoration: 'underline', color: 'primary.main' }}
          onClick={() => handleRowClick(row)}
        >
          {row.eventId.substring(0, 8)}...
        </Typography>
      ),
    },
    {
      id: 'eventType',
      label: 'Event Type',
      accessor: (row) => row.eventType,
    },
    {
      id: 'originalTopic',
      label: 'Topic',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.originalTopic}
        </Typography>
      ),
    },
    {
      id: 'workerType',
      label: 'Worker',
      accessor: (row) => row.workerType,
    },
    {
      id: 'status',
      label: 'Status',
      accessor: (row) => (
        <Chip
          label={row.status || 'pending'}
          size="small"
          color={
            row.status === 'succeeded' ? 'success' :
            row.status === 'retrying' ? 'warning' :
            row.status === 'discarded' ? 'default' : 'error'
          }
        />
      ),
    },
    {
      id: 'retryCount',
      label: 'Retries',
      numeric: true,
      accessor: (row) => row.retryCount,
    },
    {
      id: 'failedAt',
      label: 'Failed At',
      accessor: (row) => new Date(row.failedAt).toLocaleString(),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view DLQ messages.</Alert>
      </Box>
    )
  }

  const displayEntry = entryDetail || selectedEntry

  return (
    <Box>
      <PageHeader
        title="Dead Letter Queue (DLQ)"
        subtitle="View and manage failed messages in the DLQ"
        lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : undefined}
        onRefresh={handleRefresh}
      />

      <OpsFilterBar
        value={filters}
        onChange={setFilters}
        showStatus={true}
        showEventType={true}
        syncWithUrl={true}
      />

      <DataTable
        columns={columns as DataTableColumn<Record<string, unknown>>[]}
        rows={(dlqData?.items || []) as Record<string, unknown>[]}
        loading={dlqLoading}
        page={page}
        pageSize={pageSize}
        totalCount={dlqData?.total || 0}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        emptyTitle="No messages in DLQ"
        emptyMessage="No messages in DLQ. Trigger a failing exception to populate DLQ."
      />

      {/* Detail Drawer */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedEntry(null)
        }}
        PaperProps={{
          sx: { width: { xs: '100%', sm: 600 } },
        }}
      >
        <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">DLQ Entry Details</Typography>
            <IconButton onClick={() => {
              setDrawerOpen(false)
              setSelectedEntry(null)
            }}>
              <CloseIcon />
            </IconButton>
          </Box>

          {detailLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : displayEntry ? (
            <>
              <Grid container spacing={2} sx={{ mb: 3 }}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Event ID</Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {displayEntry.eventId}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Event Type</Typography>
                  <Typography variant="body2">{displayEntry.eventType}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Status</Typography>
                  <Box>
                    <Chip
                      label={displayEntry.status || 'pending'}
                      size="small"
                      color={
                        displayEntry.status === 'succeeded' ? 'success' :
                        displayEntry.status === 'retrying' ? 'warning' :
                        displayEntry.status === 'discarded' ? 'default' : 'error'
                      }
                    />
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Retry Count</Typography>
                  <Typography variant="body2">{displayEntry.retryCount}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Original Topic</Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {displayEntry.originalTopic}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Worker Type</Typography>
                  <Typography variant="body2">{displayEntry.workerType}</Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="caption" color="text.secondary">Failure Reason</Typography>
                  <Typography variant="body2" color="error.main">
                    {displayEntry.failureReason}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="caption" color="text.secondary">Failed At</Typography>
                  <Typography variant="body2">{new Date(displayEntry.failedAt).toLocaleString()}</Typography>
                </Grid>
                {displayEntry.exceptionId && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="text.secondary">Exception ID</Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                      {displayEntry.exceptionId}
                    </Typography>
                  </Grid>
                )}
              </Grid>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" sx={{ mb: 1 }}>Payload</Typography>
              <CodeViewer code={displayEntry.payload} maxHeight={300} collapsible defaultCollapsed />

              <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>Event Metadata</Typography>
              <CodeViewer code={displayEntry.eventMetadata} maxHeight={300} collapsible defaultCollapsed />

              <Divider sx={{ my: 3 }} />

              <Stack direction="row" spacing={2}>
                <Button
                  variant="contained"
                  startIcon={<RefreshIcon />}
                  onClick={handleRetry}
                  disabled={displayEntry.status === 'succeeded' || retryMutation.isPending}
                >
                  Retry
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<DeleteIcon />}
                  onClick={handleDiscard}
                  disabled={displayEntry.status === 'discarded' || discardMutation.isPending}
                >
                  Discard
                </Button>
              </Stack>
            </>
          ) : (
            <Alert severity="info">No entry selected.</Alert>
          )}
        </Box>
      </Drawer>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmDialogOpen}
        title={confirmAction === 'retry' ? 'Retry DLQ Entry' : 'Discard DLQ Entry'}
        message={
          confirmAction === 'retry'
            ? `Are you sure you want to retry this DLQ entry? It will be re-queued for processing.`
            : `Are you sure you want to discard this DLQ entry? This action cannot be undone.`
        }
        confirmLabel={confirmAction === 'retry' ? 'Retry' : 'Discard'}
        cancelLabel="Cancel"
        onConfirm={handleConfirm}
        onCancel={() => {
          setConfirmDialogOpen(false)
          setConfirmAction(null)
        }}
        loading={retryMutation.isPending || discardMutation.isPending}
        destructive={confirmAction === 'discard'}
      />
    </Box>
  )
}

