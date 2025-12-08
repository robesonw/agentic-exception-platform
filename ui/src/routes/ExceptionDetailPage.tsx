import { useState, useEffect } from 'react'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import {
  Box,
  Typography,
  Button,
  Alert,
  Grid,
  Tabs,
  Tab,
  Paper,
  IconButton,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ExceptionTimelineTab from '../components/exceptions/ExceptionTimelineTab.tsx'
import ExceptionEvidenceTab from '../components/exceptions/ExceptionEvidenceTab.tsx'
import ExceptionExplanationTab from '../components/exceptions/ExceptionExplanationTab.tsx'
import ExceptionAuditTab from '../components/exceptions/ExceptionAuditTab.tsx'
import SimulationDialog from '../components/exceptions/SimulationDialog.tsx'
import SimulationResult from '../components/exceptions/SimulationResult.tsx'
import { SeverityChip } from '../components/common'
import { useExceptionDetail } from '../hooks/useExceptions.ts'
import { useSnackbar } from '../components/common/SnackbarProvider.tsx'
import { useNavigate } from 'react-router-dom'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'
import { formatDateTime } from '../utils/dateFormat.ts'
import { useTenant } from '../hooks/useTenant.tsx'


/**
 * Tab panel component for tabs content
 */
interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div role="tabpanel" hidden={value !== index} id={`exception-tabpanel-${index}`} aria-labelledby={`exception-tab-${index}`}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  )
}

export default function ExceptionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const { showInfo } = useSnackbar()
  const navigate = useNavigate()
  const { tenantId, apiKey } = useTenant()
  const [simulationDialogOpen, setSimulationDialogOpen] = useState(false)

  // Read simulationId from URL query params
  const simulationId = searchParams.get('simulationId')

  // Tab names mapping
  const tabNames = ['timeline', 'evidence', 'explanation', 'audit'] as const
  type TabName = typeof tabNames[number]

  // Get initial tab from URL or default to 'timeline'
  const getTabIndexFromUrl = (): number => {
    const tabParam = searchParams.get('tab')
    if (tabParam && tabNames.includes(tabParam as TabName)) {
      return tabNames.indexOf(tabParam as TabName)
    }
    return 0 // Default to timeline
  }

  const [activeTab, setActiveTab] = useState(getTabIndexFromUrl)

  // Sync activeTab with URL when tab param changes externally (e.g., browser back/forward)
  useEffect(() => {
    const tabParam = searchParams.get('tab')
    if (tabParam && tabNames.includes(tabParam as TabName)) {
      const tabIndex = tabNames.indexOf(tabParam as TabName)
      if (tabIndex !== activeTab) {
        setActiveTab(tabIndex)
      }
    } else if (!tabParam && activeTab !== 0) {
      // If no tab param and not on first tab, sync to first tab
      setActiveTab(0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  // Fetch exception detail
  const { data, isLoading, isError, error } = useExceptionDetail(id || '')
  
  const exception = data?.exception

  // Compute document title (must be before early returns for hook to work)
  const documentTitle = exception
    ? (() => {
        // Try to include exception type or other identifier if available
        const exceptionType = exception.exceptionType || exception.normalizedContext?.exceptionType
        return exceptionType 
          ? `Exception ${id} – ${exceptionType}`
          : `Exception ${id}`
      })()
    : id
    ? `Exception ${id}`
    : 'Exception'
  
  // Call hook unconditionally (before any early returns)
  useDocumentTitle(documentTitle)

  // Show error if tenantId or API key is missing (required for API call)
  if ((!tenantId || !apiKey) && !isLoading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Alert severity="warning">
          {!tenantId && !apiKey 
            ? 'Tenant ID and API key are required to view exception details. Please go to the login page to set them.'
            : !tenantId 
            ? 'Tenant ID is required to view exception details. Please select a tenant from the login page.'
            : 'API key is required to view exception details. Please set your API key on the login page.'}
        </Alert>
        <Button component={Link} to="/login">
          Go to Login
        </Button>
        <Button component={Link} to="/exceptions" variant="outlined">
          Back to Exceptions List
        </Button>
      </Box>
    )
  }

  // Handle 404 or missing ID
  if (!id) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Alert severity="error">
          Invalid exception ID. Please check the URL and try again.
        </Alert>
        <Button component={Link} to="/exceptions">
          Back to Exceptions List
        </Button>
      </Box>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Typography>Loading...</Typography>
      </Box>
    )
  }

  // Error state (non-404 errors) - check BEFORE trying to use exception
  if (isError && !error?.message?.includes('404')) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Alert severity="error">
          Failed to load exception: {error?.message || 'Unknown error'}
        </Alert>
        <Button component={Link} to="/exceptions">
          Back to Exceptions List
        </Button>
      </Box>
    )
  }

  // Handle 404 from API or no exception
  if (isError && error?.message?.includes('404')) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Alert severity="error">
          Exception not found. It may have been deleted or the ID is incorrect.
        </Alert>
        <Button component={Link} to="/exceptions">
          Back to Exceptions List
        </Button>
      </Box>
    )
  }

  if (!exception) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Typography>No exception found.</Typography>
        <Button component={Link} to="/exceptions">
          Back to Exceptions List
        </Button>
      </Box>
    )
  }

  // Handle simulation completion
  const handleSimulationComplete = (simulationId: string) => {
    // Navigate to same page with simulationId query param, preserving current tab
    const newParams = new URLSearchParams(searchParams)
    newParams.set('simulationId', simulationId)
    // Preserve tab if not default
    const currentTab = searchParams.get('tab')
    if (currentTab && currentTab !== 'timeline') {
      newParams.set('tab', currentTab)
    }
    navigate(`/exceptions/${id}?${newParams.toString()}`, { replace: true })
    // Optionally show info about viewing results
    showInfo(`Simulation completed. View results in the Explanation tab.`)
  }

  const handleApprove = () => {
    showInfo('Approve functionality coming in a later phase')
  }

  const handleEscalate = () => {
    showInfo('Escalate functionality coming in a later phase')
  }

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue)
    // Update URL query param while preserving other params (like simulationId)
    const newParams = new URLSearchParams(searchParams)
    if (newValue === 0) {
      // Remove tab param for default (timeline) tab
      newParams.delete('tab')
    } else {
      newParams.set('tab', tabNames[newValue])
    }
    setSearchParams(newParams, { replace: false }) // Use replace: false to allow browser back/forward
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid',
          borderColor: 'divider',
          pb: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <IconButton
            component={Link}
            to="/exceptions"
            sx={{ color: 'text.secondary' }}
          >
            <ArrowBackIcon />
          </IconButton>
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 0.5 }}>
              <Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
                {exception.exceptionId || id || 'Unknown'}
              </Typography>
              {exception.severity && (
                <SeverityChip severity={exception.severity} size="small" />
              )}
            </Box>
            <Typography variant="body2" color="text.secondary">
              {exception.exceptionType || '—'} · {exception.normalizedContext?.domain != null ? String(exception.normalizedContext.domain) : '—'} · Owner: —
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            color="error"
            onClick={handleEscalate}
          >
            Escalate
          </Button>
          <Button
            variant="contained"
            color="primary"
            onClick={handleApprove}
          >
            Approve Resolution
          </Button>
        </Box>
      </Box>

      {/* Main 3-column layout */}
      <Grid container spacing={2}>
        {/* LEFT: key attributes / RAG preview */}
        <Grid item xs={12} md={3}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" gutterBottom>
                Key Attributes
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                {exception.normalizedContext?.amount != null && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', display: 'block', mb: 0.5 }}>
                      Amount
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {String(exception.normalizedContext.amount)}
                    </Typography>
                  </Box>
                )}
                {exception.normalizedContext?.counterparty != null && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', display: 'block', mb: 0.5 }}>
                      Counterparty
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {String(exception.normalizedContext.counterparty)}
                    </Typography>
                  </Box>
                )}
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', display: 'block', mb: 0.5 }}>
                    Source System
                  </Typography>
                  <Typography variant="body2">
                    {exception.sourceSystem || '—'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', display: 'block', mb: 0.5 }}>
                    Timestamp
                  </Typography>
                  <Typography variant="body2">
                    {formatDateTime(exception.timestamp)}
                  </Typography>
                </Box>
                {exception.normalizedContext?.domain != null && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.05em', display: 'block', mb: 0.5 }}>
                      Domain
                    </Typography>
                    <Typography variant="body2">
                      {String(exception.normalizedContext.domain)}
                    </Typography>
                  </Box>
                )}
              </Box>
            </Paper>

            <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" gutterBottom>
                RAG Evidence
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                No evidence loaded
              </Typography>
            </Paper>
          </Box>
        </Grid>

        {/* CENTER: main tabbed content (Timeline/Evidence/Explanation/Audit) */}
        <Grid item xs={12} md={6}>
          <Paper
            sx={{
              p: 2,
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'divider',
              minHeight: 400,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Tabs value={activeTab} onChange={handleTabChange} aria-label="exception detail tabs">
              <Tab label="Timeline" id="exception-tab-0" aria-controls="exception-tabpanel-0" />
              <Tab label="Evidence" id="exception-tab-1" aria-controls="exception-tabpanel-1" />
              <Tab label="Explanation" id="exception-tab-2" aria-controls="exception-tabpanel-2" />
              <Tab label="Audit" id="exception-tab-3" aria-controls="exception-tabpanel-3" />
            </Tabs>

            <TabPanel value={activeTab} index={0}>
              <ExceptionTimelineTab exceptionId={id!} />
            </TabPanel>

            <TabPanel value={activeTab} index={1}>
              <ExceptionEvidenceTab exceptionId={id!} />
            </TabPanel>

            <TabPanel value={activeTab} index={2}>
              <ExceptionExplanationTab exceptionId={id!} />
            </TabPanel>

            <TabPanel value={activeTab} index={3}>
              <ExceptionAuditTab exceptionId={id!} />
            </TabPanel>
          </Paper>
        </Grid>

        {/* RIGHT: Recommended playbook + collaborators */}
        <Grid item xs={12} md={3}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" gutterBottom>
                Recommended Playbook
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                No playbook available
              </Typography>
            </Paper>

            <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" gutterBottom>
                Collaborators
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                No collaborators yet
              </Typography>
            </Paper>
          </Box>
        </Grid>
      </Grid>

      {/* Simulation Dialog */}
      <SimulationDialog
        open={simulationDialogOpen}
        onClose={() => setSimulationDialogOpen(false)}
        exceptionId={id!}
        onSimulationComplete={handleSimulationComplete}
      />

      {/* Simulation Result Display */}
      {simulationId && id && (
        <SimulationResult exceptionId={id} simulationId={simulationId} />
      )}
    </Box>
  )
}
