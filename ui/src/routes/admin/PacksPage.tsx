import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Box, Typography, Tabs, Tab, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions, Button, Chip } from '@mui/material'
import { useTenant } from '../../hooks/useTenant'
import { listDomainPacks, listTenantPacks, getDomainPack, getTenantPack, activatePackVersion } from '../../api/admin'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import CodeViewer from '../../components/common/CodeViewer'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { OpsFilters } from '../../components/common/OpsFilterBar'
import type { DomainPack, TenantPack } from '../../api/admin'
import { isAdminEnabled } from '../../utils/featureFlags'
import { formatDateTime } from '../../utils/dateFormat'

type PackType = 'domain' | 'tenant'

export default function PacksPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<PackType>('domain')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [filters, setFilters] = useState<OpsFilters>({})
  const [selectedPack, setSelectedPack] = useState<DomainPack | TenantPack | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [activateDialogOpen, setActivateDialogOpen] = useState(false)

  const isAdmin = isAdminEnabled()

  const { data: domainPacksData, isLoading: domainPacksLoading, isError: domainPacksError, error: domainPacksErrorObj } = useQuery({
    queryKey: ['domain-packs', tenantId, filters, page, pageSize],
    queryFn: () => listDomainPacks({
      tenantId: tenantId || undefined,
      domain: filters.domain,
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: tab === 'domain' && !!tenantId,
  })

  const { data: tenantPacksData, isLoading: tenantPacksLoading, isError: tenantPacksError, error: tenantPacksErrorObj } = useQuery({
    queryKey: ['tenant-packs', tenantId, filters, page, pageSize],
    queryFn: () => listTenantPacks({
      tenantId: tenantId || undefined,
      domain: filters.domain,
      limit: pageSize,
      offset: page * pageSize,
    }),
    enabled: tab === 'tenant' && !!tenantId,
  })

  // Handle 401/403 errors
  const currentError = tab === 'domain' ? domainPacksErrorObj : tenantPacksErrorObj
  if ((tab === 'domain' ? domainPacksError : tenantPacksError) && currentError && 'status' in currentError && (currentError.status === 401 || currentError.status === 403)) {
    return <NotAuthorizedPage />
  }

  // Handle 429 rate limit errors
  if ((tab === 'domain' ? domainPacksError : tenantPacksError) && currentError && 'status' in currentError && currentError.status === 429) {
    return (
      <Box>
        <PageHeader
          title="Packs Management"
          subtitle="View and manage Domain Packs and Tenant Policy Packs"
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
    mutationFn: ({ packType, packId, version }: { packType: PackType; packId: string; version: string }) =>
      activatePackVersion(packType, packId, version, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [tab === 'domain' ? 'domain-packs' : 'tenant-packs'] })
      setActivateDialogOpen(false)
      setDetailDialogOpen(false)
      setSelectedPack(null)
    },
  })

  const handleViewDetail = async (pack: DomainPack | TenantPack) => {
    try {
      const detail = tab === 'domain'
        ? await getDomainPack(pack.id)
        : await getTenantPack(pack.id)
      setSelectedPack(detail)
      setDetailDialogOpen(true)
    } catch (error) {
      console.error('Failed to fetch pack detail:', error)
    }
  }

  const handleActivate = () => {
    if (!selectedPack) return
    setActivateDialogOpen(true)
  }

  const domainColumns: DataTableColumn<DomainPack>[] = [
    {
      id: 'name',
      label: 'Name',
      accessor: (row) => row.name,
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2">{row.version}</Typography>
          {row.isActive && (
            <Chip label="Active" size="small" color="success" />
          )}
        </Box>
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain,
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
              color="primary"
              onClick={() => {
                setSelectedPack(row)
                handleActivate()
              }}
              disabled={row.isActive}
            >
              Activate
            </Button>
          )}
        </Box>
      ),
    },
  ]

  const tenantColumns: DataTableColumn<TenantPack>[] = [
    {
      id: 'name',
      label: 'Name',
      accessor: (row) => row.name,
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2">{row.version}</Typography>
          {row.isActive && (
            <Chip label="Active" size="small" color="success" />
          )}
        </Box>
      ),
    },
    {
      id: 'tenantId',
      label: 'Tenant',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.tenantId}
        </Typography>
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain,
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
              color="primary"
              onClick={() => {
                setSelectedPack(row)
                handleActivate()
              }}
              disabled={row.isActive}
            >
              Activate
            </Button>
          )}
        </Box>
      ),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view packs.</Alert>
      </Box>
    )
  }

  const currentData = tab === 'domain' ? domainPacksData : tenantPacksData
  const isLoading = tab === 'domain' ? domainPacksLoading : tenantPacksLoading
  const columns = tab === 'domain' ? domainColumns : tenantColumns

  return (
    <Box>
      <PageHeader
        title="Packs Management"
        subtitle="View and manage Domain Packs and Tenant Policy Packs"
      />
      
      <AdminWarningBanner />

      <Tabs value={tab} onChange={(_, newValue) => {
        setTab(newValue)
        setPage(0)
      }} sx={{ mb: 3 }}>
        <Tab label="Domain Packs" value="domain" />
        <Tab label="Tenant Packs" value="tenant" />
      </Tabs>

      <OpsFilterBar
        value={filters}
        onChange={setFilters}
        showDomain={true}
        syncWithUrl={true}
      />

      <DataTable
        columns={columns}
        rows={currentData?.items || []}
        loading={isLoading}
        page={page}
        pageSize={pageSize}
        totalCount={currentData?.total || 0}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
        exportEnabled={true}
        emptyMessage={`No ${tab === 'domain' ? 'domain' : 'tenant'} packs found.`}
      />

      {/* Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false)
          setSelectedPack(null)
        }}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          {tab === 'domain' ? 'Domain Pack' : 'Tenant Pack'} Details
          {selectedPack?.isActive && (
            <Chip label="Active" size="small" color="success" sx={{ ml: 2 }} />
          )}
        </DialogTitle>
        <DialogContent>
          {selectedPack && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Name: {selectedPack.name}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Version: {selectedPack.version}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Created: {formatDateTime(selectedPack.createdAt)}
              </Typography>

              <Box sx={{ mt: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Configuration
                </Typography>
                <CodeViewer
                  code={selectedPack.config}
                  title="Pack Configuration"
                  maxHeight={500}
                  collapsible
                />
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          {isAdmin && selectedPack && !selectedPack.isActive && (
            <Button
              variant="contained"
              onClick={handleActivate}
            >
              Activate Version
            </Button>
          )}
          <Button onClick={() => {
            setDetailDialogOpen(false)
            setSelectedPack(null)
          }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Activate Confirm Dialog */}
      <ConfirmDialog
        open={activateDialogOpen}
        title="Activate Pack Version"
        message={`Are you sure you want to activate version ${selectedPack?.version} of ${selectedPack?.name}?`}
        confirmLabel="Activate"
        cancelLabel="Cancel"
        onConfirm={() => {
          if (selectedPack) {
            activateMutation.mutate({
              packType: tab,
              packId: selectedPack.id,
              version: selectedPack.version,
            })
          }
        }}
        onCancel={() => setActivateDialogOpen(false)}
        loading={activateMutation.isPending}
        destructive={false}
      />
    </Box>
  )
}

