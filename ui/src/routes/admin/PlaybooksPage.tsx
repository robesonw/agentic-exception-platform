import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Box, Typography, Button, CircularProgress, Alert, Dialog, DialogTitle, DialogContent, DialogActions, Chip, Tooltip, Paper, Stack, TextField, FormControl, InputLabel, Select, MenuItem, Tabs, Tab, IconButton } from '@mui/material'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import InfoIcon from '@mui/icons-material/Info'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import CloseIcon from '@mui/icons-material/Close'
import { useTenant } from '../../hooks/useTenant'
import { getPlaybooksRegistry, PlaybookRegistryEntry, PlaybookRegistryParams } from '../../api/admin'
import { getDomainPack } from '../../api/onboarding'
import PageHeader from '../../components/common/PageHeader'
import NotAuthorizedPage from '../../components/common/NotAuthorizedPage'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import DataTable from '../../components/common/DataTable'
import CodeViewer from '../../components/common/CodeViewer'
import PlaybookDiagram from '../../components/admin/PlaybookDiagram'
import type { DataTableColumn } from '../../components/common/DataTable'

// Filters for playbooks
interface PlaybookFilters {
  domain?: string
  status?: string
  source?: 'domain' | 'tenant'
  search?: string
  exception_type?: string
}

export default function PlaybooksPage() {
  const { tenantId } = useTenant()
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [filters, setFilters] = useState<PlaybookFilters>({})
  const [selectedPlaybook, setSelectedPlaybook] = useState<PlaybookRegistryEntry | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [playbookContent, setPlaybookContent] = useState<any>(null)
  const [loadingPlaybook, setLoadingPlaybook] = useState(false)
  const [dialogTab, setDialogTab] = useState<'details' | 'diagram'>('details')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['playbooks-registry', tenantId, filters, page, pageSize],
    queryFn: () => {
      const params: PlaybookRegistryParams = {
        tenant_id: tenantId || undefined,
        domain: filters.domain,
        exception_type: filters.exception_type,
        source: filters.source as 'domain' | 'tenant' | undefined,
        search: filters.search,
        page: page + 1, // API uses 1-based pagination
        page_size: pageSize,
      }
      return getPlaybooksRegistry(params)
    },
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

  const handleViewDetail = async (playbook: PlaybookRegistryEntry) => {
    setSelectedPlaybook(playbook)
    setDetailDialogOpen(true)
    setLoadingPlaybook(true)
    setPlaybookContent(null)
    
    try {
      // Fetch the source pack to get full playbook content
      if (playbook.source_pack_type === 'domain') {
        // Use the domain pack API with domain and version
        console.log('Fetching domain pack:', playbook.domain, playbook.version)
        
        const pack = await getDomainPack(playbook.domain, playbook.version)
        // The pack contains content_json with playbooks
        const packContent = (pack as any).content_json || (pack as any).config || pack
        const playbooks = packContent?.playbooks || []
        
        console.log('Pack content:', packContent)
        console.log('Playbooks found:', playbooks.length)
        
        const fullPlaybook = playbooks.find((pb: any) => {
          const pbExceptionType = pb.exceptionType || pb.exception_type || pb.applies_to
          console.log('Checking playbook:', pbExceptionType, 'vs', playbook.exception_type)
          return pbExceptionType === playbook.exception_type
        })
        
        console.log('Found playbook:', fullPlaybook)
        setPlaybookContent(fullPlaybook)
      } else {
        // For tenant packs, we'd fetch from tenant pack endpoint
        console.log('Tenant pack fetching not yet implemented')
      }
    } catch (error) {
      console.error('Failed to fetch playbook content:', error)
    } finally {
      setLoadingPlaybook(false)
    }
  }

  const handleCloseDialog = useCallback(() => {
    setDetailDialogOpen(false)
    setSelectedPlaybook(null)
    setPlaybookContent(null)
    setDialogTab('details')
  }, [])

  const columns: DataTableColumn<PlaybookRegistryEntry>[] = [
    {
      id: 'playbook_id',
      label: 'ID',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.playbook_id}
        </Typography>
      ),
    },
    {
      id: 'name',
      label: 'Name',
      accessor: (row) => row.name,
    },
    {
      id: 'exception_type',
      label: 'Exception Type',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.exception_type || '-'}
        </Typography>
      ),
    },
    {
      id: 'domain',
      label: 'Domain',
      accessor: (row) => row.domain,
    },
    {
      id: 'source_pack_type',
      label: 'Source',
      accessor: (row) => (
        <Chip
          label={row.source_pack_type}
          size="small"
          color={row.source_pack_type === 'tenant' ? 'primary' : 'default'}
        />
      ),
    },
    {
      id: 'version',
      label: 'Version',
      accessor: (row) => row.version,
    },
    {
      id: 'steps_count',
      label: 'Steps',
      accessor: (row) => row.steps_count,
    },
    {
      id: 'tool_refs_count',
      label: 'Tools',
      accessor: (row) => row.tool_refs_count,
    },
    {
      id: 'status',
      label: 'Status',
      accessor: (row) => (
        <Chip
          label={row.status}
          size="small"
          color={row.status === 'active' ? 'success' : 'default'}
        />
      ),
    },
    {
      id: 'overridden',
      label: 'Override',
      accessor: (row) => (
        row.overridden ? (
          <Tooltip title={`Overridden from ${row.overridden_from}`}>
            <Chip
              label="Overridden"
              size="small"
              color="warning"
            />
          </Tooltip>
        ) : null
      ),
    },
    {
      id: 'actions',
      label: 'Actions',
      accessor: (row) => (
        <Button
          size="small"
          variant="outlined"
          onClick={() => handleViewDetail(row)}
        >
          View Details
        </Button>
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

      {/* Custom Filters for Playbooks Registry */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <TextField
            label="Search by Name or ID"
            value={filters.search || ''}
            onChange={(e) => setFilters({ ...filters, search: e.target.value || undefined })}
            size="small"
            sx={{ minWidth: 200 }}
          />
          <TextField
            label="Domain"
            value={filters.domain || ''}
            onChange={(e) => setFilters({ ...filters, domain: e.target.value || undefined })}
            size="small"
            sx={{ minWidth: 150 }}
          />
          <TextField
            label="Exception Type"
            value={filters.exception_type || ''}
            onChange={(e) => setFilters({ ...filters, exception_type: e.target.value || undefined })}
            size="small"
            sx={{ minWidth: 150 }}
          />
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Source</InputLabel>
            <Select
              value={filters.source || ''}
              label="Source"
              onChange={(e) => setFilters({ ...filters, source: e.target.value as 'domain' | 'tenant' || undefined })}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="domain">Domain Packs</MenuItem>
              <MenuItem value="tenant">Tenant Packs</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="outlined"
            onClick={() => setFilters({})}
          >
            Clear Filters
          </Button>
        </Stack>
      </Paper>

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

      {/* Detail Dialog with Tabs */}
      <Dialog
        open={detailDialogOpen}
        onClose={handleCloseDialog}
        maxWidth="lg"
        fullWidth
        PaperProps={{ sx: { minHeight: '70vh' } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pr: 6 }}>
          <Typography variant="h6" component="span" sx={{ flexGrow: 1 }}>
            {selectedPlaybook?.name || 'Playbook'}
          </Typography>
          <Chip 
            label={selectedPlaybook?.status || 'unknown'} 
            size="small" 
            color={selectedPlaybook?.status === 'active' ? 'success' : 'default'} 
          />
          {selectedPlaybook?.overridden && (
            <Chip label="Overridden" size="small" color="warning" />
          )}
          <IconButton
            aria-label="close"
            onClick={handleCloseDialog}
            sx={{ position: 'absolute', right: 8, top: 8 }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        
        {/* Tab Navigation */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
          <Tabs 
            value={dialogTab} 
            onChange={(_, newValue) => setDialogTab(newValue)}
            aria-label="Playbook view tabs"
          >
            <Tab 
              icon={<InfoIcon />} 
              iconPosition="start" 
              label="Details" 
              value="details" 
            />
            <Tab 
              icon={<AccountTreeIcon />} 
              iconPosition="start" 
              label="Workflow Diagram" 
              value="diagram" 
              disabled={!playbookContent?.steps || playbookContent.steps.length === 0}
            />
          </Tabs>
        </Box>

        <DialogContent sx={{ p: 0 }}>
          {loadingPlaybook && (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
              <CircularProgress />
            </Box>
          )}
          
          {/* Details Tab */}
          {selectedPlaybook && !loadingPlaybook && dialogTab === 'details' && (
            <Box sx={{ p: 3 }}>
              {/* Summary Section */}
              <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2, color: 'primary.main' }}>
                  Summary
                </Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Name</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 500 }}>{selectedPlaybook.name}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Playbook ID</Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{selectedPlaybook.playbook_id}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Exception Type</Typography>
                    <Chip label={selectedPlaybook.exception_type} size="small" variant="outlined" />
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Domain</Typography>
                    <Typography variant="body1">{selectedPlaybook.domain}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Version</Typography>
                    <Typography variant="body1">{selectedPlaybook.version}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Source</Typography>
                    <Chip 
                      label={`${selectedPlaybook.source_pack_type} pack`} 
                      size="small" 
                      color={selectedPlaybook.source_pack_type === 'tenant' ? 'primary' : 'default'}
                    />
                  </Box>
                </Box>
                {selectedPlaybook.description && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="caption" color="text.secondary">Description</Typography>
                    <Typography variant="body2">{selectedPlaybook.description}</Typography>
                  </Box>
                )}
              </Paper>

              {/* Metrics Section */}
              <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2, color: 'primary.main' }}>
                  Metrics
                </Typography>
                <Box sx={{ display: 'flex', gap: 4 }}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="primary">{selectedPlaybook.steps_count}</Typography>
                    <Typography variant="caption" color="text.secondary">Workflow Steps</Typography>
                  </Box>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="secondary">{selectedPlaybook.tool_refs_count}</Typography>
                    <Typography variant="caption" color="text.secondary">Tool References</Typography>
                  </Box>
                </Box>
              </Paper>

              {/* Override Information */}
              {selectedPlaybook.overridden && (
                <Paper variant="outlined" sx={{ p: 2, mb: 3, borderColor: 'warning.main' }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 1, color: 'warning.main' }}>
                    Override Information
                  </Typography>
                  <Typography variant="body2">
                    This playbook overrides: <strong>{selectedPlaybook.overridden_from}</strong>
                  </Typography>
                </Paper>
              )}

              {/* Workflow Steps List */}
              {playbookContent?.steps && playbookContent.steps.length > 0 && (
                <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2, color: 'primary.main' }}>
                    Workflow Steps ({playbookContent.steps.length})
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {playbookContent.steps.map((step: any, index: number) => (
                      <Box 
                        key={index} 
                        sx={{ 
                          display: 'flex', 
                          alignItems: 'flex-start', 
                          p: 1.5, 
                          bgcolor: 'action.hover', 
                          borderRadius: 1,
                          border: '1px solid',
                          borderColor: 'divider'
                        }}
                      >
                        <Box 
                          sx={{ 
                            minWidth: 28, 
                            height: 28, 
                            bgcolor: step.type === 'human' ? 'warning.main' : step.type === 'decision' ? 'info.main' : 'primary.main', 
                            color: 'white', 
                            borderRadius: '50%', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center', 
                            fontSize: '0.75rem',
                            fontWeight: 'bold',
                            mr: 2,
                            flexShrink: 0
                          }}
                        >
                          {index + 1}
                        </Box>
                        <Box sx={{ flex: 1 }}>
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {step.action || step.name || `Step ${index + 1}`}
                          </Typography>
                          {step.description && (
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                              {step.description}
                            </Typography>
                          )}
                          {step.type && (
                            <Chip label={step.type} size="small" sx={{ mt: 0.5 }} />
                          )}
                          {step.tool && (
                            <Chip label={`Tool: ${step.tool}`} size="small" color="secondary" sx={{ mt: 0.5, ml: 0.5 }} />
                          )}
                        </Box>
                      </Box>
                    ))}
                  </Box>
                </Paper>
              )}

              {/* Source Pack Info */}
              <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2, color: 'primary.main' }}>
                  <FolderOpenIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                  Source Pack Information
                </Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Pack Type</Typography>
                    <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>{selectedPlaybook.source_pack_type}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Pack ID</Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{selectedPlaybook.source_pack_id}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Domain</Typography>
                    <Typography variant="body1">{selectedPlaybook.domain}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Version</Typography>
                    <Typography variant="body1">{selectedPlaybook.version}</Typography>
                  </Box>
                </Box>
              </Paper>

              {/* Raw Configuration */}
              {playbookContent && (
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 'bold', mb: 2, color: 'primary.main' }}>
                    Raw Configuration
                  </Typography>
                  <CodeViewer
                    code={JSON.stringify(playbookContent, null, 2)}
                    title="Playbook JSON"
                    language="json"
                    maxHeight={300}
                    collapsible
                  />
                </Paper>
              )}
            </Box>
          )}

          {/* Diagram Tab */}
          {selectedPlaybook && !loadingPlaybook && dialogTab === 'diagram' && playbookContent?.steps && (
            <Box sx={{ height: 500, width: '100%' }}>
              <PlaybookDiagram 
                steps={playbookContent.steps}
                playbookName={selectedPlaybook.name}
              />
            </Box>
          )}
        </DialogContent>
        
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button 
            variant="contained"
            onClick={handleCloseDialog}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

