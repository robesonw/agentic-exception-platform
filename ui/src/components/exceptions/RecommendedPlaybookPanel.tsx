/**
 * Recommended Playbook Panel Component
 * 
 * Phase 7 P7-15: Displays playbook status for an exception.
 * Shows playbook name/version, step list with status, and highlights current step.
 */

import React from 'react'
import { Box, Typography, Paper, CircularProgress, Alert, Chip, List, ListItem, ListItemText } from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked'
import { useExceptionPlaybook, useRecalculatePlaybook, useCompletePlaybookStep } from '../../hooks/useExceptions'
import { useSnackbar } from '../common/SnackbarProvider'
import { useUser } from '../../hooks/useUser'
import LoadingButton from '../common/LoadingButton'

interface RecommendedPlaybookPanelProps {
  exceptionId: string
}

export default function RecommendedPlaybookPanel({ exceptionId }: RecommendedPlaybookPanelProps) {
  const { data, isLoading, isError, error } = useExceptionPlaybook(exceptionId)
  const recalculateMutation = useRecalculatePlaybook(exceptionId)
  const completeStepMutation = useCompletePlaybookStep(exceptionId)
  const { showSuccess, showError } = useSnackbar()
  const { userId } = useUser()

  // Track which step is currently being completed (for per-step loading)
  const [completingStepOrder, setCompletingStepOrder] = React.useState<number | null>(null)

  // Handle recalculation
  const handleRecalculate = async () => {
    try {
      await recalculateMutation.mutateAsync()
      showSuccess('Playbook recalculated successfully')
      // Refetch is handled automatically by the mutation's onSuccess
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to recalculate playbook')
    }
  }

  // Handle step completion
  const handleCompleteStep = async (stepOrder: number) => {
    setCompletingStepOrder(stepOrder)
    try {
      await completeStepMutation.mutateAsync({
        stepOrder,
        request: {
          actorType: 'human',
          actorId: userId,
          notes: null,
        },
      })
      showSuccess(`Step ${stepOrder} completed successfully`)
      // Refetch is handled automatically by the mutation's onSuccess
    } catch (err) {
      showError(err instanceof Error ? err.message : `Failed to complete step ${stepOrder}`)
    } finally {
      setCompletingStepOrder(null)
    }
  }

  // Determine if a step can be completed
  // Backend validates that step_order must be the next expected step (current_step)
  const canCompleteStep = (stepOrder: number, currentStep: number | null | undefined, status: string): boolean => {
    // Can complete if:
    // 1. Step is not already completed or skipped
    // 2. It's the current step (next step to complete)
    if (status === 'completed' || status === 'skipped') {
      return false
    }
    if (currentStep == null) {
      // No current step, can complete first step
      return stepOrder === 1
    }
    // Can only complete the current step (backend enforces this)
    return stepOrder === currentStep
  }

  // Loading state
  if (isLoading) {
    return (
      <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="subtitle2" gutterBottom>
          Recommended Playbook
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 3 }}>
          <CircularProgress size={24} />
        </Box>
      </Paper>
    )
  }

  // Error state
  if (isError) {
    return (
      <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2">
            Recommended Playbook
          </Typography>
          <LoadingButton
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleRecalculate}
            loading={recalculateMutation.isPending}
            disabled={recalculateMutation.isPending || isLoading}
          >
            Recalculate
          </LoadingButton>
        </Box>
        <Alert severity="error" sx={{ mt: 2 }}>
          {error?.message || 'Failed to load playbook status'}
        </Alert>
      </Paper>
    )
  }

  // Empty state (no playbook assigned)
  if (!data || !data.playbookId || !data.playbookName) {
    return (
      <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2">
            Recommended Playbook
          </Typography>
          <LoadingButton
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleRecalculate}
            loading={recalculateMutation.isPending}
            disabled={recalculateMutation.isPending || isLoading}
          >
            Recalculate
          </LoadingButton>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          No playbook available
        </Typography>
      </Paper>
    )
  }

  // Render playbook with steps
  return (
    <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2">
          Recommended Playbook
        </Typography>
        <LoadingButton
          size="small"
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={handleRecalculate}
          loading={recalculateMutation.isPending}
          disabled={recalculateMutation.isPending || isLoading}
        >
          Recalculate
        </LoadingButton>
      </Box>
      
      {/* Playbook name and version */}
      <Box sx={{ mt: 2, mb: 2 }}>
        <Typography variant="body1" sx={{ fontWeight: 500 }}>
          {data.playbookName}
        </Typography>
        {data.playbookVersion != null && (
          <Typography variant="body2" color="text.secondary">
            Version {data.playbookVersion}
          </Typography>
        )}
      </Box>

      {/* Steps list */}
      {data.steps && data.steps.length > 0 ? (
        <List dense sx={{ mt: 1 }}>
          {data.steps.map((step) => {
            const isCurrentStep = data.currentStep != null && step.stepOrder === data.currentStep
            const isCompleted = step.status === 'completed'
            const isSkipped = step.status === 'skipped'
            const canComplete = canCompleteStep(step.stepOrder, data.currentStep, step.status)
            const isCompleting = completingStepOrder === step.stepOrder
            
            return (
              <ListItem
                key={step.stepOrder}
                sx={{
                  py: 0.5,
                  px: 1,
                  borderRadius: 1,
                  backgroundColor: isCurrentStep ? 'action.selected' : 'transparent',
                  border: isCurrentStep ? '1px solid' : 'none',
                  borderColor: isCurrentStep ? 'primary.main' : 'transparent',
                  mb: 0.5,
                  flexDirection: 'column',
                  alignItems: 'stretch',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                  {/* Step status icon */}
                  {isCompleted ? (
                    <CheckCircleIcon sx={{ fontSize: 18, color: 'success.main' }} />
                  ) : isSkipped ? (
                    <RadioButtonUncheckedIcon sx={{ fontSize: 18, color: 'text.disabled' }} />
                  ) : (
                    <RadioButtonUncheckedIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                  )}
                  
                  {/* Step number and name */}
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: isCurrentStep ? 600 : 400 }}>
                          {step.stepOrder}. {step.name}
                        </Typography>
                        {isCurrentStep && (
                          <Chip
                            label="Current"
                            size="small"
                            color="primary"
                            sx={{ height: 20, fontSize: '0.65rem' }}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Typography variant="caption" color="text.secondary">
                        {step.actionType}
                      </Typography>
                    }
                  />
                </Box>
                
                {/* Mark Completed button for allowed steps */}
                {canComplete && (
                  <Box sx={{ mt: 1, ml: 4 }}>
                    <LoadingButton
                      size="small"
                      variant="outlined"
                      onClick={() => handleCompleteStep(step.stepOrder)}
                      loading={isCompleting}
                      disabled={isCompleting || completeStepMutation.isPending}
                    >
                      Mark Completed
                    </LoadingButton>
                  </Box>
                )}
              </ListItem>
            )
          })}
        </List>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          No steps available
        </Typography>
      )}
    </Paper>
  )
}

