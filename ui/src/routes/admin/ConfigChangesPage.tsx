import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions, TextField, Chip } from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import CancelIcon from '@mui/icons-material/Cancel'
import { useTenant } from '../../hooks/useTenant'
import { listConfigChanges, getConfigChange, getConfigChangeDiff, approveConfigChange, rejectConfigChange } from '../../api/admin'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import CodeViewer from '../../components/common/CodeViewer'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { OpsFilters } from '../../components/common/OpsFilterBar'
import type { ConfigChangeRequest } from '../../api/admin'
import { isAdminEnabled } from '../../utils/featureFlags'
import { formatDateTime } from '../../utils/dateFormat'

export default function ConfigChangesPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [filters, setFilters] = useState<OpsFilters>({})
  const [selectedChange, setSelectedChange] = useState<ConfigChangeRequest | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [approveDialogOpen, setApproveDialogOpen] = useState(false)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [rejectComment, setRejectComment] = useState('')
  const [diffData, setDiffData] = useState<any>(null)

  const isAdmin = isAdminEnabled()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['config-changes', tenantId, filters, page, pageSize],
    queryFn: () => listConfigChanges({
      tenantId: tenantId || undefined,
      status: filters.status as any,
      changeType: filters.eventType,
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: !!tenantId,
  })

  // Handle 401/403 errors
  if (isError && error && 'status' in error && (error.status === 401 || error.status === 403)) {
    return <NotAuthorizedPage />
  }

  // Handle 429 rate limit errors
  if (isError && error && 'status' in error && error.status === 429) {
    return (
      <Box>
        <PageHeader
          title="Config Change Governance"
          subtitle="Review and approve configuration change requests"
        />
        <Alert severity="warning" sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Rate Limit Exceeded
          </Typography>
          <Typography variant="body2">
            Too many requests. Please wait a minute before trying again.
          </Typography>
        </Alert>
      </Box>
    )
  }

  const approveMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) => 
      approveConfigChange(id, tenantId || '', comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-changes'] })
      setApproveDialogOpen(false)
      setDetailDialogOpen(false)
      setSelectedChange(null)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) => 
      rejectConfigChange(id, tenantId || '', comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config-changes'] })
      setRejectDialogOpen(false)
      setDetailDialogOpen(false)
      setSelectedChange(null)
      setRejectComment('')
    },
  })

  const handleViewDetail = async (change: ConfigChangeRequest) => {
    setSelectedChange(change)
    setDetailDialogOpen(true)
    
    // Fetch diff if available
    try {
      const diff = await getConfigChangeDiff(change.id, tenantId || '')
      setDiffData(diff)
    } catch (error) {
      console.error('Failed to fetch diff:', error)
    }
  }

  const handleApprove = () => {
    if (!selectedChange) return
    setApproveDialogOpen(true)
  }

  const handleReject = () => {
    if (!selectedChange) return
    setRejectDialogOpen(true)
  }

  const columns: DataTableColumn<ConfigChangeRequest>[] = [
    {
      id: 'changeType',
      label: 'Type',
      accessor: (row) => (
        <Chip
          label={row.changeType.replace(/_/g, ' ')}
          size="small"
          color="primary"
          variant="outlined"
        />
      ),
    },
    {
      id: 'resourceId',
      label: 'Resource',
      accessor: (row) => (
        <Box component="span" sx={{ fontFamily: 'monospace', fontSize: '0.8125rem', color: 'text.primary' }}>
          {row.resourceId}
        </Box>
      ),
    },
    {
      id: 'requestedBy',
      label: 'Requested By',
      accessor: (row) => row.requestedBy,
    },
    {
      id: 'requestedAt',
      label: 'Requested At',
      accessor: (row) => (
        <Box component="span" sx={{ color: 'text.secondary', fontSize: '0.8125rem' }}>
          {formatDateTime(row.requestedAt)}
        </Box>
      ),
    },
    {
      id: 'status',
      label: 'Status',
      accessor: (row) => (
        <Chip
          label={row.status}
          size="small"
          color={
            row.status === 'approved' ? 'success' :
            row.status === 'rejected' ? 'error' :
            row.status === 'pending' ? 'warning' : 'default'
          }
        />
      ),
    },
    {
      id: 'actions',
      label: 'Actions',
      accessor: (row) => (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" onClick={() => handleViewDetail(row)}>
            View
          </Button>
          {isAdmin && row.status === 'pending' && (
            <>
              <Button
                size="small"
                color="success"
                startIcon={<CheckCircleIcon />}
                onClick={() => {
                  setSelectedChange(row)
                  handleApprove()
                }}
              >
                Approve
              </Button>
              <Button
                size="small"
                color="error"
                startIcon={<CancelIcon />}
                onClick={() => {
                  setSelectedChange(row)
                  handleReject()
                }}
              >
                Reject
              </Button>
            </>
          )}
        </Box>
      ),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view config changes.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Config Change Governance"
        subtitle="Review and approve configuration change requests"
      />
      
      <AdminWarningBanner />

      {!isAdmin && (
        <Alert severity="info" sx={{ mb: 3 }}>
          View-only mode. Only administrators can approve or reject changes.
        </Alert>
      )}

      <OpsFilterBar
        value={filters}
        onChange={setFilters}
        showStatus={true}
        showEventType={true}
        syncWithUrl={true}
      />

      <DataTable
        columns={columns}
        rows={data?.items || []}
        loading={isLoading}
        page={page}
        pageSize={pageSize}
        totalCount={data?.total || 0}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        exportEnabled={true}
        emptyMessage="No configuration changes found."
      />

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false)
          setSelectedChange(null)
          setDiffData(null)
        }}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          Config Change Details
          {selectedChange && (
            <Chip
              label={selectedChange.status}
              size="small"
              color={
                selectedChange.status === 'approved' ? 'success' :
                selectedChange.status === 'rejected' ? 'error' :
                selectedChange.status === 'pending' ? 'warning' : 'default'
              }
              sx={{ ml: 2 }}
            />
          )}
        </DialogTitle>
        <DialogContent>
          {selectedChange && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Change Type: {selectedChange.changeType.replace(/_/g, ' ')}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Resource: {selectedChange.resourceId}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Requested by: {selectedChange.requestedBy} on {formatDateTime(selectedChange.requestedAt)}
              </Typography>
              
              {selectedChange.reviewComment && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  Review Comment: {selectedChange.reviewComment}
                </Alert>
              )}

              {diffData && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Configuration Diff
                  </Typography>
                  <CodeViewer
                    code={diffData}
                    title="Changes"
                    maxHeight={400}
                    collapsible
                  />
                </Box>
              )}

              <Box sx={{ mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Proposed Configuration
                </Typography>
                <CodeViewer
                  code={selectedChange.proposedConfig}
                  title="Proposed Config"
                  maxHeight={400}
                  collapsible
                />
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {isAdmin && selectedChange?.status === 'pending' && (
            <>
              <Button onClick={handleApprove} color="success" startIcon={<CheckCircleIcon />}>
                Approve
              </Button>
              <Button onClick={handleReject} color="error" startIcon={<CancelIcon />}>
                Reject
              </Button>
            </>
          )}
          <Button onClick={() => {
            setDetailDialogOpen(false)
            setSelectedChange(null)
            setDiffData(null)
          }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Approve Confirm Dialog */}
      <ConfirmDialog
        open={approveDialogOpen}
        title="Approve Configuration Change"
        message={`Are you sure you want to approve this ${selectedChange?.changeType.replace(/_/g, ' ')} change?`}
        confirmLabel="Approve"
        cancelLabel="Cancel"
        onConfirm={() => {
          if (selectedChange) {
            approveMutation.mutate({ id: selectedChange.id })
          }
        }}
        onCancel={() => setApproveDialogOpen(false)}
        loading={approveMutation.isPending}
        destructive={false}
      />

      {/* Reject Dialog */}
      <Dialog
        open={rejectDialogOpen}
        onClose={() => {
          setRejectDialogOpen(false)
          setRejectComment('')
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Reject Configuration Change</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Please provide a reason for rejecting this change:
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={4}
            value={rejectComment}
            onChange={(e) => setRejectComment(e.target.value)}
            placeholder="Enter rejection reason..."
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setRejectDialogOpen(false)
            setRejectComment('')
          }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => {
              if (selectedChange && rejectComment.trim()) {
                rejectMutation.mutate({ id: selectedChange.id, comment: rejectComment })
              }
            }}
            disabled={!rejectComment.trim() || rejectMutation.isPending}
          >
            Reject
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

