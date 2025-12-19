import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions, Chip } from '@mui/material'
import ToggleOnIcon from '@mui/icons-material/ToggleOn'
import ToggleOffIcon from '@mui/icons-material/ToggleOff'
import { useTenant } from '../../hooks/useTenant'
import { listPlaybooks, getPlaybook, activatePlaybook } from '../../api/admin'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import CodeViewer from '../../components/common/CodeViewer'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { OpsFilters } from '../../components/common/OpsFilterBar'
import type { Playbook } from '../../api/admin'
import { isAdminEnabled } from '../../utils/featureFlags'
import { formatDateTime } from '../../utils/dateFormat'

export default function PlaybooksPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [filters, setFilters] = useState<OpsFilters>({})
  const [selectedPlaybook, setSelectedPlaybook] = useState<Playbook | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [activateDialogOpen, setActivateDialogOpen] = useState(false)

  const isAdmin = isAdminEnabled()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['playbooks', tenantId, filters, page, pageSize],
    queryFn: () => listPlaybooks({
      tenantId: tenantId || undefined,
      domain: filters.domain,
      exceptionType: filters.eventType,
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
          title="Playbooks Management"
          subtitle="View and manage playbook configurations"
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

  const activateMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      activatePlaybook(id, tenantId || '', active),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
      setActivateDialogOpen(false)
      setDetailDialogOpen(false)
      setSelectedPlaybook(null)
    },
  })

  const handleViewDetail = async (playbook: Playbook) => {
    try {
      const detail = await getPlaybook(playbook.id)
      setSelectedPlaybook(detail)
      setDetailDialogOpen(true)
    } catch (error) {
      console.error('Failed to fetch playbook detail:', error)
    }
  }

  const handleToggleActive = () => {
    if (!selectedPlaybook) return
    setActivateDialogOpen(true)
  }

  const columns: DataTableColumn<Playbook>[] = [
    {
      id: 'name',
      label: 'Name',
      accessor: (row) => row.name,
    },
    {
      id: 'exceptionType',
      label: 'Exception Type',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.exceptionType}
        </Typography>
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain,
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row) => row.version,
    },
    {
      id: 'isActive',
      label: 'Status',
      accessor: (row) => (
        <Chip
          label={row.isActive ? 'Active' : 'Inactive'}
          size="small"
          color={row.isActive ? 'success' : 'default'}
        />
      ),
    },
    {
      id: 'createdAt',
      label: 'Created',
      accessor: (row) => formatDateTime(row.createdAt),
    },
    {
      id: 'actions',
      label: 'Actions',
      accessor: (row) => (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" onClick={() => handleViewDetail(row)}>
            View
          </Button>
          {isAdmin && (
            <Button
              size="small"
              color={row.isActive ? 'error' : 'success'}
              startIcon={row.isActive ? <ToggleOffIcon /> : <ToggleOnIcon />}
              onClick={() => {
                setSelectedPlaybook(row)
                handleToggleActive()
              }}
            >
              {row.isActive ? 'Deactivate' : 'Activate'}
            </Button>
          )}
        </Box>
      ),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view playbooks.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Playbooks Management"
        subtitle="View and manage playbook configurations"
      />
      
      <AdminWarningBanner />

      <OpsFilterBar
        value={filters}
        onChange={setFilters}
        showDomain={true}
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
        emptyMessage="No playbooks found."
      />

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false)
          setSelectedPlaybook(null)
        }}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          Playbook Details
          {selectedPlaybook?.isActive && (
            <Chip label="Active" size="small" color="success" sx={{ ml: 2 }} />
          )}
        </DialogTitle>
        <DialogContent>
          {selectedPlaybook && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Name: {selectedPlaybook.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Exception Type: {selectedPlaybook.exceptionType}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Domain: {selectedPlaybook.domain}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Version: {selectedPlaybook.version}
              </Typography>

              <Box sx={{ mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Match Rules
                </Typography>
                <CodeViewer
                  code={selectedPlaybook.matchRules}
                  title="Match Rules"
                  maxHeight={200}
                  collapsible
                />
              </Box>

              <Box sx={{ mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Steps
                </Typography>
                <CodeViewer
                  code={selectedPlaybook.steps}
                  title="Steps"
                  maxHeight={300}
                  collapsible
                />
              </Box>

              {selectedPlaybook.referencedTools.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Referenced Tools
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {selectedPlaybook.referencedTools.map((tool) => (
                      <Chip key={tool} label={tool} size="small" />
                    ))}
                  </Box>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {isAdmin && selectedPlaybook && (
            <Button
              variant="contained"
              color={selectedPlaybook.isActive ? 'error' : 'success'}
              startIcon={selectedPlaybook.isActive ? <ToggleOffIcon /> : <ToggleOnIcon />}
              onClick={handleToggleActive}
            >
              {selectedPlaybook.isActive ? 'Deactivate' : 'Activate'}
            </Button>
          )}
          <Button onClick={() => {
            setDetailDialogOpen(false)
            setSelectedPlaybook(null)
          }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Activate/Deactivate Confirm Dialog */}
      <ConfirmDialog
        open={activateDialogOpen}
        title={selectedPlaybook?.isActive ? 'Deactivate Playbook' : 'Activate Playbook'}
        message={`Are you sure you want to ${selectedPlaybook?.isActive ? 'deactivate' : 'activate'} the playbook "${selectedPlaybook?.name}"?`}
        confirmLabel={selectedPlaybook?.isActive ? 'Deactivate' : 'Activate'}
        cancelLabel="Cancel"
        onConfirm={() => {
          if (selectedPlaybook) {
            activateMutation.mutate({
              id: selectedPlaybook.id,
              active: !selectedPlaybook.isActive,
            })
          }
        }}
        onCancel={() => setActivateDialogOpen(false)}
        loading={activateMutation.isPending}
        destructive={selectedPlaybook?.isActive || false}
      />
    </Box>
  )
}

