import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Chip,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import { useTenant } from '../../hooks/useTenant'
import {
  listTenants,
  createTenant,
  updateTenantStatus,
  getActiveConfig,
  type Tenant,
  type TenantCreateRequest,
  type TenantStatusUpdateRequest,
  type ActiveConfigResponse,
} from '../../api/onboarding'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import CodeViewer from '../../components/common/CodeViewer'
import FilterBar from '../../components/common/FilterBar'
import type { DataTableColumn } from '../../components/common/DataTable'
import { isAdminEnabled } from '../../utils/featureFlags'
import { formatDateTime } from '../../utils/dateFormat'
import { useSnackbar } from '../../components/common/SnackbarProvider'
import RecentChangesPanel from '../../components/admin/RecentChangesPanel'

export default function TenantsPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [statusFilter, setStatusFilter] = useState<'ACTIVE' | 'SUSPENDED' | ''>('')
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [statusDialogOpen, setStatusDialogOpen] = useState(false)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null)
  const [activeConfig, setActiveConfig] = useState<ActiveConfigResponse | null>(null)
  const [newTenant, setNewTenant] = useState<TenantCreateRequest>({
    tenant_id: '',
    name: '',
  })
  const [tenantIdError, setTenantIdError] = useState<string>('')

  const isAdmin = isAdminEnabled()

  // Validate tenant ID format: uppercase, alphanumeric and underscores only
  const validateTenantId = (value: string): string => {
    if (!value.trim()) {
      return 'Tenant ID is required'
    }
    // Check if contains lowercase letters
    if (value !== value.toUpperCase()) {
      return 'Tenant ID must be uppercase'
    }
    // Check format: alphanumeric, underscores, and hyphens allowed
    if (!/^[A-Z0-9_\-]+$/.test(value)) {
      return 'Tenant ID must contain only uppercase letters, numbers, underscores, and hyphens'
    }
    return ''
  }

  const handleTenantIdChange = (value: string) => {
    const upperValue = value.toUpperCase()
    setNewTenant({ ...newTenant, tenant_id: upperValue })
    setTenantIdError(validateTenantId(upperValue))
  }

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['tenants', page, pageSize, statusFilter],
    queryFn: () =>
      listTenants({
        page: page + 1, // API uses 1-based pagination
        page_size: pageSize,
        status: statusFilter || undefined,
      }),
    enabled: isAdmin,
  })

  // Handle 401/403 errors
  if (isError && error && 'status' in error && (error.status === 401 || error.status === 403)) {
    return <NotAuthorizedPage />
  }

  const createMutation = useMutation({
    mutationFn: (request: TenantCreateRequest) => createTenant(request),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      setCreateDialogOpen(false)
      setNewTenant({ tenant_id: '', name: '' })
      setTenantIdError('')
      showSuccess(`Tenant ${data.tenant_id} created successfully`)
    },
    onError: (error: Error & { status?: number; details?: unknown }) => {
      // Handle duplicate tenant ID error
      if (error.status === 400 || error.message.includes('already exists') || error.message.includes('duplicate')) {
        showError(`Tenant ID ${newTenant.tenant_id} already exists. Please use a different ID.`)
      } else if (error.status === 403) {
        showError('You are not authorized to create tenants')
      } else {
        const errorMessage = error.message || 'Failed to create tenant'
        showError(errorMessage)
      }
    },
  })

  const statusMutation = useMutation({
    mutationFn: ({ tenantId, status }: { tenantId: string; status: 'ACTIVE' | 'SUSPENDED' }) =>
      updateTenantStatus(tenantId, { status }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      setStatusDialogOpen(false)
      const statusText = data.status === 'ACTIVE' ? 'activated' : 'suspended'
      showSuccess(`Tenant ${data.tenant_id} ${statusText} successfully`)
      setSelectedTenant(null)
    },
    onError: (error: Error & { status?: number }) => {
      if (error.status === 403) {
        showError('You are not authorized to update tenant status')
      } else {
        showError(error.message || 'Failed to update tenant status')
      }
    },
  })

  const handleCreateTenant = () => {
    // Validate tenant ID format
    const error = validateTenantId(newTenant.tenant_id)
    if (error) {
      setTenantIdError(error)
      return
    }
    if (!newTenant.tenant_id.trim() || !newTenant.name.trim()) {
      return
    }
    createMutation.mutate(newTenant)
  }

  const handleStatusUpdate = (tenant: Tenant, newStatus: 'ACTIVE' | 'SUSPENDED') => {
    setSelectedTenant(tenant)
    setStatusDialogOpen(true)
    // Store the new status in a ref or state
    ;(setSelectedTenant as any).pendingStatus = newStatus
  }

  const handleViewDetail = async (tenant: Tenant) => {
    setSelectedTenant(tenant)
    const config = await getActiveConfig(tenant.tenant_id)
    setActiveConfig(config)
    setDetailDialogOpen(true)
  }

  const columns: DataTableColumn<Tenant>[] = [
    {
      id: 'tenant_id',
      label: 'Tenant ID',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
          {row.tenant_id}
        </Typography>
      ),
    },
    {
      id: 'name',
      label: 'Name',
      accessor: (row) => row.name,
    },
    {
      id: 'status',
      label: 'Status',
      accessor: (row) => (
        <Chip
          label={row.status.toUpperCase()}
          size="small"
          color={row.status.toUpperCase() === 'ACTIVE' ? 'success' : 'default'}
        />
      ),
    },
    {
      id: 'created_at',
      label: 'Created At',
      accessor: (row) => formatDateTime(row.created_at),
    },
    {
      id: 'created_by',
      label: 'Created By',
      accessor: (row) => row.created_by || '-',
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
              color={row.status.toUpperCase() === 'ACTIVE' ? 'warning' : 'primary'}
              onClick={() =>
                handleStatusUpdate(row, row.status.toUpperCase() === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE')
              }
            >
              {row.status.toUpperCase() === 'ACTIVE' ? 'Suspend' : 'Enable'}
            </Button>
          )}
        </Box>
      ),
    },
  ]

  if (!isAdmin) {
    return <NotAuthorizedPage />
  }

  return (
    <Box>
      <PageHeader
        title="Tenants Management"
        subtitle="Create and manage tenants"
        actions={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateDialogOpen(true)}
          >
            Create Tenant
          </Button>
        }
      />

      <AdminWarningBanner />

      {/* Status Filter */}
      <Box sx={{ mb: 3 }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value as 'ACTIVE' | 'SUSPENDED' | '')}
          >
            <MenuItem value="">
              <em>All</em>
            </MenuItem>
            <MenuItem value="ACTIVE">ACTIVE</MenuItem>
            <MenuItem value="SUSPENDED">SUSPENDED</MenuItem>
          </Select>
        </FormControl>
      </Box>

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
        emptyMessage="No tenants found."
      />

      {/* Create Tenant Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Tenant</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
            <TextField
              label="Tenant ID"
              value={newTenant.tenant_id}
              onChange={(e) => handleTenantIdChange(e.target.value)}
              required
              fullWidth
              error={!!tenantIdError}
              helperText={tenantIdError || 'Unique identifier for the tenant (e.g., TENANT_FINANCE_001). Must be uppercase.'}
              disabled={createMutation.isPending}
            />
            <TextField
              label="Name"
              value={newTenant.name}
              onChange={(e) => setNewTenant({ ...newTenant, name: e.target.value })}
              required
              fullWidth
              helperText="Display name for the tenant"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateTenant}
            disabled={!newTenant.tenant_id.trim() || !newTenant.name.trim() || !!tenantIdError || createMutation.isPending}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Status Update Confirm Dialog */}
      <ConfirmDialog
        open={statusDialogOpen}
        title={`${selectedTenant?.status.toUpperCase() === 'ACTIVE' ? 'Suspend' : 'Enable'} Tenant`}
        message={`Are you sure you want to ${
          selectedTenant?.status.toUpperCase() === 'ACTIVE' ? 'suspend' : 'enable'
        } tenant ${selectedTenant?.tenant_id}?`}
        confirmLabel={selectedTenant?.status.toUpperCase() === 'ACTIVE' ? 'Suspend' : 'Enable'}
        cancelLabel="Cancel"
        onConfirm={() => {
          if (selectedTenant) {
            const newStatus = selectedTenant.status.toUpperCase() === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE'
            statusMutation.mutate({ tenantId: selectedTenant.tenant_id, status: newStatus })
          }
        }}
        onCancel={() => {
          setStatusDialogOpen(false)
          setSelectedTenant(null)
        }}
        loading={statusMutation.isPending}
        destructive={selectedTenant?.status.toUpperCase() === 'ACTIVE'}
      />

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false)
          setSelectedTenant(null)
          setActiveConfig(null)
        }}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          Tenant Details: {selectedTenant?.tenant_id}
          {selectedTenant && (
            <Chip
              label={selectedTenant.status.toUpperCase()}
              size="small"
              color={selectedTenant.status.toUpperCase() === 'ACTIVE' ? 'success' : 'default'}
              sx={{ ml: 2 }}
            />
          )}
        </DialogTitle>
        <DialogContent>
          {selectedTenant && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Name: {selectedTenant.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Status: {selectedTenant.status}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Created: {formatDateTime(selectedTenant.created_at)}
              </Typography>
              {selectedTenant.created_by && (
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Created By: {selectedTenant.created_by}
                </Typography>
              )}

              {activeConfig && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="h6" gutterBottom>
                    Active Configuration
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Domain Pack Version: {activeConfig.active_domain_pack_version || 'None'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Tenant Pack Version: {activeConfig.active_tenant_pack_version || 'None'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Activated At: {formatDateTime(activeConfig.activated_at)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Activated By: {activeConfig.activated_by}
                  </Typography>
                </Box>
              )}

              {!activeConfig && (
                <Box sx={{ mt: 3 }}>
                  <Alert severity="info">No active configuration found for this tenant.</Alert>
                </Box>
              )}

              {/* Recent Changes Panel */}
              <Box sx={{ mt: 3 }}>
                <RecentChangesPanel
                  entityType="tenant"
                  entityId={selectedTenant.tenant_id}
                  tenantId={selectedTenant.tenant_id}
                  title="Recent Changes"
                  limit={5}
                />
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setDetailDialogOpen(false)
              setSelectedTenant(null)
              setActiveConfig(null)
            }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

