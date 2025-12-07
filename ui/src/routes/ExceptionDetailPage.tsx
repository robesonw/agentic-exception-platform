import { useState, useEffect } from 'react'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Grid,
  Stack,
  Divider,
  Tabs,
  Tab,
} from '@mui/material'
import PageHeader from '../components/common/PageHeader.tsx'
import CardSkeleton from '../components/common/CardSkeleton.tsx'
import LoadingButton from '../components/common/LoadingButton.tsx'
import { SeverityChip, StatusChip, BreadcrumbsNav } from '../components/common'
import ExceptionTimelineTab from '../components/exceptions/ExceptionTimelineTab.tsx'
import ExceptionEvidenceTab from '../components/exceptions/ExceptionEvidenceTab.tsx'
import ExceptionExplanationTab from '../components/exceptions/ExceptionExplanationTab.tsx'
import ExceptionAuditTab from '../components/exceptions/ExceptionAuditTab.tsx'
import SimulationDialog from '../components/exceptions/SimulationDialog.tsx'
import SimulationResult from '../components/exceptions/SimulationResult.tsx'
import { useExceptionDetail } from '../hooks/useExceptions.ts'
import { useSnackbar } from '../components/common/SnackbarProvider.tsx'
import { useNavigate } from 'react-router-dom'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'
import { formatDateTime } from '../utils/dateFormat.ts'


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

  // Handle 404 or missing ID
  if (!id) {
    return (
      <Box>
        <BreadcrumbsNav
          items={[
            { label: 'Exceptions', to: '/exceptions' },
            { label: 'Exception Not Found' },
          ]}
        />
        <PageHeader title="Exception Not Found" subtitle="Exception ID is missing" />
        <Alert severity="error" sx={{ mt: 3 }}>
          Invalid exception ID. Please check the URL and try again.
        </Alert>
        <Button component={Link} to="/exceptions" sx={{ mt: 2 }}>
          Back to Exceptions List
        </Button>
      </Box>
    )
  }

  // Handle 404 from API
  if (isError && error?.message?.includes('404')) {
    return (
      <Box>
        <BreadcrumbsNav
          items={[
            { label: 'Exceptions', to: '/exceptions' },
            { label: `Exception ${id}` },
          ]}
        />
        <PageHeader title="Exception Not Found" subtitle={`Exception ID: ${id}`} />
        <Alert severity="error" sx={{ mt: 3 }}>
          Exception not found. It may have been deleted or the ID is incorrect.
        </Alert>
        <Button component={Link} to="/exceptions" sx={{ mt: 2 }}>
          Back to Exceptions List
        </Button>
      </Box>
    )
  }

  const exception = data?.exception

  // Set document title dynamically
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
  
  useDocumentTitle(documentTitle)

  // Handle action button clicks
  const handleRerunSimulation = () => {
    setSimulationDialogOpen(true)
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
    <Box>
      <BreadcrumbsNav
        items={[
          { label: 'Exceptions', to: '/exceptions' },
          { label: `Exception ${id}` },
        ]}
      />
      <PageHeader
        title={`Exception ${id}${simulationId ? ' (Simulation View)' : ''}`}
        subtitle={simulationId ? 'Viewing simulation result - no real actions were taken' : 'Exception detail and decision explanation'}
      />

      {/* Error State */}
      {isError && !error?.message?.includes('404') && (
        <Alert severity="error" sx={{ mt: 3, mb: 3 }}>
          Failed to load exception: {error?.message || 'Unknown error'}
        </Alert>
      )}

      {/* Loading State */}
      {isLoading && (
        <Grid container spacing={3} sx={{ mt: 2 }}>
          <Grid item xs={12} md={4}>
            <CardSkeleton lines={8} />
          </Grid>
          <Grid item xs={12} md={8}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary">
                  Loading tabs...
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Content */}
      {!isLoading && exception && (
        <>
          <Grid container spacing={3} sx={{ mt: 2 }}>
            {/* Summary Card - Left/Top */}
            <Grid item xs={12} md={4}>
              <Card>
                <CardContent>
                  <Stack spacing={2}>
                    {/* Header with action buttons */}
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Typography variant="h6">Summary</Typography>
                      <Stack direction="row" spacing={1}>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={handleRerunSimulation}
                        >
                          Re-run
                        </Button>
                      </Stack>
                    </Box>

                    <Divider />

                    {/* Exception ID */}
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Exception ID
                      </Typography>
                      <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                        {exception.exceptionId}
                      </Typography>
                    </Box>

                    {/* Status */}
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Status
                      </Typography>
                      <Box sx={{ mt: 0.5 }}>
                        <StatusChip status={exception.resolutionStatus} size="small" />
                      </Box>
                    </Box>

                    {/* Severity */}
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Severity
                      </Typography>
                      <Box sx={{ mt: 0.5 }}>
                        <SeverityChip severity={exception.severity} size="small" />
                      </Box>
                    </Box>

                    {/* Exception Type */}
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Exception Type
                      </Typography>
                      <Typography variant="body1">
                        {exception.exceptionType || '—'}
                      </Typography>
                    </Box>

                    {/* Timestamp */}
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Timestamp
                      </Typography>
                      <Typography variant="body1">
                        {formatDateTime(exception.timestamp)}
                      </Typography>
                    </Box>

                    {/* Source System */}
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Source System
                      </Typography>
                      <Typography variant="body1">
                        {exception.sourceSystem || '—'}
                      </Typography>
                    </Box>

                    {/* Domain */}
                    {exception.normalizedContext?.domain !== undefined && exception.normalizedContext?.domain !== null && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Domain
                        </Typography>
                        <Typography variant="body1">
                          {String(exception.normalizedContext.domain)}
                        </Typography>
                      </Box>
                    )}

                    {/* Tenant ID */}
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Tenant ID
                      </Typography>
                      <Typography variant="body1" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                        {exception.tenantId}
                      </Typography>
                    </Box>

                    <Divider />

                    {/* Quick Action Buttons */}
                    <Stack spacing={1}>
                      <LoadingButton
                        variant="contained"
                        fullWidth
                        onClick={handleApprove}
                      >
                        Approve
                      </LoadingButton>
                      <LoadingButton
                        variant="outlined"
                        fullWidth
                        onClick={handleEscalate}
                      >
                        Escalate
                      </LoadingButton>
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>

            {/* Tabs Section - Right/Bottom */}
            <Grid item xs={12} md={8}>
              <Card>
                <CardContent>
                  <Tabs value={activeTab} onChange={handleTabChange} aria-label="exception detail tabs">
                    <Tab label="Timeline" id="exception-tab-0" aria-controls="exception-tabpanel-0" />
                    <Tab label="Evidence" id="exception-tab-1" aria-controls="exception-tabpanel-1" />
                    <Tab label="Explanation" id="exception-tab-2" aria-controls="exception-tabpanel-2" />
                    <Tab label="Audit" id="exception-tab-3" aria-controls="exception-tabpanel-3" />
                  </Tabs>

                  <TabPanel value={activeTab} index={0}>
                    <ExceptionTimelineTab exceptionId={id} />
                  </TabPanel>

                  <TabPanel value={activeTab} index={1}>
                    <ExceptionEvidenceTab exceptionId={id} />
                  </TabPanel>

                  <TabPanel value={activeTab} index={2}>
                    <ExceptionExplanationTab exceptionId={id} />
                  </TabPanel>

                  <TabPanel value={activeTab} index={3}>
                    <ExceptionAuditTab exceptionId={id} />
                  </TabPanel>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </>
      )}

      {/* Simulation Dialog */}
      <SimulationDialog
        open={simulationDialogOpen}
        onClose={() => setSimulationDialogOpen(false)}
        exceptionId={id}
        onSimulationComplete={handleSimulationComplete}
      />

      {/* Simulation Result Display */}
      {simulationId && (
        <SimulationResult exceptionId={id} simulationId={simulationId} />
      )}
    </Box>
  )
}
