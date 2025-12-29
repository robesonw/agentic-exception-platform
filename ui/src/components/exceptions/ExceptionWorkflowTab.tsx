import { useEffect, useRef, useCallback } from 'react'
import { Box, Typography, Alert, IconButton, Tooltip } from '@mui/material'
import { Refresh } from '@mui/icons-material'
import { useExceptionWorkflowGraph } from '../../hooks/useExceptions'
import { WorkflowViewerWithProvider } from './WorkflowViewer'

export interface ExceptionWorkflowTabProps {
  /** Exception identifier */
  exceptionId: string
  /** Whether this tab is currently active (for optimized polling) */
  isActive?: boolean
}

/**
 * Exception Workflow Tab Component
 * 
 * Phase 13 P13-26: Workflow Viewer using React Flow + dagre.
 * Shows workflow diagram with pipeline stages and execution status.
 */
export default function ExceptionWorkflowTab({ exceptionId, isActive = true }: ExceptionWorkflowTabProps) {
  const { 
    data: workflowData, 
    isLoading, 
    isError, 
    error, 
    refetch 
  } = useExceptionWorkflowGraph(exceptionId)
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  
  // Manual refresh callback
  const handleManualRefresh = useCallback(() => {
    refetch()
  }, [refetch])

  // Auto-refresh workflow data every 5 seconds when tab is active
  useEffect(() => {
    if (!isActive) {
      // Clear interval when tab is not active to save resources
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }

    // Start polling when tab becomes active
    intervalRef.current = setInterval(() => {
      refetch()
    }, 5000) // 5 seconds

    // Cleanup on unmount or when tab becomes inactive
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [refetch, isActive])

  // Also re-start polling if exceptionId changes
  useEffect(() => {
    if (isActive && intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = setInterval(() => {
        refetch()
      }, 5000)
    }
  }, [exceptionId, refetch, isActive])

  if (isError) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" 
          action={
            <IconButton size="small" onClick={handleManualRefresh}>
              <Refresh />
            </IconButton>
          }
        >
          Failed to load workflow: {error?.message || 'Unknown error'}
        </Alert>
      </Box>
    )
  }

  if (!workflowData) {
    return (
      <Box sx={{ p: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography color="text.secondary">
          No workflow data available for this exception
        </Typography>
        <Tooltip title="Refresh workflow data">
          <IconButton onClick={handleManualRefresh} disabled={isLoading}>
            <Refresh />
          </IconButton>
        </Tooltip>
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Header info with manual refresh */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box sx={{ flex: 1 }}>
          {(workflowData.playbook_id || workflowData.playbook_name) && (
            <Box sx={{ p: 2, backgroundColor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="subtitle2" color="text.secondary">
                Playbook: <strong>{workflowData.playbook_name || workflowData.playbook_id}</strong>
                {workflowData.playbook_id && workflowData.playbook_name && (
                  <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                    (ID: {workflowData.playbook_id})
                  </Typography>
                )}
              </Typography>
              {workflowData.current_stage && (
                <Typography variant="body2" color="text.secondary">
                  Current Stage: <strong>{workflowData.current_stage}</strong>
                </Typography>
              )}
              {workflowData.exception_current_step && (
                <Typography variant="body2" color="text.secondary">
                  Current Step: <strong>Step {workflowData.exception_current_step}</strong>
                  {workflowData.playbook_steps && Array.isArray(workflowData.playbook_steps) && (
                    <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      of {workflowData.playbook_steps.length}
                    </Typography>
                  )}
                </Typography>
              )}
            </Box>
          )}
        </Box>
        <Tooltip title={isActive ? "Auto-refreshing every 5s. Click to refresh now." : "Click to refresh manually"}>
          <IconButton onClick={handleManualRefresh} disabled={isLoading} sx={{ ml: 1 }}>
            <Refresh sx={{ 
              animation: isLoading ? 'spin 1s linear infinite' : 'none',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' },
              }
            }} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Workflow viewer */}
      <WorkflowViewerWithProvider
        exceptionId={exceptionId}
        nodes={workflowData.nodes}
        edges={workflowData.edges}
        currentStage={workflowData.current_stage}
        loading={isLoading}
        error={isError ? ((error as Error)?.message || 'Unknown error') : null}
      />

      {/* Playbook steps info (if available) */}
      {workflowData.playbook_steps && Array.isArray(workflowData.playbook_steps) && workflowData.playbook_steps.length > 0 && (
        <Box sx={{ p: 2, backgroundColor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Playbook Steps
          </Typography>
          {workflowData.playbook_steps.map((step: any, index: number) => {
            const stepNumber = index + 1
            const isCurrentStep = stepNumber === workflowData.exception_current_step
            const isCompletedStep = workflowData.exception_current_step ? stepNumber < workflowData.exception_current_step : false
            
            return (
              <Typography 
                key={index} 
                variant="body2" 
                sx={{ 
                  ml: 2,
                  fontWeight: isCurrentStep ? 600 : 400,
                  color: isCurrentStep ? 'primary.main' : isCompletedStep ? 'success.main' : 'text.secondary',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                }}
              >
                {isCompletedStep && '✓ '}
                {isCurrentStep && '▶ '}
                {stepNumber}. {typeof step === 'string' ? step : step.name || step.text || 'Step'}
                {step.action_type && (
                  <Typography component="span" variant="caption" color="text.secondary">
                    ({step.action_type})
                  </Typography>
                )}
              </Typography>
            )
          })}
        </Box>
      )}
    </Box>
  )
}