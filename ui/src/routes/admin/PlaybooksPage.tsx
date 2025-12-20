import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions, Chip } from '@mui/material'
import ToggleOnIcon from '@mui/icons-material/ToggleOn'
import ToggleOffIcon from '@mui/icons-material/ToggleOff'
import LinkIcon from '@mui/icons-material/Link'
import WarningIcon from '@mui/icons-material/Warning'
import { useTenant } from '../../hooks/useTenant'
import { listPlaybooks, getPlaybook, activatePlaybook } from '../../api/admin'
import { getActiveConfig, type ActiveConfigResponse } from '../../api/onboarding'
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
  const [activeConfig, setActiveConfig] = useState<ActiveConfigResponse | null>(null)
  const [compatibilityWarning, setCompatibilityWarning] = useState<string | null>(null)

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
      
      // Fetch active config for the tenant to show linked pack information
      if (tenantId) {
        const config = await getActiveConfig(tenantId)
        setActiveConfig(config)
        
        // Check compatibility: playbook domain should match active domain pack domain
        if (config && config.active_domain_pack_version && detail.domain) {
          // In a real implementation, we'd check if the domain pack version matches the playbook's domain
          // For now, we'll just show a warning if there's a mismatch
          setCompatibilityWarning(null) // No warning by default - would need backend validation
        } else {
          setCompatibilityWarning('No active domain pack configured for this tenant')
        }
      }
      
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
      id: 'linkedPack',
      label: 'Linked Pack',
      accessor: (row) => {
        // This would show linked pack info if available
        // For now, we'll show it in the detail view
        return <Chip label="View Details" size="small" variant="outlined" />
      },
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
          setActiveConfig(null)
          setCompatibilityWarning(null)
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

              {/* Pack Linking Information */}
              <Box sx={{ mt: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LinkIcon fontSize="small" />
                  Linked Pack Information
                </Typography>
                {activeConfig ? (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      <strong>Tenant:</strong> {activeConfig.tenant_id}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      <strong>Active Domain Pack:</strong> {activeConfig.active_domain_pack_version || 'None'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      <strong>Active Tenant Pack:</strong> {activeConfig.active_tenant_pack_version || 'None'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      <strong>Playbook Domain:</strong> {selectedPlaybook.domain}
                    </Typography>
                    {compatibilityWarning && (
                      <Alert severity="warning" sx={{ mt: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <WarningIcon fontSize="small" />
                          <Typography variant="body2">{compatibilityWarning}</Typography>
                        </Box>
                      </Alert>
                    )}
                    {!compatibilityWarning && activeConfig.active_domain_pack_version && (
                      <Alert severity="success" sx={{ mt: 2 }}>
                        Playbook is compatible with active pack configuration
                      </Alert>
                    )}
                  </Box>
                ) : (
                  <Alert severity="info" sx={{ mt: 1 }}>
                    No active configuration found for this tenant. Playbook may not be usable until packs are activated.
                  </Alert>
                )}
              </Box>
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
            setActiveConfig(null)
            setCompatibilityWarning(null)
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
            // Prevent activation if compatibility warning exists
            if (compatibilityWarning && !selectedPlaybook.isActive) {
              alert('Cannot activate playbook: ' + compatibilityWarning)
              return
            }
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

