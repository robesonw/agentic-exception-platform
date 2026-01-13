/**
 * Demo Settings Page
 * 
 * Admin page for controlling demo mode, tool simulation, and scenario execution.
 * Features:
 * - Demo mode toggle
 * - Scenario generation toggle  
 * - Industry and scenario selection
 * - Three run modes: Burst, Scheduled, Continuous
 * - Bootstrap and reset controls
 */

import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Grid,
  Typography,
  Switch,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  TextField,
  Alert,
  AlertTitle,
  CircularProgress,
  Divider,
  LinearProgress,
  Stack,
  Tooltip,
  IconButton,
  OutlinedInput,
  SelectChangeEvent,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button as MuiButton
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import RefreshIcon from '@mui/icons-material/Refresh'
import BuildIcon from '@mui/icons-material/Build'
import ScheduleIcon from '@mui/icons-material/Schedule'
import AutorenewIcon from '@mui/icons-material/Autorenew'
import DeleteForeverIcon from '@mui/icons-material/DeleteForever'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty'

import { PageShell, Card, Section, Button, PageHeader } from '../../components/ui'
import AdminWarningBanner from '../../components/common/AdminWarningBanner'
import {
  updateDemoSettings,
  getDemoStatus,
  getDemoCatalog,
  runBootstrap,
  startDemoRun,
  stopDemoRun,
  resetDemoData,
  DemoStatus,
  DemoCatalog,
  DemoRunMode,
  DemoRunStatus,
  Industry,
  StartRunRequest,
  DemoSettingsUpdate
} from '../../api/demo'

// ============================================================================
// Constants
// ============================================================================

const INDUSTRY_LABELS: Record<Industry, string> = {
  finance: 'Finance / Capital Markets',
  insurance: 'Insurance',
  healthcare: 'Healthcare',
  retail: 'Retail / E-Commerce',
  saas_ops: 'SaaS / DevOps'
}

const MODE_DESCRIPTIONS: Record<DemoRunMode, string> = {
  burst: 'Generate a batch of exceptions immediately',
  scheduled: 'Generate exceptions at regular intervals for a duration',
  continuous: 'Continuously drip exceptions in background until stopped'
}

const STATUS_ICONS: Record<DemoRunStatus, React.ReactNode> = {
  pending: <HourglassEmptyIcon color="warning" />,
  running: <AutorenewIcon color="primary" sx={{ animation: 'spin 2s linear infinite', '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } } }} />,
  completed: <CheckCircleOutlineIcon color="success" />,
  cancelled: <StopIcon color="action" />,
  failed: <ErrorOutlineIcon color="error" />
}

// ============================================================================
// Component
// ============================================================================

export default function DemoSettingsPage() {
  const queryClient = useQueryClient()

  // Local state for form controls
  const [selectedMode, setSelectedMode] = useState<DemoRunMode>('burst')
  const [selectedIndustries, setSelectedIndustries] = useState<Industry[]>(['finance'])
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>([])
  const [burstCount, setBurstCount] = useState<number>(10)
  const [scheduledInterval, setScheduledInterval] = useState<number>(2)
  const [scheduledDuration, setScheduledDuration] = useState<number>(120)
  const [confirmResetOpen, setConfirmResetOpen] = useState(false)

  // Queries
  const {
    data: status,
    isLoading: statusLoading,
    error: statusError,
    refetch: refetchStatus
  } = useQuery<DemoStatus>({
    queryKey: ['demoStatus'],
    queryFn: getDemoStatus,
    refetchInterval: 3000 // Poll every 3 seconds for active run updates
  })

  const {
    data: catalog,
    isLoading: catalogLoading
  } = useQuery<DemoCatalog>({
    queryKey: ['demoCatalog'],
    queryFn: getDemoCatalog
  })

  // Mutations
  const updateSettingsMutation = useMutation({
    mutationFn: (settings: DemoSettingsUpdate) => updateDemoSettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['demoStatus'] })
    }
  })

  const bootstrapMutation = useMutation({
    mutationFn: runBootstrap,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['demoStatus'] })
    }
  })

  const startRunMutation = useMutation({
    mutationFn: startDemoRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['demoStatus'] })
    }
  })

  const stopRunMutation = useMutation({
    mutationFn: stopDemoRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['demoStatus'] })
    }
  })

  const resetMutation = useMutation({
    mutationFn: () => resetDemoData(false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['demoStatus'] })
      setConfirmResetOpen(false)
    }
  })

  // Filter scenarios by selected industries
  const filteredScenarios = catalog?.scenarios.filter(
    s => selectedIndustries.includes(s.industry)
  ) || []

  // Update selected scenarios when industries change
  useEffect(() => {
    if (filteredScenarios.length > 0 && selectedScenarios.length === 0) {
      setSelectedScenarios(filteredScenarios.slice(0, 1).map(s => s.scenario_id))
    }
    // Remove scenarios that are no longer in filtered list
    setSelectedScenarios(prev => prev.filter(
      id => filteredScenarios.some(s => s.scenario_id === id)
    ))
  }, [selectedIndustries, catalog])

  // Handlers
  const handleDemoModeToggle = useCallback(async (enabled: boolean) => {
    await updateSettingsMutation.mutateAsync({ enabled: enabled })
  }, [updateSettingsMutation])

  const handleScenariosEnabledToggle = useCallback(async (enabled: boolean) => {
    await updateSettingsMutation.mutateAsync({ scenarios_enabled: enabled })
  }, [updateSettingsMutation])

  const handleIndustryChange = (event: SelectChangeEvent<Industry[]>) => {
    const value = event.target.value
    setSelectedIndustries(typeof value === 'string' ? value.split(',') as Industry[] : value)
  }

  const handleScenarioChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value
    setSelectedScenarios(typeof value === 'string' ? value.split(',') : value)
  }

  const handleStartRun = async () => {
    const tenantKeys = catalog?.tenants
      .filter(t => selectedIndustries.includes(t.industry))
      .map(t => t.tenant_key) || []

    const request: StartRunRequest = {
      mode: selectedMode,
      tenant_keys: tenantKeys,
      scenario_ids: selectedScenarios
    }

    if (selectedMode === 'burst') {
      request.burst_count = burstCount
    } else if (selectedMode === 'scheduled') {
      request.frequency_seconds = scheduledInterval
      request.duration_seconds = scheduledDuration
    }

    await startRunMutation.mutateAsync(request)
  }

  const handleStopRun = async () => {
    await stopRunMutation.mutateAsync()
  }

  const handleBootstrap = async () => {
    await bootstrapMutation.mutateAsync()
  }

  const handleReset = async () => {
    await resetMutation.mutateAsync()
  }

  // Loading state
  if (statusLoading || catalogLoading) {
    return (
      <PageShell>
        <PageHeader title="Demo Settings" subtitle="Control demo mode, tool simulation, and generate demo exceptions" />
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      </PageShell>
    )
  }

  // Error state
  if (statusError) {
    return (
      <PageShell>
        <PageHeader title="Demo Settings" subtitle="Control demo mode, tool simulation, and generate demo exceptions" />
        <Alert severity="error">
          <AlertTitle>Failed to load demo status</AlertTitle>
          {String(statusError)}
        </Alert>
      </PageShell>
    )
  }

  // Status has properties directly (enabled, bootstrap_complete, etc.)
  const activeRun = status?.active_run
  const hasActiveRun = activeRun && ['pending', 'running'].includes(activeRun.status)
  const demoEnabled = status?.enabled ?? false

  return (
    <PageShell>
      <PageHeader 
        title="Demo Settings" 
        subtitle="Control demo mode, tool simulation, and generate demo exceptions"
        onRefresh={() => refetchStatus()}
      />
      
      <AdminWarningBanner />

      <Grid container spacing={3}>
        {/* Left Column: Settings & Controls */}
        <Grid item xs={12} md={7}>
          {/* Master Toggles */}
          <Section title="Demo Mode Controls" sx={{ mb: 3 }}>
            <Card>
              <Stack spacing={2}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box>
                    <Typography variant="subtitle1" fontWeight={600}>
                      Demo Mode
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Enable demo mode to use synthetic data and scenarios
                    </Typography>
                  </Box>
                  <Switch
                    checked={demoEnabled}
                    onChange={(e) => handleDemoModeToggle(e.target.checked)}
                    disabled={updateSettingsMutation.isPending}
                  />
                </Box>

                <Divider />

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Box>
                    <Typography variant="subtitle1" fontWeight={600}>
                      Scenario Generation
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Enable scenario-driven exception generation
                    </Typography>
                  </Box>
                  <Switch
                    checked={(status?.scenarios_active?.length ?? 0) > 0}
                    onChange={(e) => handleScenariosEnabledToggle(e.target.checked)}
                    disabled={updateSettingsMutation.isPending || !demoEnabled}
                  />
                </Box>
              </Stack>
            </Card>
          </Section>

          {/* Bootstrap */}
          <Section title="Demo Data Bootstrap" sx={{ mb: 3 }}>
            <Card>
              <Stack spacing={2}>
                <Typography variant="body2" color="text.secondary">
                  Bootstrap creates demo tenants and seeds initial exception data.
                  This is idempotent and safe to run multiple times.
                </Typography>
                
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Button
                    variant="outline"
                    startIcon={<BuildIcon />}
                    onClick={handleBootstrap}
                    disabled={bootstrapMutation.isPending || !demoEnabled}
                    loading={bootstrapMutation.isPending}
                  >
                    Run Bootstrap
                  </Button>
                  
                  {status?.bootstrap_last_at && (
                    <Typography variant="caption" color="text.secondary">
                      Last run: {new Date(status.bootstrap_last_at).toLocaleString()}
                    </Typography>
                  )}
                </Box>

                {bootstrapMutation.isSuccess && (
                  <Alert severity="success" sx={{ mt: 1 }}>
                    Bootstrap completed successfully!
                  </Alert>
                )}
                {bootstrapMutation.isError && (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    Bootstrap failed: {String(bootstrapMutation.error)}
                  </Alert>
                )}
              </Stack>
            </Card>
          </Section>

          {/* Run Configuration */}
          <Section title="Scenario Execution" sx={{ mb: 3 }}>
            <Card>
              <Stack spacing={3}>
                {/* Industry Selection */}
                <FormControl fullWidth size="small">
                  <InputLabel id="industry-select-label">Industries</InputLabel>
                  <Select
                    labelId="industry-select-label"
                    multiple
                    value={selectedIndustries}
                    onChange={handleIndustryChange}
                    input={<OutlinedInput label="Industries" />}
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((value) => (
                          <Chip key={value} label={INDUSTRY_LABELS[value]} size="small" />
                        ))}
                      </Box>
                    )}
                    disabled={!demoEnabled || hasActiveRun}
                  >
                    {Object.entries(INDUSTRY_LABELS).map(([key, label]) => (
                      <MenuItem key={key} value={key}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                {/* Scenario Selection */}
                <FormControl fullWidth size="small">
                  <InputLabel id="scenario-select-label">Scenarios</InputLabel>
                  <Select
                    labelId="scenario-select-label"
                    multiple
                    value={selectedScenarios}
                    onChange={handleScenarioChange}
                    input={<OutlinedInput label="Scenarios" />}
                    renderValue={(selected) => (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {selected.map((id) => {
                          const scenario = filteredScenarios.find(s => s.scenario_id === id)
                          return <Chip key={id} label={scenario?.name || id} size="small" />
                        })}
                      </Box>
                    )}
                    disabled={!demoEnabled || hasActiveRun || filteredScenarios.length === 0}
                  >
                    {filteredScenarios.map((scenario) => (
                      <MenuItem key={scenario.scenario_id} value={scenario.scenario_id}>
                        <Box>
                          <Typography variant="body2">{scenario.name}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {scenario.description}
                          </Typography>
                        </Box>
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>

                <Divider />

                {/* Mode Selection */}
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Execution Mode
                  </Typography>
                  <Stack direction="row" spacing={1}>
                    <Chip
                      icon={<PlayArrowIcon />}
                      label="Burst"
                      color={selectedMode === 'burst' ? 'primary' : 'default'}
                      onClick={() => setSelectedMode('burst')}
                      disabled={!demoEnabled || hasActiveRun}
                    />
                    <Chip
                      icon={<ScheduleIcon />}
                      label="Scheduled"
                      color={selectedMode === 'scheduled' ? 'primary' : 'default'}
                      onClick={() => setSelectedMode('scheduled')}
                      disabled={!demoEnabled || hasActiveRun}
                    />
                    <Chip
                      icon={<AutorenewIcon />}
                      label="Continuous"
                      color={selectedMode === 'continuous' ? 'primary' : 'default'}
                      onClick={() => setSelectedMode('continuous')}
                      disabled={!demoEnabled || hasActiveRun}
                    />
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    {MODE_DESCRIPTIONS[selectedMode]}
                  </Typography>
                </Box>

                {/* Mode-specific options */}
                {selectedMode === 'burst' && (
                  <TextField
                    label="Number of Exceptions"
                    type="number"
                    size="small"
                    value={burstCount}
                    onChange={(e) => setBurstCount(Math.max(1, parseInt(e.target.value) || 1))}
                    InputProps={{ inputProps: { min: 1, max: 100 } }}
                    disabled={!demoEnabled || hasActiveRun}
                  />
                )}

                {selectedMode === 'scheduled' && (
                  <Stack direction="row" spacing={2}>
                    <TextField
                      label="Interval (seconds)"
                      type="number"
                      size="small"
                      value={scheduledInterval}
                      onChange={(e) => setScheduledInterval(Math.max(1, parseInt(e.target.value) || 1))}
                      InputProps={{ inputProps: { min: 1, max: 60 } }}
                      disabled={!demoEnabled || hasActiveRun}
                      sx={{ flex: 1 }}
                    />
                    <TextField
                      label="Duration (seconds)"
                      type="number"
                      size="small"
                      value={scheduledDuration}
                      onChange={(e) => setScheduledDuration(Math.max(10, parseInt(e.target.value) || 10))}
                      InputProps={{ inputProps: { min: 10, max: 600 } }}
                      disabled={!demoEnabled || hasActiveRun}
                      sx={{ flex: 1 }}
                    />
                  </Stack>
                )}

                <Divider />

                {/* Action Buttons */}
                <Stack direction="row" spacing={2}>
                  {!hasActiveRun ? (
                    <Button
                      variant="primary"
                      startIcon={<PlayArrowIcon />}
                      onClick={handleStartRun}
                      disabled={
                        !demoEnabled ||
                        selectedScenarios.length === 0 ||
                        startRunMutation.isPending
                      }
                      loading={startRunMutation.isPending}
                    >
                      {selectedMode === 'burst' ? 'Run Selected Now' : 'Start Run'}
                    </Button>
                  ) : (
                    <Button
                      variant="danger"
                      startIcon={<StopIcon />}
                      onClick={handleStopRun}
                      disabled={stopRunMutation.isPending}
                      loading={stopRunMutation.isPending}
                    >
                      Stop Run
                    </Button>
                  )}

                  <Tooltip title="Refresh status">
                    <IconButton onClick={() => refetchStatus()}>
                      <RefreshIcon />
                    </IconButton>
                  </Tooltip>
                </Stack>

                {startRunMutation.isError && (
                  <Alert severity="error">
                    Failed to start run: {String(startRunMutation.error)}
                  </Alert>
                )}
              </Stack>
            </Card>
          </Section>

          {/* Reset Section */}
          <Section title="Reset Demo Data" sx={{ mb: 3 }}>
            <Card>
              <Stack spacing={2}>
                <Alert severity="warning">
                  <AlertTitle>Caution</AlertTitle>
                  Resetting will delete all demo-generated exceptions. This cannot be undone.
                </Alert>

                <Button
                  variant="outline"
                  startIcon={<DeleteForeverIcon />}
                  onClick={() => setConfirmResetOpen(true)}
                  disabled={!demoEnabled || hasActiveRun || resetMutation.isPending}
                >
                  Reset Demo Data
                </Button>
              </Stack>
            </Card>
          </Section>
        </Grid>

        {/* Right Column: Status */}
        <Grid item xs={12} md={5}>
          {/* Current Run Status */}
          <Section title="Current Run Status" sx={{ mb: 3 }}>
            <Card>
              {activeRun ? (
                <Stack spacing={2}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {STATUS_ICONS[activeRun.status]}
                    <Typography variant="subtitle1" fontWeight={600}>
                      {activeRun.mode.charAt(0).toUpperCase() + activeRun.mode.slice(1)} Run
                    </Typography>
                    <Chip
                      label={activeRun.status}
                      size="small"
                      color={
                        activeRun.status === 'running' ? 'primary' :
                        activeRun.status === 'completed' ? 'success' :
                        activeRun.status === 'failed' ? 'error' : 'default'
                      }
                    />
                  </Box>

                  {activeRun.status === 'running' && activeRun.burst_count && (
                    <Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="caption">Progress</Typography>
                        <Typography variant="caption">
                          {activeRun.generated_count} / {activeRun.burst_count}
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={(activeRun.generated_count / activeRun.burst_count) * 100}
                      />
                    </Box>
                  )}

                  {activeRun.status === 'running' && !activeRun.burst_count && (
                    <Box>
                      <Typography variant="caption">
                        Generated: {activeRun.generated_count} exceptions
                      </Typography>
                      <LinearProgress variant="indeterminate" />
                    </Box>
                  )}

                  <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Started
                      </Typography>
                      <Typography variant="body2">
                        {activeRun.started_at 
                          ? new Date(activeRun.started_at).toLocaleTimeString()
                          : 'Pending'}
                      </Typography>
                    </Box>
                    {activeRun.ends_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Ends At
                        </Typography>
                        <Typography variant="body2">
                          {new Date(activeRun.ends_at).toLocaleTimeString()}
                        </Typography>
                      </Box>
                    )}
                  </Box>

                  {activeRun.error && (
                    <Alert severity="error" sx={{ mt: 1 }}>
                      {activeRun.error}
                    </Alert>
                  )}
                </Stack>
              ) : (
                <Typography color="text.secondary">
                  No active run. Configure and start a scenario above.
                </Typography>
              )}
            </Card>
          </Section>

          {/* Active Scenarios */}
          <Section title="Active Scenarios" sx={{ mb: 3 }}>
            <Card>
              {status?.scenarios_active && status.scenarios_active.length > 0 ? (
                <Stack spacing={1}>
                  {status.scenarios_active.map((scenarioId) => (
                    <Box
                      key={scenarioId}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        p: 1,
                        borderRadius: 1,
                        bgcolor: 'grey.50'
                      }}
                    >
                      <Typography variant="body2">
                        {scenarioId}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              ) : (
                <Typography color="text.secondary">
                  No active scenarios
                </Typography>
              )}
            </Card>
          </Section>

          {/* Demo Stats */}
          <Section title="Demo Environment">
            <Card>
              <Stack spacing={2}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Demo Tenants
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {status?.tenant_count ?? 0}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Available Scenarios
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {status?.scenarios_available?.length ?? 0}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Demo Exceptions
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {status?.exception_count ?? 0}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">
                    Catalog Version
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {catalog?.version ?? 'N/A'}
                  </Typography>
                </Box>
              </Stack>
            </Card>
          </Section>
        </Grid>
      </Grid>

      {/* Reset Confirmation Dialog */}
      <Dialog
        open={confirmResetOpen}
        onClose={() => setConfirmResetOpen(false)}
      >
        <DialogTitle>Reset Demo Data?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will permanently delete all demo-generated exceptions.
            Demo tenants will be preserved but their exception data will be cleared.
            This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <MuiButton onClick={() => setConfirmResetOpen(false)}>
            Cancel
          </MuiButton>
          <MuiButton
            onClick={handleReset}
            color="error"
            variant="contained"
            disabled={resetMutation.isPending}
          >
            {resetMutation.isPending ? 'Resetting...' : 'Reset'}
          </MuiButton>
        </DialogActions>
      </Dialog>
    </PageShell>
  )
}
