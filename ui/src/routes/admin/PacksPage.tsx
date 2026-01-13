import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Chip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
} from '@mui/material'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import AddIcon from '@mui/icons-material/Add'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import { useTenant } from '../../hooks/useTenant'
import {
  listDomainPacks,
  listTenantPacks,
  getDomainPack,
  getTenantPack,
  getTenant,
  importDomainPack,
  importTenantPack,
  validatePack,
  activatePacks,
  getActiveConfig,
  type Pack,
  type PackImportRequest,
  type PackValidationResponse,
  type PackActivateRequest,
} from '../../api/onboarding'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import OpsFilterBar from '../../components/common/OpsFilterBar'
import PackContentViewer from '../../components/admin/PackContentViewer'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { OpsFilters } from '../../components/common/OpsFilterBar'
import { isAdminEnabled } from '../../utils/featureFlags'
import { formatDateTime } from '../../utils/dateFormat'
import { useSnackbar } from '../../components/common/SnackbarProvider'

type PackType = 'domain' | 'tenant'

// Map tenant industry to domain pack name
const INDUSTRY_TO_DOMAIN: Record<string, string> = {
  finance: 'CapitalMarketsTrading',
  healthcare: 'HealthcareClaimsAndCareOps',
  insurance: 'InsuranceClaimsProcessing',
  retail: 'RetailOperations',
  saas_ops: 'SaaSOperations',
}

export default function PacksPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [tab, setTab] = useState<PackType>('domain')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [filters, setFilters] = useState<OpsFilters>({})
  const [statusFilter, setStatusFilter] = useState<'DRAFT' | 'ACTIVE' | 'DEPRECATED' | ''>('')
  const [selectedPack, setSelectedPack] = useState<Pack | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [activateDialogOpen, setActivateDialogOpen] = useState(false)
  const [importDialogOpen, setImportDialogOpen] = useState(false)
  const [validateDialogOpen, setValidateDialogOpen] = useState(false)
  const [validatePackDialogOpen, setValidatePackDialogOpen] = useState(false)
  const [packToValidate, setPackToValidate] = useState<Pack | null>(null)
  const [importData, setImportData] = useState<{
    domain?: string
    tenant_id?: string
    version: string
    content: string
  }>({
    version: '',
    content: '',
  })
  const [validationResult, setValidationResult] = useState<PackValidationResponse | null>(null)
  const [activeConfigs, setActiveConfigs] = useState<Record<string, { domain?: string; tenant?: string }>>({})

  const isAdmin = isAdminEnabled()

  // Fetch current tenant info to get industry for filtering domain packs
  const { data: tenantInfo } = useQuery({
    queryKey: ['tenant-info', tenantId],
    queryFn: () => tenantId ? getTenant(tenantId) : null,
    enabled: !!tenantId,
  })

  // Get the domain name for the current tenant's industry
  const tenantDomain = tenantInfo?.industry 
    ? INDUSTRY_TO_DOMAIN[tenantInfo.industry.toLowerCase()] 
    : undefined

  const { data: domainPacksData, isLoading: domainPacksLoading, isError: domainPacksError, error: domainPacksErrorObj } = useQuery({
    queryKey: ['domain-packs', tenantDomain, filters.domain, statusFilter, page, pageSize],
    queryFn: () =>
      listDomainPacks({
        // Filter by tenant's industry domain if available, otherwise use filter
        domain: tenantDomain || filters.domain,
        status: statusFilter || undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    enabled: tab === 'domain',
  })

  const { data: tenantPacksData, isLoading: tenantPacksLoading, isError: tenantPacksError, error: tenantPacksErrorObj } = useQuery({
    queryKey: ['tenant-packs', tenantId, statusFilter, page, pageSize],
    queryFn: () =>
      listTenantPacks({
        tenant_id: tenantId || '',
        status: statusFilter || undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    enabled: tab === 'tenant' && !!tenantId,
  })

  // Fetch active configs for all tenants (for domain packs) or current tenant (for tenant packs)
  useQuery({
    queryKey: ['active-configs', tenantId],
    queryFn: async () => {
      if (tab === 'tenant' && tenantId) {
        const config = await getActiveConfig(tenantId)
        if (config) {
          setActiveConfigs({ [tenantId]: { tenant: config.active_tenant_pack_version } })
        } else {
          // No active config - clear any existing config for this tenant
          setActiveConfigs({ [tenantId]: {} })
        }
      }
      return {}
    },
    enabled: tab === 'tenant' && !!tenantId,
  })

  // Handle 401/403 errors
  const currentError = tab === 'domain' ? domainPacksErrorObj : tenantPacksErrorObj
  if ((tab === 'domain' ? domainPacksError : tenantPacksError) && currentError && 'status' in currentError && (currentError.status === 401 || currentError.status === 403)) {
    return <NotAuthorizedPage />
  }

  const importMutation = useMutation({
    mutationFn: (request: PackImportRequest) =>
      tab === 'domain' ? importDomainPack(request) : importTenantPack(request),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [tab === 'domain' ? 'domain-packs' : 'tenant-packs'] })
      setImportDialogOpen(false)
      setImportData({ version: '', content: '' })
      const packType = tab === 'domain' ? 'Domain pack' : 'Tenant pack'
      showSuccess(`${packType} ${data.domain || data.tenant_id} v${data.version} imported successfully`)
    },
    onError: (error: Error & { status?: number; details?: unknown }) => {
      let errorMessage = error.message || 'Failed to import pack'
      
      // Handle duplicate pack error with clearer message
      if (errorMessage.includes('already exists')) {
        const match = errorMessage.match(/domain=([^,]+), version=([^\s)]+)/)
        if (match) {
          const [, domain, version] = match
          errorMessage = `Domain pack already exists: ${domain} version ${version}. Please use a different version number or domain name.`
        }
      }
      
      showError(errorMessage)
    },
  })

  const validateMutation = useMutation({
    mutationFn: (content: Record<string, unknown>) =>
      validatePack({
        pack_type: tab,
        content,
        domain: tab === 'tenant' ? filters.domain : undefined,
      }),
    onSuccess: (result) => {
      setValidationResult(result)
      if (result.is_valid) {
        showSuccess('Pack validation passed')
      } else {
        showError(`Pack validation failed: ${result.errors.length} error(s) found`)
      }
    },
    onError: (error: Error) => {
      showError(error.message || 'Failed to validate pack')
    },
  })

  const validatePackMutation = useMutation({
    mutationFn: async (pack: Pack) => {
      // Fetch full pack content if not already available
      let packContent: Record<string, unknown>
      if (pack.content_json) {
        packContent = pack.content_json
      } else {
        const fullPack =
          tab === 'domain' && pack.domain
            ? await getDomainPack(pack.domain, pack.version)
            : tab === 'tenant' && pack.tenant_id
            ? await getTenantPack(pack.tenant_id, pack.version)
            : pack
        if (!fullPack.content_json) {
          throw new Error('Pack content not available')
        }
        packContent = fullPack.content_json
      }
      return validatePack({
        pack_type: tab,
        content: packContent,
        domain: tab === 'tenant' ? filters.domain : pack.domain,
      })
    },
    onSuccess: (result) => {
      setValidationResult(result)
      if (result.is_valid) {
        showSuccess(`Pack ${packToValidate?.domain || packToValidate?.tenant_id} v${packToValidate?.version} validation passed`)
      } else {
        showError(`Pack validation failed: ${result.errors.length} error(s) found`)
      }
    },
    onError: (error: Error) => {
      showError(error.message || 'Failed to validate pack')
    },
  })

  const activateMutation = useMutation({
    mutationFn: (request: PackActivateRequest) => activatePacks(request),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [tab === 'domain' ? 'domain-packs' : 'tenant-packs'] })
      queryClient.invalidateQueries({ queryKey: ['active-configs'] })
      setActivateDialogOpen(false)
      setDetailDialogOpen(false)
      setSelectedPack(null)
      showSuccess(`Pack activated successfully for tenant ${data.tenant_id}`)
    },
    onError: (error: Error) => {
      showError(error.message || 'Failed to activate pack')
    },
  })

  const handleImport = () => {
    try {
      const content = JSON.parse(importData.content)
      
      // For domain packs, verify domain matches between form and JSON
      if (tab === 'domain') {
        const jsonDomain = content.domainName || content.domain
        if (jsonDomain && importData.domain && jsonDomain !== importData.domain) {
          showError(`Domain mismatch: Form has "${importData.domain}" but JSON has "${jsonDomain}". Please use the domain from the JSON or update the form.`)
          return
        }
        // If domain not in form but exists in JSON, use JSON domain
        if (!importData.domain && jsonDomain) {
          setImportData({ ...importData, domain: jsonDomain })
        }
      }
      
      const request: PackImportRequest = {
        version: importData.version,
        content,
        ...(tab === 'domain' ? 
          { domain: importData.domain || content.domainName || content.domain } : 
          { tenant_id: importData.tenant_id || tenantId || '' }
        ),
      }
      importMutation.mutate(request)
    } catch (error) {
      showError('Invalid JSON: ' + (error instanceof Error ? error.message : 'Unknown error'))
    }
  }

  const handleValidate = () => {
    try {
      const content = JSON.parse(importData.content)
      validateMutation.mutate(content)
    } catch (error) {
      alert('Invalid JSON: ' + (error instanceof Error ? error.message : 'Unknown error'))
    }
  }

  const handleViewDetail = async (pack: Pack) => {
    try {
      const detail =
        tab === 'domain' && pack.domain
          ? await getDomainPack(pack.domain, pack.version)
          : tab === 'tenant' && pack.tenant_id
          ? await getTenantPack(pack.tenant_id, pack.version)
          : pack
      setSelectedPack(detail)
      setDetailDialogOpen(true)
    } catch (error) {
      console.error('Failed to fetch pack detail:', error)
      showError('Failed to fetch pack details')
    }
  }

  const handleValidatePack = (pack: Pack) => {
    setPackToValidate(pack)
    setValidationResult(null)
    setValidatePackDialogOpen(true)
    // Trigger validation
    validatePackMutation.mutate(pack)
  }

  const handleActivate = () => {
    if (!selectedPack) return
    setActivateDialogOpen(true)
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const content = e.target?.result as string
        try {
          const parsed = JSON.parse(content)
          setImportData({
            ...importData,
            content: JSON.stringify(parsed, null, 2),
            // Try to extract version and domain from content
            version: parsed.version || importData.version,
            domain: parsed.domainName || parsed.domain || importData.domain,
          })
        } catch (error) {
          alert('Invalid JSON file: ' + (error instanceof Error ? error.message : 'Unknown error'))
        }
      }
      reader.readAsText(file)
    }
  }

  const domainColumns: DataTableColumn<Pack>[] = [
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain || '-',
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2">{row.version}</Typography>
          {row.status === 'ACTIVE' && <Chip label="Active" size="small" color="success" />}
          {row.status === 'DRAFT' && <Chip label="Draft" size="small" color="default" />}
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
          color={row.status === 'ACTIVE' ? 'success' : row.status === 'DEPRECATED' ? 'error' : 'default'}
        />
      ),
    },
    {
      id: 'created_at',
      label: 'Created',
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
              color="info"
              onClick={() => handleValidatePack(row)}
              disabled={validatePackMutation.isPending}
            >
              Validate
            </Button>
          )}
          {isAdmin && row.status !== 'DEPRECATED' && (
            <Button size="small" color="primary" onClick={() => {
              setSelectedPack(row)
              handleActivate()
            }}>
              Activate
            </Button>
          )}
        </Box>
      ),
    },
  ]

  const tenantColumns: DataTableColumn<Pack>[] = [
    {
      id: 'tenant_id',
      label: 'Tenant',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.tenant_id || '-'}
        </Typography>
      ),
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2">{row.version}</Typography>
          {row.status === 'ACTIVE' && <Chip label="Active" size="small" color="success" />}
          {row.status === 'DRAFT' && <Chip label="Draft" size="small" color="default" />}
          {activeConfigs[row.tenant_id || '']?.tenant === row.version && (
            <Chip label="Active for Tenant" size="small" color="info" />
          )}
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
          color={row.status === 'ACTIVE' ? 'success' : row.status === 'DEPRECATED' ? 'error' : 'default'}
        />
      ),
    },
    {
      id: 'created_at',
      label: 'Created',
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
              color="info"
              onClick={() => handleValidatePack(row)}
              disabled={validatePackMutation.isPending}
            >
              Validate
            </Button>
          )}
          {isAdmin && row.status !== 'DEPRECATED' && (
            <Button size="small" color="primary" onClick={() => {
              setSelectedPack(row)
              handleActivate()
            }}>
              Activate
            </Button>
          )}
        </Box>
      ),
    },
  ]

  if (!isAdmin) {
    return <NotAuthorizedPage />
  }

  if (tab === 'tenant' && !tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view tenant packs.</Alert>
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
        subtitle="Import, validate, and manage Domain Packs and Tenant Policy Packs"
        actions={
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => {
              setImportDialogOpen(true)
              setImportData({
                version: '',
                content: '',
                ...(tab === 'domain'
                  ? { domain: '' }
                  : { tenant_id: tenantId && !isAdmin ? tenantId : '' }),
              })
            }}
          >
            {tab === 'domain' ? 'Import Domain Pack' : 'Import Tenant Pack'}
          </Button>
        }
      />

      <AdminWarningBanner />

      <Tabs
        value={tab}
        onChange={(_, newValue) => {
          setTab(newValue)
          setPage(0)
        }}
        sx={{ mb: 3 }}
      >
        <Tab label="Domain Packs" value="domain" />
        <Tab label="Tenant Packs" value="tenant" />
      </Tabs>

      <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
        <OpsFilterBar
          value={filters}
          onChange={setFilters}
          showDomain={true}
          syncWithUrl={true}
        />
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value as 'DRAFT' | 'ACTIVE' | 'DEPRECATED' | '')}
          >
            <MenuItem value="">
              <em>All</em>
            </MenuItem>
            <MenuItem value="DRAFT">DRAFT</MenuItem>
            <MenuItem value="ACTIVE">ACTIVE</MenuItem>
            <MenuItem value="DEPRECATED">DEPRECATED</MenuItem>
          </Select>
        </FormControl>
      </Stack>

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

      {/* Import Dialog */}
      <Dialog open={importDialogOpen} onClose={() => setImportDialogOpen(false)} maxWidth="lg" fullWidth>
        <DialogTitle>Import {tab === 'domain' ? 'Domain' : 'Tenant'} Pack</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
            {tab === 'domain' && (
              <TextField
                label="Domain"
                value={importData.domain}
                onChange={(e) => setImportData({ ...importData, domain: e.target.value })}
                required
                fullWidth
              />
            )}
            {tab === 'tenant' && (
              <TextField
                label="Tenant ID"
                value={importData.tenant_id || tenantId || ''}
                onChange={(e) => setImportData({ ...importData, tenant_id: e.target.value })}
                required
                fullWidth
                disabled={!!tenantId && !isAdmin}
                helperText={
                  isAdmin
                    ? 'Enter tenant ID to create pack for (admin can create packs for any tenant)'
                    : tenantId
                    ? 'Using current tenant'
                    : 'Enter tenant ID'
                }
              />
            )}
            <TextField
              label="Version"
              value={importData.version}
              onChange={(e) => setImportData({ ...importData, version: e.target.value })}
              required
              fullWidth
              helperText="Version string (e.g., v1.0)"
            />
            <Box>
              <input
                accept=".json"
                style={{ display: 'none' }}
                id="pack-file-upload"
                type="file"
                onChange={handleFileUpload}
              />
              <label htmlFor="pack-file-upload">
                <Button variant="outlined" component="span" startIcon={<UploadFileIcon />} fullWidth>
                  Upload JSON File
                </Button>
              </label>
            </Box>
            <TextField
              label="Pack JSON"
              value={importData.content}
              onChange={(e) => setImportData({ ...importData, content: e.target.value })}
              required
              fullWidth
              multiline
              rows={15}
              sx={{ fontFamily: 'monospace' }}
              helperText="Paste or upload pack JSON content"
            />
            {importMutation.isError && (
              <Alert severity="error">
                {importMutation.error instanceof Error
                  ? importMutation.error.message
                  : 'Failed to import pack'}
              </Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setValidateDialogOpen(true)}>Validate</Button>
          <Button onClick={() => setImportDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleImport}
            disabled={
              !importData.version ||
              !importData.content ||
              (tab === 'domain' && !importData.domain) ||
              (tab === 'tenant' && !(importData.tenant_id || tenantId)) ||
              importMutation.isPending
            }
          >
            Import
          </Button>
        </DialogActions>
      </Dialog>

      {/* Validate Dialog */}
      <Dialog
        open={validateDialogOpen}
        onClose={() => {
          setValidateDialogOpen(false)
          setValidationResult(null)
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Validate Pack</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
            {validateMutation.isPending && <Alert severity="info">Validating...</Alert>}
            {validationResult && (
              <>
                <Alert severity={validationResult.is_valid ? 'success' : 'error'}>
                  {validationResult.is_valid ? 'Pack is valid' : 'Pack validation failed'}
                </Alert>
                {validationResult.errors.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Errors:
                    </Typography>
                    <ul>
                      {validationResult.errors.map((error, idx) => (
                        <li key={idx}>{error}</li>
                      ))}
                    </ul>
                  </Box>
                )}
                {validationResult.warnings.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Warnings:
                    </Typography>
                    <ul>
                      {validationResult.warnings.map((warning, idx) => (
                        <li key={idx}>{warning}</li>
                      ))}
                    </ul>
                  </Box>
                )}
              </>
            )}
            {!validationResult && !validateMutation.isPending && (
              <Alert severity="info">Click Validate to check the pack</Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setValidateDialogOpen(false)}>Close</Button>
          <Button
            variant="contained"
            onClick={handleValidate}
            disabled={!importData.content || validateMutation.isPending}
          >
            Validate
          </Button>
        </DialogActions>
      </Dialog>

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
          {selectedPack && (
            <>
              {selectedPack.status === 'ACTIVE' && (
                <Chip label="Active" size="small" color="success" sx={{ ml: 2 }} />
              )}
              {selectedPack.status === 'DRAFT' && (
                <Chip label="Draft" size="small" color="default" sx={{ ml: 2 }} />
              )}
            </>
          )}
        </DialogTitle>
        <DialogContent>
          {selectedPack && (
            <PackContentViewer 
              pack={selectedPack}
              packType={tab}
            />
          )}
        </DialogContent>
        <DialogActions>
          {isAdmin && selectedPack && selectedPack.status !== 'DEPRECATED' && (
            <Button variant="contained" onClick={handleActivate}>
              Activate Version
            </Button>
          )}
          <Button
            onClick={() => {
              setDetailDialogOpen(false)
              setSelectedPack(null)
            }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Activate Confirm Dialog */}
      <ConfirmDialog
        open={activateDialogOpen}
        title="Activate Pack Version"
        message={`Are you sure you want to activate version ${selectedPack?.version}?`}
        confirmLabel="Activate"
        cancelLabel="Cancel"
        onConfirm={() => {
          if (selectedPack) {
            const request: PackActivateRequest = {
              tenant_id: selectedPack.tenant_id || tenantId || '',
              ...(tab === 'domain' && selectedPack.domain
                ? { domain: selectedPack.domain, domain_pack_version: selectedPack.version }
                : { tenant_pack_version: selectedPack.version }),
            }
            activateMutation.mutate(request)
          }
        }}
        onCancel={() => setActivateDialogOpen(false)}
        loading={activateMutation.isPending}
        destructive={false}
      />

      {/* Validate Pack Dialog */}
      <Dialog
        open={validatePackDialogOpen}
        onClose={() => {
          setValidatePackDialogOpen(false)
          setPackToValidate(null)
          setValidationResult(null)
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Validate Pack: {packToValidate?.domain || packToValidate?.tenant_id} v{packToValidate?.version}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
            {validatePackMutation.isPending && <Alert severity="info">Validating pack...</Alert>}
            {validationResult && (
              <>
                <Alert 
                  severity={validationResult.is_valid ? 'success' : 'error'}
                  icon={validationResult.is_valid ? <CheckCircleIcon /> : <ErrorIcon />}
                >
                  {validationResult.is_valid 
                    ? 'Pack validation passed' 
                    : `Pack validation failed with ${validationResult.errors.length} error(s)`}
                </Alert>
                {validationResult.errors.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                      Errors:
                    </Typography>
                    <Box component="ul" sx={{ pl: 2, m: 0 }}>
                      {validationResult.errors.map((error, idx) => (
                        <Typography component="li" key={idx} variant="body2" color="error">
                          {error}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                )}
                {validationResult.warnings.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                      Warnings:
                    </Typography>
                    <Box component="ul" sx={{ pl: 2, m: 0 }}>
                      {validationResult.warnings.map((warning, idx) => (
                        <Typography component="li" key={idx} variant="body2" color="text.secondary">
                          {warning}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                )}
              </>
            )}
            {!validationResult && !validatePackMutation.isPending && (
              <Alert severity="info">Click Validate to check the pack</Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => {
              setValidatePackDialogOpen(false)
              setPackToValidate(null)
              setValidationResult(null)
            }}
          >
            Close
          </Button>
          <Button
            variant="contained"
            onClick={() => {
              if (packToValidate) {
                validatePackMutation.mutate(packToValidate)
              }
            }}
            disabled={!packToValidate || validatePackMutation.isPending}
          >
            Re-validate
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
