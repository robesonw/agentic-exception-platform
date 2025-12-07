import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Alert,
  Stack,
  Chip,
  Grid,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
} from '@mui/material'
import {
  Error as ErrorIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Pending as PendingIcon,
} from '@mui/icons-material'
import PageHeader from '../components/common/PageHeader.tsx'
import CardSkeleton from '../components/common/CardSkeleton.tsx'
import { SeverityChip } from '../components/common'
import { SupervisorKpiCard } from '../components/supervisor'
import { useDocumentTitle } from '../hooks/useDocumentTitle.ts'
import { useSupervisorOverview } from '../hooks/useSupervisor.ts'
import { useTenant } from '../hooks/useTenant.tsx'
import { formatDateTime } from '../utils/dateFormat.ts'
import SupervisorEscalationsTab from '../components/supervisor/SupervisorEscalationsTab.tsx'
import SupervisorPolicyViolationsTab from '../components/supervisor/SupervisorPolicyViolationsTab.tsx'
import SupervisorSloQuotaCards from '../components/supervisor/SupervisorSloQuotaCards.tsx'
import type { SeverityStatusCounts } from '../types'


/**
 * Calculate total count for a severity level
 */
function getSeverityTotal(counts: SeverityStatusCounts, severity: string): number {
  const severityCounts = counts[severity]
  if (!severityCounts) {
    return 0
  }
  return Object.values(severityCounts).reduce((sum, count) => sum + count, 0)
}

/**
 * Calculate total count for a status across all severities
 */
function getStatusTotal(counts: SeverityStatusCounts, status: string): number {
  let total = 0
  Object.values(counts).forEach((severityCounts) => {
    total += severityCounts[status] || 0
  })
  return total
}

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
    <div role="tabpanel" hidden={value !== index} id={`supervisor-tabpanel-${index}`} aria-labelledby={`supervisor-tab-${index}`}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  )
}

export default function SupervisorPage() {
  useDocumentTitle('Supervisor Dashboard')
  const { tenantId } = useTenant()
  const [searchParams, setSearchParams] = useSearchParams()

  // Tab names mapping
  const tabNames = ['overview', 'escalations', 'violations'] as const
  type TabName = typeof tabNames[number]

  // Get initial tab from URL or default to 'overview'
  const getTabIndexFromUrl = (): number => {
    const tabParam = searchParams.get('tab')
    if (tabParam && tabNames.includes(tabParam as TabName)) {
      return tabNames.indexOf(tabParam as TabName)
    }
    return 0 // Default to overview
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

  // Filter state
  const [domain, setDomain] = useState<string>('')
  const [dateFrom, setDateFrom] = useState<string>('')
  const [dateTo, setDateTo] = useState<string>('')

  // Prepare API parameters
  const apiParams = {
    ...(domain ? { domain } : {}),
    ...(dateFrom ? { from_ts: new Date(dateFrom).toISOString() } : {}),
    ...(dateTo ? { to_ts: new Date(dateTo).toISOString() } : {}),
  }

  // Fetch supervisor overview
  const { data, isLoading, isError, error } = useSupervisorOverview(apiParams)

  // Extract data
  const counts = data?.counts || {}
  const escalationsCount = data?.escalations_count || 0
  const pendingApprovalsCount = data?.pending_approvals_count || 0
  const topViolations = data?.top_policy_violations || []
  const optimizationSuggestions = data?.optimization_suggestions_summary || {}

  // Severity levels to display
  const severityLevels = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

  // Prepare filter props for tabs
  const filterProps = {
    tenantId: tenantId || undefined,
    domain: domain || undefined,
    from_ts: dateFrom ? new Date(dateFrom).toISOString() : undefined,
    to_ts: dateTo ? new Date(dateTo).toISOString() : undefined,
  }

  // Handle tab change
  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue)
    // Update URL query param
    const newParams = new URLSearchParams(searchParams)
    if (newValue === 0) {
      // Remove tab param for default (overview) tab
      newParams.delete('tab')
    } else {
      newParams.set('tab', tabNames[newValue])
    }
    setSearchParams(newParams, { replace: false }) // Use replace: false to allow browser back/forward
  }

  return (
    <Box>
      <PageHeader
        title="Supervisor Dashboard"
        subtitle="Cross-tenant and cross-domain exception oversight"
      />

      {/* Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                label="Domain"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="All domains"
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                type="date"
                label="From Date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                InputLabelProps={{ shrink: true }}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                type="date"
                label="To Date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                InputLabelProps={{ shrink: true }}
                size="small"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
                <Typography variant="body2" color="text.secondary">
                  Tenant: {tenantId || 'Not selected'}
                </Typography>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Tabs value={activeTab} onChange={handleTabChange} aria-label="supervisor dashboard tabs">
            <Tab label="Overview" id="supervisor-tab-0" aria-controls="supervisor-tabpanel-0" />
            <Tab label="Escalations" id="supervisor-tab-1" aria-controls="supervisor-tabpanel-1" />
            <Tab label="Policy Violations" id="supervisor-tab-2" aria-controls="supervisor-tabpanel-2" />
          </Tabs>

          {/* Overview Tab */}
          <TabPanel value={activeTab} index={0}>
            {/* Error State */}
            {isError && (
              <Alert severity="error" sx={{ mb: 3 }}>
                Failed to load supervisor overview: {error?.message || 'Unknown error'}
              </Alert>
            )}

            {/* Loading State */}
            {isLoading && (
              <>
                <Typography variant="h6" gutterBottom sx={{ mt: 3, mb: 2 }}>
                  Status Summary
                </Typography>
                <Grid container spacing={3} sx={{ mb: 4 }}>
                  {[1, 2, 3, 4].map((i) => (
                    <Grid item xs={12} sm={6} md={3} key={i}>
                      <CardSkeleton lines={3} />
                    </Grid>
                  ))}
                </Grid>
              </>
            )}

            {/* KPI Cards - Severity Counts */}
            {!isLoading && data && (
        <>
          <Typography variant="h6" gutterBottom sx={{ mt: 3, mb: 2 }}>
            Severity Overview
          </Typography>
          <Grid container spacing={3} sx={{ mb: 4 }}>
            {severityLevels.map((severity) => {
              const total = getSeverityTotal(counts, severity)
              const severityCounts = counts[severity] || {}
              return (
                <Grid item xs={12} sm={6} md={3} key={severity}>
                  <Card>
                    <CardContent>
                      <Stack spacing={1}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="h4">{total}</Typography>
                          <SeverityChip severity={severity} size="small" />
                        </Box>
                        <Stack spacing={0.5}>
                          {Object.entries(severityCounts).map(([status, count]) => (
                            <Box key={status} sx={{ display: 'flex', justifyContent: 'space-between' }}>
                              <Typography variant="caption" color="text.secondary">
                                {status.replace('_', ' ')}:
                              </Typography>
                              <Typography variant="body2" fontWeight="medium">
                                {count}
                              </Typography>
                            </Box>
                          ))}
                        </Stack>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              )
            })}
          </Grid>

          {/* KPI Cards - Status Summary */}
          {!isLoading && data && (
            <>
              <Typography variant="h6" gutterBottom sx={{ mt: 3, mb: 2 }}>
                Status Summary
              </Typography>
              <Grid container spacing={3} sx={{ mb: 4 }}>
                <Grid item xs={12} sm={6} md={3}>
                  <SupervisorKpiCard
                    label="Open exceptions"
                    value={getStatusTotal(counts, 'OPEN')}
                    icon={<PendingIcon />}
                    severity="normal"
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <SupervisorKpiCard
                    label="Escalated exceptions"
                    value={escalationsCount}
                    icon={<ErrorIcon />}
                    severity={escalationsCount > 0 ? 'critical' : 'normal'}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <SupervisorKpiCard
                    label="Pending approvals"
                    value={pendingApprovalsCount}
                    icon={<WarningIcon />}
                    severity={pendingApprovalsCount > 0 ? 'warning' : 'normal'}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <SupervisorKpiCard
                    label="Resolved exceptions"
                    value={getStatusTotal(counts, 'RESOLVED')}
                    icon={<CheckCircleIcon />}
                    severity="normal"
                  />
                </Grid>
              </Grid>
            </>
          )}

          {/* Top Policy Violations */}
          <Typography variant="h6" gutterBottom sx={{ mt: 3, mb: 2 }}>
            Top Policy Violations
          </Typography>
          {topViolations.length > 0 ? (
            <Card sx={{ mb: 4 }}>
              <CardContent>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Rule</TableCell>
                        <TableCell>Violation Type</TableCell>
                        <TableCell>Exception ID</TableCell>
                        <TableCell>Tenant</TableCell>
                        <TableCell>Domain</TableCell>
                        <TableCell>Last Seen</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {topViolations.slice(0, 10).map((violation, index) => (
                        <TableRow key={`${violation.exception_id}-${index}`} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight="medium">
                              {violation.violated_rule}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={violation.violation_type}
                              size="small"
                              color="error"
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                              {violation.exception_id}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{violation.tenant_id}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{violation.domain || '—'}</Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {formatDateTime(violation.timestamp)}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          ) : (
            <Alert severity="info" sx={{ mb: 4 }}>
              No policy violations found for the selected filters.
            </Alert>
          )}

          {/* SLO & Quota Cards */}
          <SupervisorSloQuotaCards filters={filterProps} />

          {/* Optimization Suggestions */}
          <Typography variant="h6" gutterBottom sx={{ mt: 3, mb: 2 }}>
            Optimization Suggestions
          </Typography>
          {Object.keys(optimizationSuggestions).length > 0 ? (
            <Card>
              <CardContent>
                <Stack spacing={1}>
                  {Object.entries(optimizationSuggestions).map(([key, value]) => (
                    <Box key={key} sx={{ pl: 2, borderLeft: 2, borderColor: 'primary.main' }}>
                      <Typography variant="body2">
                        <strong>{key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}:</strong>{' '}
                        {typeof value === 'object' && value !== null
                          ? JSON.stringify(value, null, 2)
                          : String(value)}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              </CardContent>
            </Card>
          ) : (
            <Alert severity="info">
              No optimization suggestions at this time.
            </Alert>
          )}
            </>
            )}

            {/* Empty State (no tenant selected) */}
            {!tenantId && !isLoading && (
              <Alert severity="info" sx={{ mt: 3 }}>
                Please select a tenant to view supervisor dashboard.
              </Alert>
            )}
          </TabPanel>

          {/* Escalations Tab */}
          <TabPanel value={activeTab} index={1}>
            <SupervisorEscalationsTab filters={filterProps} />
          </TabPanel>

          {/* Policy Violations Tab */}
          <TabPanel value={activeTab} index={2}>
            <SupervisorPolicyViolationsTab filters={filterProps} />
          </TabPanel>
        </CardContent>
      </Card>
    </Box>
  )
}
