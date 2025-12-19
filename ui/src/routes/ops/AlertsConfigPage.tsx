import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Alert,
  Chip,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControlLabel,
  Switch,
  Tabs,
  Tab,
  IconButton,
  Stack,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import CancelIcon from '@mui/icons-material/Cancel'
import PageHeader from '../../components/common/PageHeader'
import { useTenant } from '../../hooks/useTenant'
import { isOpsEnabled } from '../../utils/featureFlags'
import {
  listAlertConfigs,
  createAlertConfig,
  updateAlertConfig,
  deleteAlertConfig,
  listAlertChannels,
  createAlertChannel,
  deleteAlertChannel,
  verifyAlertChannel,
} from '../../api/ops'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import CodeViewer from '../../components/common/CodeViewer'
import { useSnackbar } from '../../components/common/SnackbarProvider'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { AlertConfig, AlertChannel } from '../../api/ops'

interface TabPanelProps {
  children?: React.ReactNode
  index: number
  value: number
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`alerts-tabpanel-${index}`}
      aria-labelledby={`alerts-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  )
}

export default function AlertsConfigPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [tabValue, setTabValue] = useState(0)
  const [configDialogOpen, setConfigDialogOpen] = useState(false)
  const [channelDialogOpen, setChannelDialogOpen] = useState(false)
  const [selectedConfig, setSelectedConfig] = useState<AlertConfig | null>(null)
  const [selectedChannel, setSelectedChannel] = useState<AlertChannel | null>(null)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [confirmAction, setConfirmAction] = useState<'delete-config' | 'delete-channel' | null>(null)

  // Form state
  const [configForm, setConfigForm] = useState<Partial<AlertConfig>>({
    alertType: 'SLA_BREACH',
    name: '',
    enabled: true,
    thresholdValue: undefined,
    thresholdUnit: undefined,
    severity: undefined,
    channels: [],
  })

  const [channelForm, setChannelForm] = useState<Partial<AlertChannel>>({
    channelType: 'webhook',
    config: {},
  })

  if (!isOpsEnabled()) {
    return (
      <Box>
        <Alert severity="error">Ops features are not enabled. Set VITE_OPS_ENABLED=true in ui/.env</Alert>
      </Box>
    )
  }

  const { data: configs, isLoading: configsLoading, dataUpdatedAt: configsUpdatedAt } = useQuery({
    queryKey: ['alert-configs', tenantId],
    queryFn: () => listAlertConfigs(tenantId || ''),
    enabled: !!tenantId,
  })

  const { data: channels, isLoading: channelsLoading, dataUpdatedAt: channelsUpdatedAt } = useQuery({
    queryKey: ['alert-channels', tenantId],
    queryFn: () => listAlertChannels(tenantId || ''),
    enabled: !!tenantId,
  })

  const createConfigMutation = useMutation({
    mutationFn: (config: Omit<AlertConfig, 'id' | 'createdAt' | 'updatedAt'>) =>
      createAlertConfig(tenantId || '', config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-configs', tenantId] })
      setConfigDialogOpen(false)
      setConfigForm({
        alertType: 'SLA_BREACH',
        name: '',
        enabled: true,
        thresholdValue: undefined,
        thresholdUnit: undefined,
        severity: undefined,
        channels: [],
      })
      showSuccess('Alert rule created successfully')
    },
    onError: (error) => {
      showError(`Failed to create alert rule: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const updateConfigMutation = useMutation({
    mutationFn: ({ id, config }: { id: string; config: Partial<AlertConfig> }) =>
      updateAlertConfig(id, tenantId || '', config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-configs', tenantId] })
      setConfigDialogOpen(false)
      setSelectedConfig(null)
      showSuccess('Alert rule updated successfully')
    },
    onError: (error) => {
      showError(`Failed to update alert rule: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const deleteConfigMutation = useMutation({
    mutationFn: (id: string) => deleteAlertConfig(id, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-configs', tenantId] })
      setConfirmDialogOpen(false)
      setConfirmAction(null)
      showSuccess('Alert rule deleted successfully')
    },
    onError: (error) => {
      showError(`Failed to delete alert rule: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const createChannelMutation = useMutation({
    mutationFn: (channel: Omit<AlertChannel, 'id' | 'createdAt'>) =>
      createAlertChannel(tenantId || '', channel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-channels', tenantId] })
      setChannelDialogOpen(false)
      setChannelForm({
        channelType: 'webhook',
        config: {},
      })
      showSuccess('Alert channel created successfully')
    },
    onError: (error) => {
      showError(`Failed to create alert channel: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const deleteChannelMutation = useMutation({
    mutationFn: (id: string) => deleteAlertChannel(id, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-channels', tenantId] })
      setConfirmDialogOpen(false)
      setConfirmAction(null)
      showSuccess('Alert channel deleted successfully')
    },
    onError: (error) => {
      showError(`Failed to delete alert channel: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const verifyChannelMutation = useMutation({
    mutationFn: (id: string) => verifyAlertChannel(id, tenantId || ''),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alert-channels', tenantId] })
      showSuccess('Alert channel verified successfully')
    },
    onError: (error) => {
      showError(`Failed to verify alert channel: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['alert-configs', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['alert-channels', tenantId] })
  }

  const lastUpdated = tabValue === 0
    ? (configsUpdatedAt ? new Date(configsUpdatedAt) : undefined)
    : (channelsUpdatedAt ? new Date(channelsUpdatedAt) : undefined)

  const handleCreateConfig = () => {
    setSelectedConfig(null)
    setConfigForm({
      alertType: 'SLA_BREACH',
      name: '',
      enabled: true,
      thresholdValue: undefined,
      thresholdUnit: undefined,
      severity: undefined,
      channels: [],
    })
    setConfigDialogOpen(true)
  }

  const handleEditConfig = (config: AlertConfig) => {
    setSelectedConfig(config)
    setConfigForm(config)
    setConfigDialogOpen(true)
  }

  const handleSaveConfig = () => {
    if (selectedConfig?.id) {
      updateConfigMutation.mutate({ id: selectedConfig.id, config: configForm })
    } else {
      createConfigMutation.mutate(configForm as Omit<AlertConfig, 'id' | 'createdAt' | 'updatedAt'>)
    }
  }

  const handleCreateChannel = () => {
    setSelectedChannel(null)
    setChannelForm({
      channelType: 'webhook',
      config: {},
    })
    setChannelDialogOpen(true)
  }

  const handleSaveChannel = () => {
    createChannelMutation.mutate(channelForm as Omit<AlertChannel, 'id' | 'createdAt'>)
  }

  const configColumns: DataTableColumn<AlertConfig>[] = [
    {
      id: 'name',
      label: 'Name',
      accessor: (row) => row.name,
    },
    {
      id: 'alertType',
      label: 'Alert Type',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {row.alertType.replace(/_/g, ' ')}
        </Typography>
      ),
    },
    {
      id: 'enabled',
      label: 'Status',
      accessor: (row) => (
        <Chip
          label={row.enabled ? 'Enabled' : 'Disabled'}
          size="small"
          color={row.enabled ? 'success' : 'default'}
        />
      ),
    },
    {
      id: 'thresholdValue',
      label: 'Threshold',
      accessor: (row) => row.thresholdValue ? `${row.thresholdValue} ${row.thresholdUnit || ''}` : '-',
    },
    {
      id: 'channels',
      label: 'Channels',
      accessor: (row) => row.channels?.length || 0,
    },
    {
      id: 'actions',
      label: 'Actions',
      accessor: (row) => (
        <Stack direction="row" spacing={1}>
          <IconButton size="small" onClick={() => handleEditConfig(row)}>
            <EditIcon fontSize="small" />
          </IconButton>
          <IconButton
            size="small"
            color="error"
            onClick={() => {
              setSelectedConfig(row)
              setConfirmAction('delete-config')
              setConfirmDialogOpen(true)
            }}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Stack>
      ),
    },
  ]

  const channelColumns: DataTableColumn<AlertChannel>[] = [
    {
      id: 'channelType',
      label: 'Type',
      accessor: (row) => (
        <Chip label={row.channelType} size="small" color="primary" />
      ),
    },
    {
      id: 'verified',
      label: 'Status',
      accessor: (row) => (
        <Chip
          icon={row.verified ? <CheckCircleIcon /> : <CancelIcon />}
          label={row.verified ? 'Verified' : 'Unverified'}
          size="small"
          color={row.verified ? 'success' : 'warning'}
        />
      ),
    },
    {
      id: 'config',
      label: 'Configuration',
      accessor: (row) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {JSON.stringify(row.config).substring(0, 50)}...
        </Typography>
      ),
    },
    {
      id: 'actions',
      label: 'Actions',
      accessor: (row) => (
        <Stack direction="row" spacing={1}>
          {!row.verified && (
            <Button
              size="small"
              onClick={() => verifyChannelMutation.mutate(row.id)}
              disabled={verifyChannelMutation.isPending}
            >
              Verify
            </Button>
          )}
          <IconButton
            size="small"
            color="error"
            onClick={() => {
              setSelectedChannel(row)
              setConfirmAction('delete-channel')
              setConfirmDialogOpen(true)
            }}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Stack>
      ),
    },
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to configure alerts.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Alerts Configuration"
        subtitle="Configure alert channels and notification rules"
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
      />

      <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)} sx={{ mb: 2 }}>
        <Tab label="Alert Rules" />
        <Tab label="Channels" />
      </Tabs>

      <TabPanel value={tabValue} index={0}>
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateConfig}
          >
            Create Alert Rule
          </Button>
        </Box>
        <DataTable
          columns={configColumns as DataTableColumn<Record<string, unknown>>[]}
          rows={(configs || []) as Record<string, unknown>[]}
          loading={configsLoading}
          page={0}
          pageSize={configs?.length || 10}
          totalCount={configs?.length || 0}
          onPageChange={() => {}}
          onPageSizeChange={() => {}}
          emptyTitle="No alert rules configured"
          emptyMessage="No alert rules are currently configured. Create an alert rule to get started."
        />
      </TabPanel>

      <TabPanel value={tabValue} index={1}>
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateChannel}
          >
            Create Channel
          </Button>
        </Box>
        <DataTable
          columns={channelColumns as DataTableColumn<Record<string, unknown>>[]}
          rows={(channels || []) as Record<string, unknown>[]}
          loading={channelsLoading}
          page={0}
          pageSize={channels?.length || 10}
          totalCount={channels?.length || 0}
          onPageChange={() => {}}
          onPageSizeChange={() => {}}
          emptyTitle="No alert channels configured"
          emptyMessage="No alert channels are currently configured. Create an alert channel to receive notifications."
        />
      </TabPanel>

      {/* Config Dialog */}
      <Dialog open={configDialogOpen} onClose={() => setConfigDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{selectedConfig ? 'Edit Alert Rule' : 'Create Alert Rule'}</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Name"
            value={configForm.name}
            onChange={(e) => setConfigForm({ ...configForm, name: e.target.value })}
            sx={{ mt: 2 }}
          />
          <TextField
            fullWidth
            select
            label="Alert Type"
            value={configForm.alertType}
            onChange={(e) => setConfigForm({ ...configForm, alertType: e.target.value as AlertConfig['alertType'] })}
            sx={{ mt: 2 }}
            SelectProps={{
              native: true,
            }}
          >
            <option value="SLA_BREACH">SLA Breach</option>
            <option value="SLA_IMMINENT">SLA Imminent</option>
            <option value="DLQ_GROWTH">DLQ Growth</option>
            <option value="WORKER_UNHEALTHY">Worker Unhealthy</option>
            <option value="ERROR_RATE_HIGH">Error Rate High</option>
            <option value="THROUGHPUT_LOW">Throughput Low</option>
          </TextField>
          <TextField
            fullWidth
            label="Threshold Value"
            type="number"
            value={configForm.thresholdValue || ''}
            onChange={(e) => setConfigForm({ ...configForm, thresholdValue: parseFloat(e.target.value) })}
            sx={{ mt: 2 }}
          />
          <TextField
            fullWidth
            label="Threshold Unit"
            value={configForm.thresholdUnit || ''}
            onChange={(e) => setConfigForm({ ...configForm, thresholdUnit: e.target.value })}
            sx={{ mt: 2 }}
          />
          <FormControlLabel
            control={
              <Switch
                checked={configForm.enabled}
                onChange={(e) => setConfigForm({ ...configForm, enabled: e.target.checked })}
              />
            }
            label="Enabled"
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSaveConfig}
            disabled={createConfigMutation.isPending || updateConfigMutation.isPending}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Channel Dialog */}
      <Dialog open={channelDialogOpen} onClose={() => setChannelDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Alert Channel</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            select
            label="Channel Type"
            value={channelForm.channelType}
            onChange={(e) => setChannelForm({ ...channelForm, channelType: e.target.value as 'webhook' | 'email' })}
            sx={{ mt: 2 }}
            SelectProps={{
              native: true,
            }}
          >
            <option value="webhook">Webhook</option>
            <option value="email">Email</option>
          </TextField>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 1 }}>
            Configuration (JSON)
          </Typography>
          <CodeViewer
            code={JSON.stringify(channelForm.config || {}, null, 2)}
            maxHeight={200}
            collapsible
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setChannelDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSaveChannel}
            disabled={createChannelMutation.isPending}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmDialogOpen}
        title={confirmAction === 'delete-config' ? 'Delete Alert Rule' : 'Delete Channel'}
        message={
          confirmAction === 'delete-config'
            ? `Are you sure you want to delete the alert rule "${selectedConfig?.name}"?`
            : `Are you sure you want to delete this channel?`
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={() => {
          if (confirmAction === 'delete-config' && selectedConfig) {
            deleteConfigMutation.mutate(selectedConfig.id!)
          } else if (confirmAction === 'delete-channel' && selectedChannel) {
            deleteChannelMutation.mutate(selectedChannel.id)
          }
        }}
        onCancel={() => {
          setConfirmDialogOpen(false)
          setConfirmAction(null)
        }}
        loading={deleteConfigMutation.isPending || deleteChannelMutation.isPending}
        destructive
      />
    </Box>
  )
}

