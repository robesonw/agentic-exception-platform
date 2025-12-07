import { useState } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Checkbox,
  FormControlLabel,
  Stack,
  Typography,
  Box,
} from '@mui/material'
import LoadingButton from '../common/LoadingButton.tsx'
import { rerunException } from '../../api/simulation.ts'
import { useTenant } from '../../hooks/useTenant.tsx'
import { useSnackbar } from '../common/SnackbarProvider.tsx'
import type { RerunRequest } from '../../types/simulation'

/**
 * Props for SimulationDialog component
 */
export interface SimulationDialogProps {
  /** Whether dialog is open */
  open: boolean
  /** Callback when dialog is closed */
  onClose: () => void
  /** Exception identifier */
  exceptionId: string
  /** Optional callback when simulation completes successfully */
  onSimulationComplete?: (simulationId: string) => void
}

/**
 * Severity options for override
 */
const SEVERITY_OPTIONS = [
  { value: '', label: 'No override' },
  { value: 'LOW', label: 'LOW' },
  { value: 'MEDIUM', label: 'MEDIUM' },
  { value: 'HIGH', label: 'HIGH' },
  { value: 'CRITICAL', label: 'CRITICAL' },
] as const

/**
 * Simulation Dialog Component
 * 
 * Allows users to configure and run a simulation for an exception
 * with optional overrides for severity, policies, and playbook.
 */
export default function SimulationDialog({
  open,
  onClose,
  exceptionId,
  onSimulationComplete,
}: SimulationDialogProps) {
  const { tenantId } = useTenant()
  const { showSuccess, showError } = useSnackbar()

  // Form state
  const [severityOverride, setSeverityOverride] = useState<string>('')
  const [policyOverrides, setPolicyOverrides] = useState<string>('')
  const [playbookId, setPlaybookId] = useState<string>('')
  const [simulationMode, setSimulationMode] = useState<boolean>(true)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)

  // Handle form submission
  const handleSubmit = async () => {
    if (!tenantId) {
      showError('Tenant ID is required to run simulation')
      return
    }

    setIsSubmitting(true)

    try {
      // Build overrides object
      const overrides: Record<string, unknown> = {}

      if (severityOverride) {
        overrides.severity = severityOverride
      }

      if (policyOverrides.trim()) {
        // Parse policy overrides (comma-separated IDs or JSON)
        try {
          // Try parsing as JSON first
          const parsed = JSON.parse(policyOverrides)
          overrides.policies = parsed
        } catch {
          // If not JSON, treat as comma-separated list
          const policyIds = policyOverrides
            .split(',')
            .map((id) => id.trim())
            .filter((id) => id.length > 0)
          if (policyIds.length > 0) {
            overrides.policies = policyIds
          }
        }
      }

      if (playbookId.trim()) {
        overrides.playbook_id = playbookId.trim()
      }

      // Build request payload
      const request: RerunRequest = {
        tenant_id: tenantId,
        simulation: simulationMode,
        ...(Object.keys(overrides).length > 0 ? { overrides } : {}),
      }

      // Call API
      const response = await rerunException(exceptionId, request)

      // Success
      showSuccess(`Simulation completed successfully. Simulation ID: ${response.simulation_id}`)

      // Call callback if provided
      if (onSimulationComplete) {
        onSimulationComplete(response.simulation_id)
      }

      // Close dialog
      onClose()

      // Reset form
      setSeverityOverride('')
      setPolicyOverrides('')
      setPlaybookId('')
      setSimulationMode(true)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to run simulation'
      showError(errorMessage)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle dialog close
  const handleClose = () => {
    if (!isSubmitting) {
      onClose()
    }
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Re-run Simulation</DialogTitle>
      <DialogContent>
        <Stack spacing={3} sx={{ mt: 1 }}>
          {/* Severity Override */}
          <FormControl fullWidth>
            <InputLabel>Severity Override</InputLabel>
            <Select
              value={severityOverride}
              onChange={(e) => setSeverityOverride(e.target.value)}
              label="Severity Override"
            >
              {SEVERITY_OPTIONS.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
              Override the severity level for this simulation (leave empty to use original)
            </Typography>
          </FormControl>

          {/* Policy Overrides */}
          <TextField
            fullWidth
            label="Policy Overrides"
            value={policyOverrides}
            onChange={(e) => setPolicyOverrides(e.target.value)}
            placeholder='Comma-separated policy IDs or JSON array, e.g., "policy1,policy2" or ["policy1","policy2"]'
            multiline
            rows={3}
            helperText="Enter policy IDs to override (comma-separated) or JSON array"
          />

          {/* Playbook Selector */}
          <TextField
            fullWidth
            label="Playbook ID"
            value={playbookId}
            onChange={(e) => setPlaybookId(e.target.value)}
            placeholder="Enter playbook ID or name (optional)"
            helperText="Specify a playbook to use for this simulation (optional)"
          />

          {/* Simulation Mode Checkbox */}
          <FormControlLabel
            control={
              <Checkbox
                checked={simulationMode}
                onChange={(e) => setSimulationMode(e.target.checked)}
              />
            }
            label="Simulation mode (no real action)"
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: -2 }}>
            When enabled, the simulation will not execute real actions. Always enabled by default for safety.
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Box sx={{ display: 'flex', gap: 1, width: '100%', justifyContent: 'flex-end' }}>
          <LoadingButton onClick={handleClose} disabled={isSubmitting}>
            Cancel
          </LoadingButton>
          <LoadingButton
            onClick={handleSubmit}
            loading={isSubmitting}
            variant="contained"
            disabled={!tenantId}
          >
            Run Simulation
          </LoadingButton>
        </Box>
      </DialogActions>
    </Dialog>
  )
}

