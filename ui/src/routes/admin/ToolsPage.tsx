import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions, Chip, Link } from '@mui/material'
import ToggleOnIcon from '@mui/icons-material/ToggleOn'
import ToggleOffIcon from '@mui/icons-material/ToggleOff'
import { Link as RouterLink } from 'react-router-dom'
import { useTenant } from '../../hooks/useTenant'
import { listTools, getTool, enableToolForTenant } from '../../api/admin'
import { PageShell, Card, DataCard } from '../../components/ui'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import CodeViewer from '../../components/common/CodeViewer'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { OpsFilters } from '../../components/common/OpsFilterBar'
import type { Tool } from '../../api/admin'
import { isAdminEnabled } from '../../utils/featureFlags'

export default function ToolsPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [filters, setFilters] = useState<OpsFilters>({})
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [enableDialogOpen, setEnableDialogOpen] = useState(false)

  const isAdmin = isAdminEnabled()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['tools', tenantId, filters, page, pageSize],
    queryFn: () => listTools({
      tenantId: tenantId || undefined,
      enabled: filters.status === 'enabled' ? true : filters.status === 'disabled' ? false : undefined,
      provider: filters.domain, // Reuse domain filter for provider
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
      <PageShell>
        <PageHeader
          title="Tools Management"
          subtitle="View and manage tool registry and tenant enablement"
        />
        <Alert severity="warning" sx={{ mt: 3 }}>
          <Typography variant="h6" gutterBottom>
            Rate Limit Exceeded
          </Typography>
          <Typography variant="body2">
            Too many requests. Please wait a minute before trying again.
          </Typography>
        </Alert>
      </PageShell>
    )
  }

  const enableMutation = useMutation({
    mutationFn: ({ toolId, enabled }: { toolId: string; enabled: boolean }) =>
      enableToolForTenant(toolId, tenantId || '', enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tools'] })
      setEnableDialogOpen(false)
      setDetailDialogOpen(false)
      setSelectedTool(null)
    },
  })

  const handleViewDetail = async (tool: Tool) => {
    try {
      const detail = await getTool(tool.id)
      setSelectedTool(detail)
      setDetailDialogOpen(true)
    } catch (error) {
      console.error('Failed to fetch tool detail:', error)
    }
  }

  const handleToggleEnable = () => {
    if (!selectedTool) return
    setEnableDialogOpen(true)
  }

  const columns: DataTableColumn<Tool>[] = [
    {
      id: 'name',
      label: 'Name',
      accessor: (row) => (
        <Link
          component={RouterLink}
          to={`/tools/${row.id}`}
          sx={{ textDecoration: 'none' }}
        >
          {row.name}
        </Link>
      ),
    },
    {
      id: 'description',
      label: 'Description',
      accessor: (row) => (
        <Typography
          variant="body2"
          sx={{
            maxWidth: 300,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={row.description}
        >
          {row.description}
        </Typography>
      ),
    },
    {
      id: 'provider',
      label: 'Provider',
      accessor: (row) => row.provider,
    },
    {
      id: 'enabledForTenant',
      label: 'Enabled',
      accessor: (row) => (
        <Chip
          label={row.enabledForTenant ? 'Yes' : 'No'}
          size="small"
          color={row.enabledForTenant ? 'success' : 'default'}
        />
      ),
    },
    {
      id: 'allowedTenants',
      label: 'Allowed Tenants',
      accessor: (row) => (
        <Typography variant="body2" color="text.secondary">
          {row.allowedTenants.length > 0 ? `${row.allowedTenants.length} tenant(s)` : 'All'}
        </Typography>
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
          {isAdmin && (
            <Button
              size="small"
              color={row.enabledForTenant ? 'error' : 'success'}
              startIcon={row.enabledForTenant ? <ToggleOffIcon /> : <ToggleOnIcon />}
              onClick={() => {
                setSelectedTool(row)
                handleToggleEnable()
              }}
            >
              {row.enabledForTenant ? 'Disable' : 'Enable'}
            </Button>
          )}
        </Box>
      ),
    },
  ]

  if (!tenantId) {
    return (
      <PageShell>
        <Alert severity="warning">Please select a tenant to view tools.</Alert>
      </PageShell>
    )
  }

  return (
    <PageShell>
      <PageHeader
        title="Tools Management"
        subtitle="View and manage tool registry and tenant enablement"
      />
      
      <AdminWarningBanner />

      <Card sx={{ mb: 3 }}>
        <OpsFilterBar
          value={filters}
          onChange={setFilters}
          showStatus={true}
          showDomain={true}
          syncWithUrl={true}
        />
      </Card>

      <DataCard title="Tool Registry" subtitle={data?.total ? `${data.total} tools` : undefined}>
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
          emptyMessage="No tools found."
        />
      </DataCard>

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false)
          setSelectedTool(null)
        }}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          Tool Details
          {selectedTool?.enabledForTenant && (
            <Chip label="Enabled" size="small" color="success" sx={{ ml: 2 }} />
          )}
        </DialogTitle>
        <DialogContent>
          {selectedTool && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Name: {selectedTool.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Provider: {selectedTool.provider}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Description: {selectedTool.description}
              </Typography>

              {selectedTool.allowedTenants.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Allowed Tenants
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {selectedTool.allowedTenants.map((tenant) => (
                      <Chip key={tenant} label={tenant} size="small" />
                    ))}
                  </Box>
                </Box>
              )}

              <Box sx={{ mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Schema
                </Typography>
                <CodeViewer
                  code={selectedTool.schema}
                  title="Tool Schema"
                  maxHeight={400}
                  collapsible
                />
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {isAdmin && selectedTool && (
            <Button
              variant="contained"
              color={selectedTool.enabledForTenant ? 'error' : 'success'}
              startIcon={selectedTool.enabledForTenant ? <ToggleOffIcon /> : <ToggleOnIcon />}
              onClick={handleToggleEnable}
            >
              {selectedTool.enabledForTenant ? 'Disable for Tenant' : 'Enable for Tenant'}
            </Button>
          )}
          <Button onClick={() => {
            setDetailDialogOpen(false)
            setSelectedTool(null)
          }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Enable/Disable Confirm Dialog */}
      <ConfirmDialog
        open={enableDialogOpen}
        title={selectedTool?.enabledForTenant ? 'Disable Tool for Tenant' : 'Enable Tool for Tenant'}
        message={`Are you sure you want to ${selectedTool?.enabledForTenant ? 'disable' : 'enable'} the tool "${selectedTool?.name}" for this tenant?`}
        confirmLabel={selectedTool?.enabledForTenant ? 'Disable' : 'Enable'}
        cancelLabel="Cancel"
        onConfirm={() => {
          if (selectedTool) {
            enableMutation.mutate({
              toolId: selectedTool.id,
              enabled: !selectedTool.enabledForTenant,
            })
          }
        }}
        onCancel={() => setEnableDialogOpen(false)}
        loading={enableMutation.isPending}
        destructive={selectedTool?.enabledForTenant || false}
      />
    </PageShell>
  )
}

