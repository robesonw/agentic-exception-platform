import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Box, Typography, Button, CircularProgress, Alert, LinearProgress, Chip, Dialog, DialogTitle, DialogContent, DialogActions, TextField } from '@mui/material'
import EditIcon from '@mui/icons-material/Edit'
import { useTenant } from '../../hooks/useTenant'
import { getRateLimits, getRateLimitUsage, updateRateLimit } from '../../api/admin'
import PageHeader from '../../components/common/PageHeader'
import DataTable from '../../components/common/DataTable'
import ConfirmDialog from '../../components/common/ConfirmDialog'
import { useSnackbar } from '../../components/common/SnackbarProvider'
import type { DataTableColumn } from '../../components/common/DataTable'
import type { RateLimitConfig } from '../../api/admin'
import { isAdminEnabled } from '../../utils/featureFlags'

interface RateLimitRow extends RateLimitConfig {
  currentUsage?: number
  resetAt?: string
  utilization?: number
}

export default function RateLimitsPage() {
  const { tenantId } = useTenant()
  const queryClient = useQueryClient()
  const { showSuccess, showError } = useSnackbar()
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [selectedLimit, setSelectedLimit] = useState<RateLimitConfig | null>(null)
  const [newLimitValue, setNewLimitValue] = useState<number>(0)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)

  const isAdmin = isAdminEnabled()

  const { data: limitsData, isLoading: limitsLoading, dataUpdatedAt: limitsUpdatedAt } = useQuery({
    queryKey: ['rate-limits', tenantId],
    queryFn: () => getRateLimits(tenantId || ''),
    enabled: !!tenantId,
  })

  const { data: usageData, isLoading: usageLoading, dataUpdatedAt: usageUpdatedAt } = useQuery({
    queryKey: ['rate-limit-usage', tenantId],
    queryFn: () => getRateLimitUsage(tenantId || ''),
    enabled: !!tenantId,
    refetchInterval: 30000, // Refresh every 30s
  })

  const updateMutation = useMutation({
    mutationFn: (limit: Partial<RateLimitConfig>) => updateRateLimit(tenantId || '', limit),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rate-limits', tenantId] })
      queryClient.invalidateQueries({ queryKey: ['rate-limit-usage', tenantId] })
      setEditDialogOpen(false)
      setConfirmDialogOpen(false)
      setSelectedLimit(null)
      showSuccess('Rate limit updated successfully')
    },
    onError: (error) => {
      showError(`Failed to update rate limit: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['rate-limits', tenantId] })
    queryClient.invalidateQueries({ queryKey: ['rate-limit-usage', tenantId] })
  }

  // Merge limits with usage data
  const rows: RateLimitRow[] = (limitsData || []).map((limit) => {
    const usage = usageData?.usage.find((u) => u.limitType === limit.limitType)
    const utilization = usage && limit.limitValue > 0 
      ? (usage.currentCount / limit.limitValue) * 100 
      : 0
    
    return {
      ...limit,
      currentUsage: usage?.currentCount || 0,
      resetAt: usage?.resetAt,
      utilization: Math.min(utilization, 100),
    }
  })

  const handleEdit = (limit: RateLimitConfig) => {
    setSelectedLimit(limit)
    setNewLimitValue(limit.limitValue)
    setEditDialogOpen(true)
  }

  const handleConfirmUpdate = () => {
    if (!selectedLimit) return
    
    updateMutation.mutate({
      limitType: selectedLimit.limitType,
      limitValue: newLimitValue,
      windowSeconds: selectedLimit.windowSeconds,
      enabled: selectedLimit.enabled,
    })
  }

  const columns: DataTableColumn<RateLimitRow>[] = [
    {
      id: 'limitType',
      label: 'Limit Type',
      accessor: (row: RateLimitRow) => (
        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
          {row.limitType.replace(/_/g, ' ')}
        </Typography>
      ),
    },
    {
      id: 'limitValue',
      label: 'Limit',
      numeric: true,
      accessor: (row) => row.limitValue.toLocaleString(),
    },
    {
      id: 'windowSeconds',
      label: 'Window',
      accessor: (row) => `${row.windowSeconds}s`,
    },
    {
      id: 'currentUsage',
      label: 'Current Usage',
      numeric: true,
      accessor: (row: RateLimitRow) => (
        <Box>
          <Typography variant="body2">
            {row.currentUsage?.toLocaleString() || 0} / {row.limitValue.toLocaleString()}
          </Typography>
          {row.utilization !== undefined && (
            <LinearProgress
              variant="determinate"
              value={row.utilization}
              color={row.utilization > 90 ? 'error' : row.utilization > 70 ? 'warning' : 'primary'}
              sx={{ mt: 0.5, height: 4, borderRadius: 2 }}
            />
          )}
        </Box>
      ),
    },
    {
      id: 'utilization',
      label: 'Utilization',
      numeric: true,
      accessor: (row: RateLimitRow) => (
        <Chip
          label={`${row.utilization?.toFixed(1) || 0}%`}
          size="small"
          color={row.utilization && row.utilization > 90 ? 'error' : row.utilization && row.utilization > 70 ? 'warning' : 'default'}
        />
      ),
    },
    {
      id: 'enabled',
      label: 'Status',
      accessor: (row: RateLimitRow) => (
        <Chip
          label={row.enabled ? 'Enabled' : 'Disabled'}
          size="small"
          color={row.enabled ? 'success' : 'default'}
        />
      ),
    },
    ...(isAdmin ? [{
      id: 'actions',
      label: 'Actions',
      accessor: (row: RateLimitRow) => (
        <Button
          size="small"
          startIcon={<EditIcon />}
          onClick={() => handleEdit(row)}
        >
          Edit
        </Button>
      ),
    }] : []),
  ]

  if (!tenantId) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="warning">Please select a tenant to view rate limits.</Alert>
      </Box>
    )
  }

  const lastUpdated = usageUpdatedAt 
    ? new Date(usageUpdatedAt) 
    : (limitsUpdatedAt ? new Date(limitsUpdatedAt) : undefined)

  return (
    <Box>
      <PageHeader
        title="Rate Limits"
        subtitle={isAdmin ? "Manage rate limits per tenant" : "View current rate limit usage"}
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
      />

      {limitsLoading || usageLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {!isAdmin && (
            <Alert severity="info" sx={{ mb: 3 }}>
              View-only mode. Contact an administrator to modify rate limits.
            </Alert>
          )}

          <DataTable
            columns={columns as DataTableColumn<Record<string, unknown>>[]}
            rows={rows as Record<string, unknown>[]}
            loading={limitsLoading || usageLoading}
            page={0}
            pageSize={rows.length || 10}
            totalCount={rows.length}
            onPageChange={() => {}}
            onPageSizeChange={() => {}}
            emptyTitle="No rate limits configured"
            emptyMessage="No rate limits are currently configured for this tenant."
          />
        </>
      )}

      {/* Edit Dialog */}
      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Edit Rate Limit</DialogTitle>
        <DialogContent>
          {selectedLimit && (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {selectedLimit.limitType.replace(/_/g, ' ')}
              </Typography>
              <TextField
                fullWidth
                label="Limit Value"
                type="number"
                value={newLimitValue}
                onChange={(e) => setNewLimitValue(parseInt(e.target.value, 10) || 0)}
                sx={{ mt: 2 }}
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              setEditDialogOpen(false)
              setConfirmDialogOpen(true)
            }}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmDialogOpen}
        title="Update Rate Limit"
        message={`Are you sure you want to update the ${selectedLimit?.limitType.replace(/_/g, ' ')} limit to ${newLimitValue.toLocaleString()}?`}
        confirmLabel="Update"
        cancelLabel="Cancel"
        onConfirm={handleConfirmUpdate}
        onCancel={() => {
          setConfirmDialogOpen(false)
          setEditDialogOpen(true)
        }}
        loading={updateMutation.isPending}
        destructive={false}
      />
    </Box>
  )
}

