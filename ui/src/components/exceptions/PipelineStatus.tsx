/**
 * Pipeline Status Widget
 * 
 * Displays async processing status computed from latest events:
 * - Intake done
 * - Triage done
 * - Policy done
 * - Playbook matched
 * - Steps progressing
 * - Tool execution pending/completed
 */

import { useQuery } from '@tanstack/react-query'
import { Box, Typography, Paper, LinearProgress, Chip } from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked'
import PendingIcon from '@mui/icons-material/Pending'
import { fetchExceptionEvents } from '../../api/exceptions'
import { useTenant } from '../../hooks/useTenant'

interface PipelineStatusProps {
  exceptionId: string
}

interface PipelineStatusState {
  intakeDone: boolean
  triageDone: boolean
  policyDone: boolean
  playbookMatched: boolean
  stepsProgressing: boolean
  toolExecutionStatus: 'none' | 'pending' | 'completed'
  currentStep?: number
  totalSteps?: number
}

/**
 * Compute pipeline status from events
 */
function computePipelineStatus(events: Array<{ eventType: string; payload: Record<string, unknown> }>): PipelineStatusState {
  const state: PipelineStatusState = {
    intakeDone: false,
    triageDone: false,
    policyDone: false,
    playbookMatched: false,
    stepsProgressing: false,
    toolExecutionStatus: 'none',
  }

  // Process events in chronological order
  for (const event of events) {
    const eventType = event.eventType
    const payload = event.payload || {}

    // Intake done: ExceptionNormalized event
    if (eventType === 'ExceptionNormalized') {
      state.intakeDone = true
    }

    // Triage done: TriageCompleted event
    if (eventType === 'TriageCompleted') {
      state.triageDone = true
    }

    // Policy done: PolicyEvaluationCompleted event
    if (eventType === 'PolicyEvaluationCompleted') {
      state.policyDone = true
    }

    // Playbook matched: PlaybookMatched event
    if (eventType === 'PlaybookMatched') {
      state.playbookMatched = true
      // Extract playbook info if available
      if (payload.playbook_id) {
        // Could extract step count from playbook if available
      }
    }

    // Steps progressing: StepExecutionRequested or PlaybookStepCompletionRequested events
    if (eventType === 'StepExecutionRequested' || eventType === 'PlaybookStepCompletionRequested') {
      state.stepsProgressing = true
      const stepOrder = payload.step_order || payload.stepOrder
      if (typeof stepOrder === 'number') {
        state.currentStep = Math.max(state.currentStep || 0, stepOrder)
      }
    }
    
    // Check for PlaybookStarted to get total steps if available
    if (eventType === 'PlaybookStarted' && payload.steps) {
      const steps = payload.steps
      if (Array.isArray(steps)) {
        state.totalSteps = steps.length
      }
    }

    // Tool execution: ToolExecutionRequested or ToolExecutionCompleted
    if (eventType === 'ToolExecutionRequested') {
      state.toolExecutionStatus = 'pending'
    }
    if (eventType === 'ToolExecutionCompleted') {
      state.toolExecutionStatus = 'completed'
    }
    if (eventType === 'ToolExecutionFailed') {
      state.toolExecutionStatus = 'completed' // Show as completed even if failed
    }
  }

  return state
}

export default function PipelineStatus({ exceptionId }: PipelineStatusProps) {
  const { tenantId } = useTenant()

  // Fetch events for this exception
  const { data: eventsData, isLoading } = useQuery({
    queryKey: ['exception-events', exceptionId, tenantId],
    queryFn: () => {
      if (!tenantId) {
        throw new Error('Tenant ID is required')
      }
      return fetchExceptionEvents(exceptionId, {
        tenantId,
        pageSize: 100, // Get enough events to compute status
      })
    },
    enabled: !!tenantId && !!exceptionId,
    refetchInterval: 5000, // Poll every 5 seconds for async updates
  })

  const events = eventsData?.items || []
  const status = computePipelineStatus(events)

  // Calculate overall progress
  const stages = [
    status.intakeDone,
    status.triageDone,
    status.policyDone,
    status.playbookMatched,
    status.stepsProgressing || status.toolExecutionStatus !== 'none',
  ]
  const completedStages = stages.filter(Boolean).length
  const progressPercent = (completedStages / stages.length) * 100

  if (isLoading) {
    return (
      <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="subtitle2" gutterBottom>
          Pipeline Status
        </Typography>
        <Box sx={{ mt: 2 }}>
          <LinearProgress />
        </Box>
      </Paper>
    )
  }

  return (
    <Paper sx={{ p: 2, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="subtitle2">
          Pipeline Status
        </Typography>
        <Chip
          label={`${completedStages}/${stages.length}`}
          size="small"
          color={completedStages === stages.length ? 'success' : 'default'}
        />
      </Box>

      {/* Progress bar */}
      <Box sx={{ mb: 2 }}>
        <LinearProgress
          variant="determinate"
          value={progressPercent}
          sx={{ height: 6, borderRadius: 3 }}
        />
      </Box>

      {/* Status items */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {/* Intake */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {status.intakeDone ? (
            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
          ) : (
            <RadioButtonUncheckedIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
          )}
          <Typography variant="body2" sx={{ flex: 1 }}>
            Intake
          </Typography>
        </Box>

        {/* Triage */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {status.triageDone ? (
            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
          ) : (
            <RadioButtonUncheckedIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
          )}
          <Typography variant="body2" sx={{ flex: 1 }}>
            Triage
          </Typography>
        </Box>

        {/* Policy */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {status.policyDone ? (
            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
          ) : (
            <RadioButtonUncheckedIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
          )}
          <Typography variant="body2" sx={{ flex: 1 }}>
            Policy
          </Typography>
        </Box>

        {/* Playbook */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {status.playbookMatched ? (
            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
          ) : (
            <RadioButtonUncheckedIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
          )}
          <Typography variant="body2" sx={{ flex: 1 }}>
            Playbook Matched
          </Typography>
        </Box>

        {/* Steps */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {status.stepsProgressing ? (
            <>
              {status.currentStep && status.totalSteps ? (
                <>
                  <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    Steps ({status.currentStep}/{status.totalSteps})
                  </Typography>
                </>
              ) : (
                <>
                  <PendingIcon sx={{ color: 'warning.main', fontSize: 20 }} />
                  <Typography variant="body2" sx={{ flex: 1 }}>
                    Steps Progressing
                  </Typography>
                </>
              )}
            </>
          ) : status.playbookMatched ? (
            <RadioButtonUncheckedIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
          ) : (
            <RadioButtonUncheckedIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
          )}
          {!status.stepsProgressing && status.playbookMatched && (
            <Typography variant="body2" sx={{ flex: 1 }}>
              Steps Pending
            </Typography>
          )}
        </Box>

        {/* Tool Execution */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {status.toolExecutionStatus === 'completed' ? (
            <CheckCircleIcon sx={{ color: 'success.main', fontSize: 20 }} />
          ) : status.toolExecutionStatus === 'pending' ? (
            <PendingIcon sx={{ color: 'warning.main', fontSize: 20 }} />
          ) : (
            <RadioButtonUncheckedIcon sx={{ color: 'text.disabled', fontSize: 20 }} />
          )}
          <Typography variant="body2" sx={{ flex: 1 }}>
            {status.toolExecutionStatus === 'completed'
              ? 'Tool Execution'
              : status.toolExecutionStatus === 'pending'
              ? 'Tool Execution (Pending)'
              : 'Tool Execution'}
          </Typography>
        </Box>
      </Box>
    </Paper>
  )
}

